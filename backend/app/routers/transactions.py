"""Transaction listing, filtering, and manual categorization."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_unlocked
from ..models import CategoryRule, Transaction
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
