"""Cash-flow forecast: projected liquid balance over the coming weeks.

Scope is deliberately *liquid accounts only* (checking/savings/cash), using raw
ledger flows on those accounts:

- Scheduled events come from recurring streams detected on liquid accounts —
  bills and autopay debits (including transfers out to loans/cards, which really
  do drain cash) and recurring credits (payroll, interest). A transfer between
  two liquid accounts appears as both an outflow and an inflow stream and nets
  to zero, as it should.
- Everything non-recurring is modeled as a flat daily "discretionary" burn: the
  mean of the last 60 days of liquid debits that don't belong to a detected
  recurring merchant (this also absorbs variable card payments).
- Overdue streams (next date already passed) are assumed to land tomorrow.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account, Transaction
from ..schemas import ForecastPoint, ForecastSummary
from .insights import effective_account_types
from .recurring import _merchant_key, detect_streams

LIQUID_TYPES = {"depository", "checking", "savings", "cash"}
_DISCRETIONARY_WINDOW_DAYS = 60


def build_forecast(db: Session, days: int = 30) -> ForecastSummary:
    today = datetime.now(timezone.utc).date()
    horizon = today + timedelta(days=days)
    eff = effective_account_types(db)

    liquid_ids = {
        a.id
        for a in db.scalars(select(Account).where(Account.is_active.is_(True)))
        if eff.get(a.id) in LIQUID_TYPES
    }
    start_balance = sum(
        a.balance_minor
        for a in db.scalars(select(Account).where(Account.id.in_(liquid_ids or {0})))
    )

    out_streams = detect_streams(db, direction="out", account_ids=liquid_ids)
    in_streams = detect_streams(db, direction="in", account_ids=liquid_ids)
    recurring_keys = {s.merchant_key for s in out_streams}

    # Flat daily burn for everything the streams don't cover.
    window_start = datetime.now(timezone.utc) - timedelta(days=_DISCRETIONARY_WINDOW_DAYS)
    disc_total = 0
    for t in db.scalars(
        select(Transaction).where(
            Transaction.posted_at >= window_start,
            Transaction.pending.is_(False),
            Transaction.amount_minor < 0,
        )
    ):
        if t.account_id in liquid_ids and _merchant_key(t) not in recurring_keys:
            disc_total += -t.amount_minor
    discretionary_daily = disc_total // _DISCRETIONARY_WINDOW_DAYS

    # Scheduled events: project each stream forward through the horizon.
    events: dict[date, int] = defaultdict(int)
    expected_bills = expected_income = 0
    for streams, sign in ((out_streams, -1), (in_streams, +1)):
        for s in streams:
            step = timedelta(days=max(round(s.period_days), 1))
            d = max(s.charge.next_date, today + timedelta(days=1))  # overdue -> tomorrow
            while d <= horizon:
                events[d] += sign * s.charge.typical_amount_minor
                if sign < 0:
                    expected_bills += s.charge.typical_amount_minor
                else:
                    expected_income += s.charge.typical_amount_minor
                d += step

    balance = start_balance
    points: list[ForecastPoint] = []
    for i in range(1, days + 1):
        d = today + timedelta(days=i)
        balance += events.get(d, 0) - discretionary_daily
        points.append(ForecastPoint(date=d, balance_minor=int(balance)))

    return ForecastSummary(
        start_balance_minor=int(start_balance),
        end_balance_minor=points[-1].balance_minor if points else int(start_balance),
        expected_income_minor=expected_income,
        expected_bills_minor=expected_bills,
        discretionary_daily_minor=discretionary_daily,
        days=days,
        points=points,
    )
