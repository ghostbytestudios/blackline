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

from ..models import Account, AccountSetting, Transaction
from ..schemas import CategorySpend, InsightCard, InsightsSummary, MonthlyTrend

# Only these are liabilities; everything else (depository, checking, savings, investment,
# cash, other, unknown) is treated as an asset for cash-flow classification.
LIABILITY_TYPES = {"credit", "loan"}
# Cash-like accounts where idle balances could move to a higher yield (savings excluded —
# it's presumably already chosen for yield).
LIQUID_CHECKING_TYPES = {"depository", "checking", "cash"}
# Internal money movement — neither income nor spending.
EXCLUDED_CATEGORIES = {"transfer", "atm"}

# 50/30/20 buckets for category spending.
NEEDS_CATEGORIES = {"housing", "utilities", "groceries", "transport", "insurance", "health"}
WANTS_CATEGORIES = {"dining", "entertainment", "shopping", "travel", "subscriptions"}
DEBT_CATEGORIES = {"loans", "interest"}  # debt service counts toward the 20% bucket

# Estimated take-home as a fraction of gross (used for the car/take-home guideline).
TAKE_HOME_FRACTION = 0.75

# Recommended monthly budget as a fraction of gross income (a 50/30/20-style starting point).
RECOMMENDED_ALLOCATION = {
    "housing": 0.30, "utilities": 0.08, "groceries": 0.10, "transport": 0.10,
    "insurance": 0.05, "health": 0.05,  # needs
    "dining": 0.06, "entertainment": 0.04, "shopping": 0.05, "travel": 0.03,
    "subscriptions": 0.02,  # wants
}


def classify(amount_minor: int, account_type: str, category: str) -> tuple[int, int]:
    """Return (inflow_minor, outflow_minor) from the user's cash-flow perspective."""
    if category in EXCLUDED_CATEGORIES:
        return 0, 0
    if account_type in LIABILITY_TYPES:
        # Non-transfer activity on a liability is money out of your pocket (interest, card
        # purchases). Principal payments are "transfer" and excluded above.
        return 0, abs(amount_minor)
    # Asset account: positive is income, negative is spending.
    return (amount_minor, 0) if amount_minor > 0 else (0, -amount_minor)


def effective_account_types(db: Session) -> dict[int, str]:
    """Map account id -> effective type, applying user role overrides over the auto type."""
    overrides = {
        s.account_id: s.type_override
        for s in db.scalars(select(AccountSetting))
        if s.type_override
    }
    return {a.id: overrides.get(a.id) or a.account_type for a in db.scalars(select(Account))}


def current_month_category_spend(db: Session) -> dict[str, int]:
    """Outflow per category for the current calendar month (user cash-flow view)."""
    now = datetime.now(timezone.utc)
    start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    account_type = effective_account_types(db)
    out: dict[str, int] = defaultdict(int)
    for t in db.scalars(
        select(Transaction).where(Transaction.posted_at >= start, Transaction.pending.is_(False))
    ):
        _, outflow = classify(t.amount_minor, account_type.get(t.account_id, "depository"), t.category)
        if outflow > 0:
            out[t.category] += outflow
    return out


def _net_worth_minor(db: Session) -> int:
    total = db.scalar(
        select(func.coalesce(func.sum(Account.balance_minor), 0)).where(Account.is_active.is_(True))
    )
    return int(total or 0)


