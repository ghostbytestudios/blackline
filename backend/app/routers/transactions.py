"""Transaction listing, filtering, manual categorization, and CSV export."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, time, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from sqlalchemy import func, or_

from ..db import get_db
from ..deps import require_unlocked
from ..models import Account, CategoryRule, Transaction
from ..schemas import CategoryRuleIn, CategoryUpdate, TransactionAnnotate, TransactionOut
from ..services import categorize

router = APIRouter(tags=["transactions"], dependencies=[Depends(require_unlocked)])


def normalize_tags(tags: list[str]) -> str:
    """Lowercase, trim, collapse whitespace, dedupe (order-preserving) -> stored CSV."""
    seen: list[str] = []
    for raw in tags:
        t = " ".join(raw.lower().replace(",", " ").split())
        if t and t not in seen:
            seen.append(t)
    return ",".join(seen)


@router.get("/transactions", response_model=list[TransactionOut])
def list_transactions(
    db: Session = Depends(get_db),
    account_id: int | None = None,
    category: str | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    tag: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Transaction]:
    stmt = select(Transaction).order_by(Transaction.posted_at.desc())
    if account_id is not None:
        stmt = stmt.where(Transaction.account_id == account_id)
    if category is not None:
        stmt = stmt.where(Transaction.category == category)
    if q:
        needle = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Transaction.payee).like(needle),
                func.lower(Transaction.description).like(needle),
                func.lower(Transaction.memo).like(needle),
                func.lower(Transaction.note).like(needle),
            )
        )
    if tag:
        # Tags are stored as "a,b,c"; match a whole tag, not a substring of one.
        stmt = stmt.where(
            ("," + Transaction.tags + ",").like(f"%,{tag.strip().lower()},%")
        )
    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt))


@router.patch("/transactions/{txn_id}", response_model=TransactionOut)
def annotate_transaction(
    txn_id: int, body: TransactionAnnotate, db: Session = Depends(get_db)
) -> Transaction:
    txn = db.get(Transaction, txn_id)
    if txn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    if body.note is not None:
        txn.note = body.note.strip() or None
    if body.tags is not None:
        txn.tags = normalize_tags(body.tags)
    db.commit()
    db.refresh(txn)
    return txn


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
        ["date", "account", "payee", "description", "amount", "currency", "category",
         "pending", "memo", "note", "tags"]
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
                _csv_text(t.note),
                t.tags,
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
