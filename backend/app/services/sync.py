"""Sync orchestration: pull from SimpleFIN and upsert locally (idempotent).

Idempotency: accounts keyed by external_id; transactions by (account_id, external_id);
holdings by (account_id, external_id). Re-running a sync never duplicates rows.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import secure_db
from ..integrations import simplefin
from ..models import Account, CategoryRule, Holding, Transaction
from ..schemas import SyncResult
from ..security import vault
from ..security.lock import app_lock
from . import categorize


def _get_access_url(db: Session) -> str:
    key = app_lock.require_key()
    access_url = vault.get_secret(db, key, vault.SIMPLEFIN_ACCESS_URL)
    if access_url is None:
        raise RuntimeError("no SimpleFIN account connected; connect one in Settings first")
    return access_url.decode("utf-8")


def run_sync(db: Session, lookback_days: int = 90) -> SyncResult:
    """Pull recent data and upsert. Returns a summary; raises on hard failures."""
    access_url = _get_access_url(db)
    # Snapshot the pre-sync blob so a disk fault can lose at most the syncs since
    # the newest backup.
    secure_db.rotate_backup()
    start = datetime.now(UTC) - timedelta(days=lookback_days)

    try:
        payload = simplefin.fetch_accounts(access_url, start_date=start)
    except simplefin.SimpleFINError as exc:
        audit.record(db, "sync", detail=str(exc), success=False)
        raise

    accounts_upserted = 0
    txns_inserted = 0
    holdings_upserted = 0
    rules = list(db.scalars(select(CategoryRule).order_by(CategoryRule.priority.asc())))

    for acct in payload.accounts:
        db_acct = db.scalar(select(Account).where(Account.external_id == acct.external_id))
        if db_acct is None:
            db_acct = Account(external_id=acct.external_id)
            db.add(db_acct)
        db_acct.org_name = acct.org_name
        db_acct.name = acct.name
        db_acct.currency = acct.currency
        db_acct.balance_minor = acct.balance_minor
        db_acct.available_minor = acct.available_minor
        db_acct.balance_date = acct.balance_date
        db_acct.account_type = _infer_type(acct)
        db.flush()  # assign db_acct.id
        accounts_upserted += 1

        for t in acct.transactions:
            existing = db.scalar(
                select(Transaction).where(
                    Transaction.account_id == db_acct.id,
                    Transaction.external_id == t.external_id,
                )
            )
            if existing is None:
                category = categorize.categorize_text(
                    t.payee,
                    t.description,
                    rules,
                    amount_minor=t.amount_minor,
                    account_type=db_acct.account_type,
                )
                db.add(
                    Transaction(
                        account_id=db_acct.id,
                        external_id=t.external_id,
                        posted_at=t.posted_at,
                        amount_minor=t.amount_minor,
                        description=t.description,
                        payee=t.payee,
                        memo=t.memo,
                        pending=t.pending,
                        category=category,
                        category_source="auto",
                    )
                )
                txns_inserted += 1
            else:
                # Update mutable fields (e.g. pending -> posted). Preserve user category.
                existing.pending = t.pending
                existing.amount_minor = t.amount_minor

        for h in acct.holdings:
            db_h = db.scalar(
                select(Holding).where(
                    Holding.account_id == db_acct.id, Holding.external_id == h.external_id
                )
            )
            if db_h is None:
                db_h = Holding(account_id=db_acct.id, external_id=h.external_id)
                db.add(db_h)
            db_h.symbol = h.symbol
            db_h.description = h.description
            db_h.shares = h.shares
            db_h.market_value_minor = h.market_value_minor
            db_h.cost_basis_minor = h.cost_basis_minor
            db_h.currency = h.currency
            db_h.as_of = h.as_of
            holdings_upserted += 1

    from .transfers import match_transfers

    match_transfers(db)
    db.commit()
    from .insights import record_snapshot
    from .portfolio import record_portfolio_snapshot

    record_snapshot(db)  # capture a net-worth point from the freshly-synced balances
    record_portfolio_snapshot(db)
    audit.record(
        db,
        "sync",
        detail=f"accounts={accounts_upserted} txns+={txns_inserted} holdings={holdings_upserted}",
        success=True,
    )
    return SyncResult(
        accounts_upserted=accounts_upserted,
        transactions_inserted=txns_inserted,
        holdings_upserted=holdings_upserted,
        errors=payload.errors,
    )


def _infer_type(acct: simplefin.NormAccount) -> str:
    if acct.holdings:
        return "investment"
    name = (acct.name or "").lower()
    if any(k in name for k in ("credit", "card", "visa", "mastercard", "amex")):
        return "credit"
    if any(k in name for k in ("loan", "mortgage")):
        return "loan"
    return "depository"
