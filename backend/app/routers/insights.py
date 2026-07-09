"""Insights and trends endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_unlocked
from sqlalchemy import select

from ..models import NetWorthSnapshot
from ..schemas import (
    DashboardSummary,
    InsightCard,
    InsightsSummary,
    NetWorthPoint,
    RecurringCharge,
)
from ..services import dashboard as dashboard_service
from ..services import insights as insights_service
from ..services import recurring as recurring_service

router = APIRouter(tags=["insights"], dependencies=[Depends(require_unlocked)])


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db)) -> DashboardSummary:
    return dashboard_service.build_dashboard(db)


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


@router.get("/recurring", response_model=list[RecurringCharge])
def recurring(db: Session = Depends(get_db)) -> list[RecurringCharge]:
    return recurring_service.detect_recurring(db)


@router.get("/networth/history", response_model=list[NetWorthPoint])
def networth_history(db: Session = Depends(get_db)) -> list[NetWorthSnapshot]:
    # Ensure today's point exists so the chart always reflects current balances.
    insights_service.record_snapshot(db)
    return list(db.scalars(select(NetWorthSnapshot).order_by(NetWorthSnapshot.as_of)))
