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
    ForecastSummary,
    InsightCard,
    InsightsSummary,
    MerchantSummary,
    NetWorthPoint,
    RecurringCharge,
)
from ..services import dashboard as dashboard_service
from ..services import forecast as forecast_service
from ..services import insights as insights_service
from ..services import merchants as merchants_service
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


@router.get("/forecast", response_model=ForecastSummary)
def forecast(
    db: Session = Depends(get_db),
    days: int = Query(default=30, ge=7, le=90),
) -> ForecastSummary:
    return forecast_service.build_forecast(db, days=days)


@router.get("/merchants", response_model=list[MerchantSummary])
def merchants(
    db: Session = Depends(get_db),
    days: int = Query(default=365, ge=30, le=730),
) -> list[MerchantSummary]:
    return merchants_service.merchant_summaries(db, days=days)


@router.get("/networth/history", response_model=list[NetWorthPoint])
def networth_history(db: Session = Depends(get_db)) -> list[NetWorthSnapshot]:
    # Ensure today's point exists so the chart always reflects current balances.
    insights_service.record_snapshot(db)
    return list(db.scalars(select(NetWorthSnapshot).order_by(NetWorthSnapshot.as_of)))
