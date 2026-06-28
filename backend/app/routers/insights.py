"""Insights and trends endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_unlocked
from ..schemas import InsightsSummary
from ..services import insights as insights_service

router = APIRouter(tags=["insights"], dependencies=[Depends(require_unlocked)])


@router.get("/insights/summary", response_model=InsightsSummary)
def summary(
    db: Session = Depends(get_db),
    days: int = Query(default=90, ge=7, le=730),
) -> InsightsSummary:
    return insights_service.build_summary(db, days=days)
