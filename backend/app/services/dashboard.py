"""Dashboard aggregates: day-level spending pace for the hero chart + KPI tiles.

The centerpiece is *cumulative outflow by day of month* for the current and previous
month, so the dashboard can answer "am I pacing ahead of or behind last month?" at a
glance. All flows use the user-perspective classification from `insights.classify`
(transfers excluded, liability signs normalized).
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Transaction
from ..schemas import DailyOutflowPoint, DashboardSummary
from .insights import classify, effective_account_types


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _prev_month_start(d: date) -> date:
    return (d.replace(day=1) - timedelta(days=1)).replace(day=1)


def _cumulative(daily: dict[int, int], through_day: int) -> list[DailyOutflowPoint]:
    total = 0
    out: list[DailyOutflowPoint] = []
    for day in range(1, through_day + 1):
        total += daily.get(day, 0)
        out.append(DailyOutflowPoint(day=day, cumulative_outflow_minor=total))
    return out


def build_dashboard(db: Session) -> DashboardSummary:
    today = datetime.now(timezone.utc).date()
    this_start = _month_start(today)
    prev_start = _prev_month_start(today)
    account_type = effective_account_types(db)

    rows = db.scalars(
        select(Transaction).where(
            Transaction.posted_at >= datetime.combine(prev_start, time.min, timezone.utc),
            Transaction.pending.is_(False),
        )
    )

    spent_today = spent_yesterday = spent_mtd = income_mtd = 0
    daily_this: dict[int, int] = {}
    daily_prev: dict[int, int] = {}
    yesterday = today - timedelta(days=1)

    for t in rows:
        inflow, outflow = classify(
            t.amount_minor, account_type.get(t.account_id, "depository"), t.category
        )
        if inflow == 0 and outflow == 0:
            continue
        d = t.posted_at.date()
        if d >= this_start:
            spent_mtd += outflow
            income_mtd += inflow
            if outflow:
                daily_this[d.day] = daily_this.get(d.day, 0) + outflow
            if d == today:
                spent_today += outflow
            elif d == yesterday:
                spent_yesterday += outflow
        elif d >= prev_start:
            if outflow:
                daily_prev[d.day] = daily_prev.get(d.day, 0) + outflow
            if d == yesterday:  # yesterday can fall in the previous month (on the 1st)
                spent_yesterday += outflow

    prev_days = calendar.monthrange(prev_start.year, prev_start.month)[1]
    return DashboardSummary(
        as_of=today,
        spent_today_minor=spent_today,
        spent_yesterday_minor=spent_yesterday,
        spent_mtd_minor=spent_mtd,
        income_mtd_minor=income_mtd,
        days_in_month=calendar.monthrange(today.year, today.month)[1],
        this_month=_cumulative(daily_this, today.day),
        last_month=_cumulative(daily_prev, prev_days),
    )
