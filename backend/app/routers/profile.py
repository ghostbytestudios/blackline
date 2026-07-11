"""User profile (income) for income-based budgeting guidance."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_unlocked
from ..models import Profile
from ..schemas import ProfileIn, ProfileOut
from ..services.insights import take_home_monthly_minor

router = APIRouter(tags=["profile"], dependencies=[Depends(require_unlocked)])


def _get_or_create(db: Session) -> Profile:
    profile = db.get(Profile, 1)
    if profile is None:
        profile = Profile(id=1, gross_annual_income_minor=0)
        db.add(profile)
        db.commit()
    return profile


def _to_out(db: Session, profile: Profile) -> ProfileOut:
    take_home, source = take_home_monthly_minor(db)
    return ProfileOut(
        gross_annual_income_minor=profile.gross_annual_income_minor,
        net_monthly_income_minor=profile.net_monthly_income_minor,
        take_home_monthly_minor=take_home,
        take_home_source=source,
    )


@router.get("/profile", response_model=ProfileOut)
def get_profile(db: Session = Depends(get_db)) -> ProfileOut:
    return _to_out(db, _get_or_create(db))


@router.put("/profile", response_model=ProfileOut)
def put_profile(body: ProfileIn, db: Session = Depends(get_db)) -> ProfileOut:
    profile = _get_or_create(db)
    fields = body.model_dump(exclude_unset=True)
    if fields.get("gross_annual_income_minor") is not None:
        profile.gross_annual_income_minor = fields["gross_annual_income_minor"]
    if "net_monthly_income_minor" in fields:  # explicit null clears the override
        profile.net_monthly_income_minor = fields["net_monthly_income_minor"]
    db.commit()
    db.refresh(profile)
    return _to_out(db, profile)
