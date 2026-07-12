"""Multi-account savings goals with deadline / on-track math."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_unlocked
from ..models import Account, Goal
from ..schemas import GoalIn, GoalOut

router = APIRouter(tags=["goals"], dependencies=[Depends(require_unlocked)])


def _linked_ids(goal: Goal) -> list[int]:
    return [int(x) for x in goal.account_ids.split(",") if x]


def _combined_balance(db: Session, ids: list[int]) -> int:
    if not ids:
        return 0
    accounts = db.scalars(select(Account).where(Account.id.in_(ids), Account.is_active.is_(True)))
    return sum(a.balance_minor for a in accounts)


def _to_out(db: Session, goal: Goal) -> GoalOut:
    ids = _linked_ids(goal)
    current = _combined_balance(db, ids)
    span = goal.target_minor - goal.start_minor
    progress = ((current - goal.start_minor) / span * 100) if span > 0 else 100.0
    progress = max(0.0, min(progress, 100.0)) if current < goal.target_minor else max(progress, 100.0)

    required_monthly: int | None = None
    on_track: bool | None = None
    if goal.target_date is not None:
        today = datetime.now(UTC).date()
        days_left = (goal.target_date - today).days
        remaining = max(0, goal.target_minor - current)
        required_monthly = int(remaining / max(days_left, 1) * 30.44) if remaining else 0
        total_days = max((goal.target_date - goal.created_at.date()).days, 1)
        elapsed_pct = min(max((total_days - days_left) / total_days * 100, 0), 100)
        on_track = progress >= elapsed_pct or current >= goal.target_minor

    return GoalOut(
        id=goal.id,
        name=goal.name,
        target_minor=goal.target_minor,
        target_date=goal.target_date,
        start_minor=goal.start_minor,
        account_ids=ids,
        created_at=goal.created_at,
        current_minor=current,
        progress_pct=round(progress, 1),
        required_monthly_minor=required_monthly,
        on_track=on_track,
    )


def _validate_accounts(db: Session, ids: list[int]) -> None:
    found = set(db.scalars(select(Account.id).where(Account.id.in_(ids))))
    missing = set(ids) - found
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown account id(s): {sorted(missing)}",
        )


@router.get("/goals", response_model=list[GoalOut])
def list_goals(db: Session = Depends(get_db)) -> list[GoalOut]:
    return [_to_out(db, g) for g in db.scalars(select(Goal).order_by(Goal.created_at))]


@router.post("/goals", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
def create_goal(body: GoalIn, db: Session = Depends(get_db)) -> GoalOut:
    _validate_accounts(db, body.account_ids)
    goal = Goal(
        name=body.name,
        target_minor=body.target_minor,
        target_date=body.target_date,
        # Baseline: progress counts money saved from now on, not pre-existing balance.
        start_minor=_combined_balance(db, body.account_ids),
        account_ids=",".join(str(i) for i in body.account_ids),
    )
    db.add(goal)
    db.commit()
    return _to_out(db, goal)


@router.patch("/goals/{goal_id}", response_model=GoalOut)
def update_goal(goal_id: int, body: GoalIn, db: Session = Depends(get_db)) -> GoalOut:
    goal = db.get(Goal, goal_id)
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    _validate_accounts(db, body.account_ids)
    goal.name = body.name
    goal.target_minor = body.target_minor
    goal.target_date = body.target_date
    goal.account_ids = ",".join(str(i) for i in body.account_ids)
    db.commit()
    return _to_out(db, goal)


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(goal_id: int, db: Session = Depends(get_db)) -> Response:
    goal = db.get(Goal, goal_id)
    if goal is not None:
        db.delete(goal)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
