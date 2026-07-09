"""Demo/sandbox mode: load or remove deterministic fake data."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_unlocked
from ..security import vault
from ..services import demo

router = APIRouter(tags=["demo"], dependencies=[Depends(require_unlocked)])


@router.post("/demo/seed")
def seed_demo(db: Session = Depends(get_db)) -> dict:
    """Load the demo household. Only into an empty, unconnected vault — demo data
    must never mingle with real financial data."""
    if vault.has_secret(db, vault.SIMPLEFIN_ACCESS_URL):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A bank connection exists. Demo data only loads into an empty vault.",
        )
    try:
        return demo.seed(db)
    except demo.DemoError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/demo")
def remove_demo(db: Session = Depends(get_db)) -> dict:
    if not demo.has_demo_data(db):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No demo data to remove."
        )
    return demo.remove(db)
