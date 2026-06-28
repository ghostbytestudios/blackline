"""User profile (income) for income-based budgeting guidance."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_unlocked
from ..models import Profile
from ..schemas import ProfileIn, ProfileOut

router = APIRouter(tags=["profile"], dependencies=[Depends(require_unlocked)])


def _get_or_create(db: Session) -> Profile:
    profile = db.get(Profile, 1)
    if profile is None:
        profile = Profile(id=1, gross_annual_income_minor=0)
        db.add(profile)
        db.commit()
    return profile


@router.get("/profile", response_model=ProfileOut)
def get_profile(db: Session = Depends(get_db)) -> Profile:
    return _get_or_create(db)


@router.put("/profile", response_model=ProfileOut)
def put_profile(body: ProfileIn, db: Session = Depends(get_db)) -> Profile:
    profile = _get_or_create(db)
    profile.gross_annual_income_minor = body.gross_annual_income_minor
    db.commit()
    db.refresh(profile)
    return profile
