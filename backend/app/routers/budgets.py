"""Monthly category budgets."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_unlocked
from ..models import Budget
from ..schemas import BudgetIn, BudgetStatus
from ..services import insights as insights_service

router = APIRouter(tags=["budgets"], dependencies=[Depends(require_unlocked)])


@router.get("/budgets", response_model=list[BudgetStatus])
def list_budgets(db: Session = Depends(get_db)) -> list[BudgetStatus]:
    spend = insights_service.current_month_category_spend(db)
    budgets = db.scalars(select(Budget).order_by(Budget.category)).all()
    return [
        BudgetStatus(category=b.category, limit_minor=b.limit_minor, spent_minor=spend.get(b.category, 0))
        for b in budgets
    ]


@router.put("/budgets", response_model=BudgetStatus)
def upsert_budget(body: BudgetIn, db: Session = Depends(get_db)) -> BudgetStatus:
    existing = db.scalar(select(Budget).where(Budget.category == body.category))
    if existing is None:
        db.add(Budget(category=body.category, limit_minor=body.limit_minor))
    else:
        existing.limit_minor = body.limit_minor
    db.commit()
    spend = insights_service.current_month_category_spend(db)
    return BudgetStatus(
        category=body.category, limit_minor=body.limit_minor, spent_minor=spend.get(body.category, 0)
    )


@router.delete("/budgets/{category}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(category: str, db: Session = Depends(get_db)) -> Response:
    db.execute(delete(Budget).where(Budget.category == category))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
