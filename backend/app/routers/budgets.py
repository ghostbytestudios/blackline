"""Monthly category budgets."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_unlocked
from ..models import Budget, Profile
from ..schemas import BudgetIn, BudgetStatus
from ..services import insights as insights_service
from ..services.insights import RECOMMENDED_ALLOCATION

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


@router.post("/budgets/suggest", response_model=list[BudgetStatus])
def suggest_budgets(db: Session = Depends(get_db)) -> list[BudgetStatus]:
    """Create recommended budgets from gross income (50/30/20-style). Does not overwrite
    budgets you've already set."""
    profile = db.get(Profile, 1)
    gross = profile.gross_annual_income_minor if profile else 0
    if gross <= 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Set your gross annual income in Settings first.",
        )
    monthly = gross / 12
    existing = {b.category for b in db.scalars(select(Budget))}
    for category, fraction in RECOMMENDED_ALLOCATION.items():
        if category not in existing:
            db.add(Budget(category=category, limit_minor=round(monthly * fraction)))
    db.commit()
    return list_budgets(db)


@router.delete("/budgets/{category}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(category: str, db: Session = Depends(get_db)) -> Response:
    db.execute(delete(Budget).where(Budget.category == category))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
