"""Spending insights and trend analysis (computed locally over the SQLite store).

Cash-flow is computed from the *user's* perspective, not each account's raw ledger sign,
because liability accounts (loans, credit cards) sign transactions as balance changes:
a loan payment is a positive (debt-reducing) entry even though it is cash leaving you.

Classification rules (see `classify`):
  - Internal movement (transfer / atm) is excluded from both income and spending.
  - Asset accounts: positive = income, negative = spending.
  - Liability accounts: every non-transfer entry is spending from your wallet
    (loan interest, card purchases). Loan *principal* is categorized "transfer" and is
    therefore excluded — paying principal is net-worth-neutral, not income or expense.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Account, Transaction
from ..schemas import CategorySpend, InsightsSummary, MonthlyTrend

ASSET_TYPES = {"depository", "investment"}
# Internal money movement — neither income nor spending.
EXCLUDED_CATEGORIES = {"transfer", "atm"}


def classify(amount_minor: int, account_type: str, category: str) -> tuple[int, int]:
    """Return (inflow_minor, outflow_minor) from the user's cash-flow perspective."""
    if category in EXCLUDED_CATEGORIES:
        return 0, 0
    if account_type in ASSET_TYPES:
        return (amount_minor, 0) if amount_minor > 0 else (0, -amount_minor)
    # Liability account: non-transfer activity is money out of your pocket
    # (interest, card purchases). Principal payments are "transfer" and excluded above.
    return 0, abs(amount_minor)


def _net_worth_minor(db: Session) -> int:
    total = db.scalar(
        select(func.coalesce(func.sum(Account.balance_minor), 0)).where(Account.is_active.is_(True))
    )
    return int(total or 0)


def build_summary(db: Session, days: int = 90) -> InsightsSummary:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    account_type = {a.id: a.account_type for a in db.scalars(select(Account))}
    rows = list(
        db.scalars(
            select(Transaction).where(
                Transaction.posted_at >= start,
                Transaction.pending.is_(False),
            )
        )
    )

    total_inflow = 0
    total_outflow = 0
    cat_totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # [total, count]
    monthly: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # [inflow, outflow]

    for t in rows:
        at = account_type.get(t.account_id, "depository")
        inflow, outflow = classify(t.amount_minor, at, t.category)
        total_inflow += inflow
        total_outflow += outflow

        key = t.posted_at.strftime("%Y-%m")
        monthly[key][0] += inflow
        monthly[key][1] += outflow

        if outflow > 0:  # already excludes transfers/atm via classify
            cat_totals[t.category][0] += outflow
            cat_totals[t.category][1] += 1

    top = sorted(
        (CategorySpend(category=c, total_minor=v[0], txn_count=v[1]) for c, v in cat_totals.items()),
        key=lambda x: x.total_minor,
        reverse=True,
    )[:10]

    trends = [
        MonthlyTrend(month=m, inflow_minor=v[0], outflow_minor=v[1], net_minor=v[0] - v[1])
        for m, v in sorted(monthly.items())
    ]

    observations = _observations(top, trends, total_inflow, total_outflow)

    return InsightsSummary(
        range_start=start,
        range_end=end,
        total_inflow_minor=total_inflow,
        total_outflow_minor=total_outflow,
        net_minor=total_inflow - total_outflow,
        net_worth_minor=_net_worth_minor(db),
        top_categories=top,
        monthly_trends=trends,
        observations=observations,
    )


def _fmt(minor: int) -> str:
    return f"${minor / 100:,.2f}"


def _observations(
    top: list[CategorySpend], trends: list[MonthlyTrend], inflow: int, outflow: int
) -> list[str]:
    obs: list[str] = []

    if outflow > inflow and inflow > 0:
        obs.append(
            f"You spent more than you earned in this period "
            f"({_fmt(outflow)} out vs {_fmt(inflow)} in)."
        )
    elif inflow > 0:
        rate = (inflow - outflow) / inflow * 100
        obs.append(f"Your savings rate this period is about {rate:.0f}%.")

    if top:
        obs.append(f"Top spending category: {top[0].category} ({_fmt(top[0].total_minor)}).")

    if len(trends) >= 2:
        prev, last = trends[-2], trends[-1]
        if prev.outflow_minor > 0:
            change = (last.outflow_minor - prev.outflow_minor) / prev.outflow_minor * 100
            direction = "up" if change >= 0 else "down"
            obs.append(
                f"Spending is {direction} {abs(change):.0f}% vs last month "
                f"({_fmt(prev.outflow_minor)} → {_fmt(last.outflow_minor)})."
            )

    if not obs:
        obs.append("Not enough data yet — connect an account and sync to see insights.")
    return obs
