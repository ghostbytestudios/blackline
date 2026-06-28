"""Accounts and holdings read endpoints, plus per-account user settings."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_unlocked
from ..models import Account, AccountSetting, Holding
from ..schemas import AccountOut, AccountSettingIn, HoldingOut, PortfolioSummary
from ..services import portfolio as portfolio_service

router = APIRouter(tags=["accounts"], dependencies=[Depends(require_unlocked)])

# Roles a user may assign. Asset-like vs liability-like is what insights cares about.
ALLOWED_TYPES = {
    "checking", "savings", "investment", "cash", "depository", "credit", "loan", "other",
}


def _to_out(account: Account, setting: AccountSetting | None) -> AccountOut:
    return AccountOut(
        id=account.id,
        name=account.name,
        org_name=account.org_name,
        account_type=(setting.type_override if setting and setting.type_override else account.account_type),
        type_override=setting.type_override if setting else None,
        currency=account.currency,
        balance_minor=account.balance_minor,
        available_minor=account.available_minor,
        balance_date=account.balance_date,
        is_active=account.is_active,
        goal_name=setting.goal_name if setting else None,
        goal_target_minor=setting.goal_target_minor if setting else None,
    )


def _settings_map(db: Session) -> dict[int, AccountSetting]:
    return {s.account_id: s for s in db.scalars(select(AccountSetting))}


@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(db: Session = Depends(get_db)) -> list[AccountOut]:
    settings = _settings_map(db)
    accounts = db.scalars(select(Account).order_by(Account.name))
    return [_to_out(a, settings.get(a.id)) for a in accounts]


@router.patch("/accounts/{account_id}/settings", response_model=AccountOut)
def update_settings(
    account_id: int, body: AccountSettingIn, db: Session = Depends(get_db)
) -> AccountOut:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    if body.type_override is not None and body.type_override not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid account type. Allowed: {sorted(ALLOWED_TYPES)}",
        )

    setting = db.scalar(select(AccountSetting).where(AccountSetting.account_id == account_id))
    if setting is None:
        setting = AccountSetting(account_id=account_id)
        db.add(setting)
    # Only overwrite fields that were provided (None means "leave unchanged").
    fields = body.model_dump(exclude_unset=True)
    for key, value in fields.items():
        setattr(setting, key, value)
    db.commit()
    db.refresh(setting)
    return _to_out(account, setting)


@router.get("/portfolio", response_model=PortfolioSummary)
def portfolio(db: Session = Depends(get_db)) -> PortfolioSummary:
    return portfolio_service.build_portfolio(db)


@router.get("/accounts/{account_id}/holdings", response_model=list[HoldingOut])
def list_holdings(account_id: int, db: Session = Depends(get_db)) -> list[Holding]:
    if db.get(Account, account_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return list(db.scalars(select(Holding).where(Holding.account_id == account_id)))
