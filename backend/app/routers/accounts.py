"""Accounts and holdings read endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_unlocked
from ..models import Account, Holding
from ..schemas import AccountOut, HoldingOut

router = APIRouter(tags=["accounts"], dependencies=[Depends(require_unlocked)])


@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(db: Session = Depends(get_db)) -> list[Account]:
    return list(db.scalars(select(Account).order_by(Account.name)))


@router.get("/accounts/{account_id}/holdings", response_model=list[HoldingOut])
def list_holdings(account_id: int, db: Session = Depends(get_db)) -> list[Holding]:
    if db.get(Account, account_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return list(db.scalars(select(Holding).where(Holding.account_id == account_id)))
