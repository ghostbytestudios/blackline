"""Monthly category budgets."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_unlocked
from ..models import Budget, Profile
from ..schemas import BudgetHistory, BudgetIn, BudgetStatus
from ..services import budgets as budgets_service
from ..services.insights import RECOMMENDED_ALLOCATION

router = APIRouter(tags=["budgets"], dependencies=[Depends(require_unlocked)])


@router.get("/budgets", response_model=list[BudgetStatus])
def list_budgets(db: Session = Depends(get_db)) -> list[BudgetStatus]:
    return budgets_service.budget_statuses(db)


@router.get("/budgets/history", response_model=list[BudgetHistory])
def history(db: Session = Depends(get_db), months: int = 6) -> list[BudgetHistory]:
    return budgets_service.budget_history(db, months=max(2, min(months, 24)))


@router.put("/budgets", response_model=BudgetStatus)
def upsert_budget(body: BudgetIn, db: Session = Depends(get_db)) -> BudgetStatus:
    existing = db.scalar(select(Budget).where(Budget.category == body.category))
    if existing is None:
        db.add(Budget(category=body.category, limit_minor=body.limit_minor, rollover=body.rollover))
    else:
        existing.limit_minor = body.limit_minor
        existing.rollover = body.rollover
    db.commit()
    status_by_cat = {s.category: s for s in budgets_service.budget_statuses(db)}
    return status_by_cat[body.category]


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
