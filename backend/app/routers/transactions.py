"""Transaction listing, filtering, manual categorization, and CSV export."""

from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime, time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_unlocked
from ..models import Account, CategoryRule, Transaction
from ..schemas import (
    CategoryRuleIn,
    CategoryRuleOut,
    CategoryUpdate,
    SplitRequest,
    TransactionAnnotate,
    TransactionOut,
    TransferMatchResult,
)
from ..services import categorize
from ..services.transfers import match_transfers

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
        stmt = stmt.where(Transaction.posted_at >= datetime.combine(start, time.min, UTC))
    if end is not None:
        stmt = stmt.where(Transaction.posted_at <= datetime.combine(end, time.max, UTC))

    accounts = {a.id: a for a in db.scalars(select(Account))}
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(
        ["date", "account", "payee", "description", "amount", "currency", "category",
         "pending", "memo", "note", "tags", "split"]
    )
    for t in db.scalars(stmt):
        acct = accounts.get(t.account_id)
        # Split parents are exported for completeness but marked, so summing the
        # amount column without excluding them would double-count — flag it.
        split_marker = "parent" if t.is_split_parent else ("part" if t.parent_id else "")
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
                split_marker,
            ]
        )

    stamp = datetime.now(UTC).strftime("%Y-%m-%d")
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


@router.get("/rules", response_model=list[CategoryRuleOut])
def list_rules(db: Session = Depends(get_db)) -> list[CategoryRuleOut]:
    """All learned/user rules, with how many transactions each one currently decides.

    A transaction is credited to the first matching rule in priority order — the
    same order categorize uses — so the counts reflect actual effect, not overlap.
    """
    rules = list(
        db.scalars(select(CategoryRule).order_by(CategoryRule.priority.asc(), CategoryRule.id))
    )
    counts = {r.id: 0 for r in rules}
    if rules:
        for payee, description in db.execute(
            select(Transaction.payee, Transaction.description)
        ):
            combined = f"{(payee or '').lower()} {(description or '').lower()}"
            for r in rules:
                if r.pattern.lower() in combined:
                    counts[r.id] += 1
                    break
    return [
        CategoryRuleOut(
            id=r.id,
            pattern=r.pattern,
            category=r.category,
            priority=r.priority,
            created_at=r.created_at,
            match_count=counts[r.id],
        )
        for r in rules
    ]


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db)) -> dict:
    rule = db.get(CategoryRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    db.delete(rule)
    db.commit()
    # Re-run categorization so the deleted rule's effect actually reverts.
    changed = categorize.recategorize_all(db)
    return {"deleted": rule_id, "transactions_recategorized": changed}


@router.post("/transfers/match", response_model=TransferMatchResult)
def match_transfers_now(db: Session = Depends(get_db)) -> TransferMatchResult:
    """Scan recent history for unlinked internal-transfer pairs (also runs after
    every sync and import — this is the catch-up button for existing data)."""
    pairs = match_transfers(db, days=365)
    db.commit()
    return TransferMatchResult(pairs_matched=pairs)


@router.post("/transactions/{txn_id}/split", response_model=list[TransactionOut])
def split_transaction(
    txn_id: int, body: SplitRequest, db: Session = Depends(get_db)
) -> list[Transaction]:
    """Split one charge across categories. The original stays in the ledger (flagged,
    excluded from stats); child rows carry the money. Splitting again replaces the
    previous parts."""
    txn = db.get(Transaction, txn_id)
    if txn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    if txn.parent_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="This row is already part of a split — unsplit the original instead.",
        )
    if txn.pending:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Pending transactions can change; split after it posts.",
        )
    if any((p.amount_minor > 0) != (txn.amount_minor > 0) for p in body.parts):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Every part must have the same direction as the original transaction.",
        )
    if sum(p.amount_minor for p in body.parts) != txn.amount_minor:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Parts must add up exactly to the original amount.",
        )

    # Re-split: discard previous children first.
    for child in db.scalars(select(Transaction).where(Transaction.parent_id == txn.id)):
        db.delete(child)
    db.flush()

    children: list[Transaction] = []
    for i, part in enumerate(body.parts, start=1):
        child = Transaction(
            account_id=txn.account_id,
            external_id=f"{txn.external_id}::split-{i}",
            posted_at=txn.posted_at,
            amount_minor=part.amount_minor,
            description=txn.description,
            payee=txn.payee,
            memo=txn.memo,
            pending=False,
            category=part.category,
            category_source="user",  # a split is a deliberate categorization
            note=part.note,
            parent_id=txn.id,
        )
        db.add(child)
        children.append(child)
    txn.is_split_parent = True
    db.commit()
    for child in children:
        db.refresh(child)
    db.refresh(txn)
    return [txn, *children]


@router.delete("/transactions/{txn_id}/split", response_model=TransactionOut)
def unsplit_transaction(txn_id: int, db: Session = Depends(get_db)) -> Transaction:
    txn = db.get(Transaction, txn_id)
    if txn is None or not txn.is_split_parent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Split not found")
    for child in db.scalars(select(Transaction).where(Transaction.parent_id == txn.id)):
        db.delete(child)
    txn.is_split_parent = False
    db.commit()
    db.refresh(txn)
    return txn