def build_summary(db: Session, days: int = 90) -> InsightsSummary:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    account_type = effective_account_types(db)
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
    account_type = effective_account_types(db)
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

    # 3) Idle cash sitting in a low-yield checking account (savings is excluded —
    #    it's presumably already chosen for yield).
    eff_types = effective_account_types(db)
    liquid = [
        a
        for a in db.scalars(select(Account))
        if eff_types.get(a.id) in LIQUID_CHECKING_TYPES and a.balance_minor > 0
    ]
    if liquid:
        biggest = max(liquid, key=lambda a: a.balance_minor)
        if biggest.balance_minor >= 500_000:  # >= $5,000
            potential = int(biggest.balance_minor * 0.04)
            cards.append(
                InsightCard(
                    id="idle-cash",
                    title="High-Yield Savings Opportunity",
                    detail=(
                        f"{biggest.name} holds {_usd(biggest.balance_minor)} in checking. At ~4% "
                        f"APY that balance could earn about {_usd(potential)} per year."
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

    # 5) Budget alerts: over budget, or on track to exceed at the current pace.
    import calendar as _calendar

    from ..models import Budget

    budgets = {b.category: b.limit_minor for b in db.scalars(select(Budget)) if b.limit_minor > 0}
    if budgets and cur == now_month:
        days_in_month = _calendar.monthrange(end.year, end.month)[1]
        day = max(end.day, 1)
        for cat, limit in budgets.items():
            spent = cat_month.get((cur, cat), 0)
            if spent <= 0:
                continue
            pct = spent / limit * 100
            projected = spent / day * days_in_month
            if spent > limit:
                cards.append(
                    InsightCard(
                        id=f"budget-over-{cat}",
                        title=f"{cat.title()} Over Budget",
                        detail=(
                            f"You've spent {_usd(spent)} on {cat.title()} this month — "
                            f"{pct:.0f}% of your {_usd(limit)} budget, {_usd(spent - limit)} over."
                        ),
                        severity="critical",
                        icon="shopping",
                        action_label="View Spending",
                        action_route="/spending",
                    )
                )
            elif projected > limit * 1.05:
                cards.append(
                    InsightCard(
                        id=f"budget-pace-{cat}",
                        title=f"{cat.title()} Over Budget",
                        detail=(
                            f"You've spent {_usd(spent)} on {cat.title()} this month, "
                            f"{pct:.0f}% of your {_usd(limit)} budget. At this pace you're on "
                            f"track to exceed it by {_usd(projected - limit)}."
                        ),
                        severity="warning",
                        icon="shopping",
                        action_label="View Spending",
                        action_route="/spending",
                    )
                )

    # 6) Income-based guidance (50/30/20 and ratio rules) — only if income is set.
    from ..models import Profile

    profile = db.get(Profile, 1)
    gross_monthly = (profile.gross_annual_income_minor / 12) if profile else 0
    if gross_monthly > 0:
        cur_spend = {cat: cat_month.get((cur, cat), 0) for _, cat in cat_month if _ == cur}
        take_home = gross_monthly * TAKE_HOME_FRACTION

        # Housing <= 30% of gross.
        housing = cur_spend.get("housing", 0)
        if housing > 0:
            hp = housing / gross_monthly * 100
            if hp > 30:
                cards.append(
                    InsightCard(
                        id="guide-housing",
                        title="Housing Above 30% Guideline",
                        detail=(
                            f"Housing is {_usd(housing)}/mo — {hp:.0f}% of gross income. The common "
                            "guideline is 30% or less; trimming here frees up the most room."
                        ),
                        severity="critical" if hp > 40 else "warning",
                        icon="trending-up",
                        action_label="View Spending",
                        action_route="/spending",
                    )
                )

        # Car / transportation <= 10% of take-home.
        transport = cur_spend.get("transport", 0)
        if transport > 0 and take_home > 0:
            tp = transport / take_home * 100
            if tp > 10:
                cards.append(
                    InsightCard(
                        id="guide-transport",
                        title="Transportation Costs Above Guideline",
                        detail=(
                            f"Transportation is {_usd(transport)}/mo — {tp:.0f}% of estimated "
                            "take-home. Keeping total car costs near 10% leaves more for savings."
                        ),
                        severity="warning",
                        icon="trending-up",
                        action_label="View Transactions",
                        action_route="/transactions",
                    )
                )

        # Total debt payments <= 36% of gross (DTI), housing + loans + interest.
        debt = housing + sum(cur_spend.get(c, 0) for c in DEBT_CATEGORIES)
        if debt > 0:
            dti = debt / gross_monthly * 100
            if dti > 36:
                cards.append(
                    InsightCard(
                        id="guide-dti",
                        title="Debt-to-Income Above 36%",
                        detail=(
                            f"Housing + debt payments are {_usd(debt)}/mo — {dti:.0f}% of gross "
                            "income. Lenders flag a debt-to-income ratio above 36%."
                        ),
                        severity="critical" if dti > 43 else "warning",
                        icon="trending-up",
                        action_label="View Net Worth",
                        action_route="/net-worth",
                    )
                )

        # 50/30/20 reality check.
        needs = sum(cur_spend.get(c, 0) for c in NEEDS_CATEGORIES)
        wants = sum(cur_spend.get(c, 0) for c in WANTS_CATEGORIES)
        total_spend = monthly_out[cur]
        savings = gross_monthly - total_spend  # implied surplus (savings + leftover)
        np_, wp, sp = (
            needs / gross_monthly * 100,
            wants / gross_monthly * 100,
            savings / gross_monthly * 100,
        )
        off_track = np_ > 60 or wp > 40 or sp < 10
        cards.append(
            InsightCard(
                id="guide-503020",
                title="50/30/20 Check" + (" — Off Target" if off_track else ""),
                detail=(
                    f"This month: needs {np_:.0f}%, wants {wp:.0f}%, savings {sp:.0f}% of gross "
                    "income. The 50/30/20 starting point is 50% needs, 30% wants, 20% savings."
                ),
                severity="warning" if off_track else "info",
                icon="activity",
                action_label="View Spending",
                action_route="/spending",
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
