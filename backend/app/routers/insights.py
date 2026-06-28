"""Insights and trends endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_unlocked
from ..models import NetWorthSnapshot
from ..schemas import InsightCard, InsightsSummary, NetWorthPoint
from ..services import insights as insights_service
from sqlalchemy import select

router = APIRouter(tags=["insights"], dependencies=[Depends(require_unlocked)])


@router.get("/insights/summary", response_model=InsightsSummary)
def summary(
    db: Session = Depends(get_db),
    days: int = Query(default=90, ge=7, le=730),
) -> InsightsSummary:
    return insights_service.build_summary(db, days=days)


@router.get("/insights/cards", response_model=list[InsightCard])
def cards(
    db: Session = Depends(get_db),
    days: int = Query(default=180, ge=30, le=730),
) -> list[InsightCard]:
    return insights_service.build_insight_cards(db, days=days)


@router.get("/networth/history", response_model=list[NetWorthPoint])
def networth_history(db: Session = Depends(get_db)) -> list[NetWorthSnapshot]:
    # Ensure today's point exists so the chart always reflects current balances.
    insights_service.record_snapshot(db)
    return list(db.scalars(select(NetWorthSnapshot).order_by(NetWorthSnapshot.as_of)))
