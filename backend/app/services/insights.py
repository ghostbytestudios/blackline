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
from ..schemas import CategorySpend, InsightCard, InsightsSummary, MonthlyTrend

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


def _usd(minor: float) -> str:
    return f"${minor / 100:,.0f}"


# Severity ordering for sorting (lower = more urgent).
_SEV_RANK = {"critical": 0, "warning": 1, "info": 2}


def build_insight_cards(db: Session, days: int = 180) -> list[InsightCard]:
    """Generate data-driven, severity-ranked insight cards from real activity.

    Every card is derived from the user's own transactions/balances — nothing is
    fabricated. Insights compare the current calendar month against prior months.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    account_type = {a.id: a.account_type for a in db.scalars(select(Account))}
    rows = list(
        db.scalars(
            select(Transaction).where(
                Transaction.posted_at >= start, Transaction.pending.is_(False)
            )
        )
    )

    monthly_in: dict[str, int] = defaultdict(int)
    monthly_out: dict[str, int] = defaultdict(int)
    cat_month: dict[tuple[str, str], int] = defaultdict(int)
    cat_driver: dict[tuple[str, str], tuple[int, str]] = {}  # (month,cat)->(amount, payee)

    for t in rows:
        inflow, outflow = classify(t.amount_minor, account_type.get(t.account_id, "depository"), t.category)
        m = t.posted_at.strftime("%Y-%m")
        monthly_in[m] += inflow
        monthly_out[m] += outflow
        if outflow > 0:
            cat_month[(m, t.category)] += outflow
            label = t.payee or t.description or t.category
            if (m, t.category) not in cat_driver or outflow > cat_driver[(m, t.category)][0]:
                cat_driver[(m, t.category)] = (outflow, label)

    months = sorted({m for m, _ in cat_month} | set(monthly_in) | set(monthly_out))
    if not months:
        return []
    now_month = end.strftime("%Y-%m")
    cur = now_month if now_month in months else months[-1]
    prior = [m for m in months if m < cur]

    cards: list[InsightCard] = []

    # 1) Category spending spikes vs the average of prior months that had that category.
    spikes: list[tuple[int, InsightCard]] = []
    for (m, cat), total in cat_month.items():
        if m != cur or cat in EXCLUDED_CATEGORIES or cat == "uncategorized":
            continue
        history = [cat_month[(pm, cat)] for pm in prior if (pm, cat) in cat_month]
        if not history:
            continue
        avg = sum(history) / len(history)
        # Require a meaningful category ($100+), a real jump (1.5x+), and $75+ over average
        # so we don't cry wolf over small categories.
        if avg <= 0 or total < 10_000 or total < 1.5 * avg or (total - avg) < 7_500:
            continue
        ratio = total / avg
        driver = cat_driver.get((cur, cat), (0, ""))[1]
        critical = ratio >= 2.0
        spikes.append(
            (
                total - int(avg),
                InsightCard(
                    id=f"spike-{cat}",
                    title=f"{cat.title()} Spending {'Spike' if critical else 'Rising'}",
                    detail=(
                        f"{cat.title()} this month ({_usd(total)}) is {ratio:.1f}x your recent "
                        f"average of {_usd(avg)}."
                        + (f" The {driver} charge drove the increase." if driver else "")
                    ),
                    severity="critical" if critical else "warning",
                    icon="trending-up",
                    action_label="View Spending",
                    action_route="/spending",
                ),
            )
        )
    spikes.sort(key=lambda x: x[0], reverse=True)
    cards.extend(c for _, c in spikes[:3])

    # 2) Savings rate this month.
    ci, co = monthly_in[cur], monthly_out[cur]
    if ci > 0:
        rate = (ci - co) / ci * 100
        if rate < 0:
            cards.append(
                InsightCard(
                    id="cashflow-negative",
                    title="Spending Exceeds Income",
                    detail=(
                        f"This month you spent {_usd(co)} against {_usd(ci)} of income — "
                        f"{_usd(co - ci)} more than you earned."
                    ),
                    severity="critical",
                    icon="trending-down",
                    action_label="View Spending",
                    action_route="/spending",
                )
            )
        elif rate < 5:
            cards.append(
                InsightCard(
                    id="savings-low",
                    title="Low Savings Rate",
                    detail=(
                        f"Your savings rate this month is {rate:.0f}%. Aiming for 15%+ builds a "
                        "healthier cushion."
                    ),
                    severity="warning",
                    icon="activity",
                    action_label="View Net Worth",
                    action_route="/net-worth",
                )
            )
        elif rate >= 15:
            cards.append(
                InsightCard(
                    id="savings-strong",
                    title="Strong Savings Rate",
                    detail=(
                        f"Your {rate:.0f}% savings rate this month is above the recommended 15%. "
                        "Consider directing the surplus to investments."
                    ),
                    severity="info",
                    icon="activity",
                    action_label="View Net Worth",
                    action_route="/net-worth",
                )
            )

    # 3) Idle cash sitting in a low-yield account.
    depository = [
        a for a in db.scalars(select(Account)) if a.account_type == "depository" and a.balance_minor > 0
    ]
    if depository:
        biggest = max(depository, key=lambda a: a.balance_minor)
        if biggest.balance_minor >= 500_000:  # >= $5,000
            potential = int(biggest.balance_minor * 0.04)
            cards.append(
                InsightCard(
                    id="idle-cash",
                    title="High-Yield Savings Opportunity",
                    detail=(
                        f"{biggest.name} holds {_usd(biggest.balance_minor)}. At ~4% APY that "
                        f"balance could earn about {_usd(potential)} per year."
                    ),
                    severity="info",
                    icon="piggy",
                    action_label="Review Accounts",
                    action_route="/accounts",
                )
            )

    # 4) Uncategorized nudge — better data, better insights.
    uncat = sum(c for (m, cat), c in cat_month.items() if m == cur and cat == "uncategorized")
    uncat_count = sum(
        1
        for t in rows
        if t.posted_at.strftime("%Y-%m") == cur and t.category == "uncategorized"
    )
    if uncat_count >= 8:
        cards.append(
            InsightCard(
                id="uncategorized",
                title="Uncategorized Transactions",
                detail=(
                    f"{uncat_count} transactions this month ({_usd(uncat)}) are uncategorized. "
                    "Categorizing them sharpens every insight here."
                ),
                severity="info",
                icon="shopping",
                action_label="Review Transactions",
                action_route="/transactions",
            )
        )

    cards.sort(key=lambda c: _SEV_RANK.get(c.severity, 9))
    return cards


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
