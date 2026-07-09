"""Transaction listing, filtering, manual categorization, and CSV export."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_unlocked
from ..models import Account, CategoryRule, Transaction
from ..schemas import CategoryRuleIn, CategoryUpdate, TransactionOut
from ..services import categorize

router = APIRouter(tags=["transactions"], dependencies=[Depends(require_unlocked)])


@router.get("/transactions", response_model=list[TransactionOut])
def list_transactions(
    db: Session = Depends(get_db),
    account_id: int | None = None,
    category: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[Transaction]:
    stmt = select(Transaction).order_by(Transaction.posted_at.desc())
    if account_id is not None:
        stmt = stmt.where(Transaction.account_id == account_id)
    if category is not None:
        stmt = stmt.where(Transaction.category == category)
    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt))


def _csv_amount(minor: int) -> str:
    """Exact decimal string from integer cents (no float representation issues)."""
    sign = "-" if minor < 0 else ""
    return f"{sign}{abs(minor) // 100}.{abs(minor) % 100:02d}"


def _csv_text(value: str | None) -> str:
    """Neutralize spreadsheet formula injection: bank-supplied text starting with a
    formula character (=, +, @, tab) gets a leading apostrophe. '-' is left alone —
    it's far more often a legitimate leading hyphen than an attack."""
    text = value or ""
    return f"'{text}" if text[:1] in ("=", "+", "@", "\t") else text


@router.get("/transactions/export.csv")
def export_csv(
    db: Session = Depends(get_db),
    account_id: int | None = None,
    category: str | None = None,
    start: date | None = None,
    end: date | None = None,
) -> Response:
    """Download transactions as CSV (oldest first), optionally filtered."""
    stmt = select(Transaction).order_by(Transaction.posted_at.asc())
    if account_id is not None:
        stmt = stmt.where(Transaction.account_id == account_id)
    if category is not None:
        stmt = stmt.where(Transaction.category == category)
    if start is not None:
        stmt = stmt.where(Transaction.posted_at >= datetime.combine(start, time.min, timezone.utc))
    if end is not None:
        stmt = stmt.where(Transaction.posted_at <= datetime.combine(end, time.max, timezone.utc))

    accounts = {a.id: a for a in db.scalars(select(Account))}
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(
        ["date", "account", "payee", "description", "amount", "currency", "category", "pending", "memo"]
    )
    for t in db.scalars(stmt):
        acct = accounts.get(t.account_id)
        writer.writerow(
            [
                t.posted_at.date().isoformat(),
                _csv_text(acct.name if acct else ""),
                _csv_text(t.payee),
                _csv_text(t.description),
                _csv_amount(t.amount_minor),
                acct.currency if acct else "USD",
                t.category,
                "yes" if t.pending else "no",
                _csv_text(t.memo),
            ]
        )

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="blackline-transactions-{stamp}.csv"'
        },
    )


@router.patch("/transactions/{txn_id}/category", response_model=TransactionOut)
def set_category(
    txn_id: int, body: CategoryUpdate, learn: bool = True, db: Session = Depends(get_db)
) -> Transaction:
    txn = db.get(Transaction, txn_id)
    if txn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    txn.category = body.category
    txn.category_source = "user"  # protect from auto re-categorization
    db.flush()
    if learn:
        # Turn this correction into a rule and propagate to similar auto transactions.
        categorize.learn_from_correction(db, txn, body.category)
    else:
        db.commit()
    db.refresh(txn)
    return txn


@router.post("/recategorize")
def recategorize(db: Session = Depends(get_db)) -> dict:
    """Re-apply current rules + built-in keywords to all auto-categorized transactions."""
    changed = categorize.recategorize_all(db)
    return {"transactions_recategorized": changed}


@router.post("/rules", status_code=status.HTTP_201_CREATED)
def add_rule(body: CategoryRuleIn, db: Session = Depends(get_db)) -> dict:
    rule = CategoryRule(pattern=body.pattern, category=body.category, priority=body.priority)
    db.add(rule)
    db.commit()
    changed = categorize.recategorize_all(db)
    return {"rule_id": rule.id, "transactions_recategorized": changed}
