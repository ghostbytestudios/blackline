"""Budget status (with rollover) and month-by-month budget history."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Budget, Transaction
from ..schemas import BudgetHistory, BudgetMonth, BudgetStatus
from .insights import classify, effective_account_types


def _month_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def _months_back(n: int) -> list[str]:
    """The last n calendar months (oldest first), including the current one."""
    now = datetime.now(UTC)
    year, month = now.year, now.month
    out: list[str] = []
    for _ in range(n):
        out.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    return list(reversed(out))


def monthly_category_spend(db: Session, months: int) -> dict[tuple[str, str], int]:
    """(month, category) -> outflow, user cash-flow perspective, over the last N months."""
    start_month = _months_back(months)[0]
    start = datetime(int(start_month[:4]), int(start_month[5:7]), 1, tzinfo=UTC)
    account_type = effective_account_types(db)
    out: dict[tuple[str, str], int] = defaultdict(int)
    for t in db.scalars(
        select(Transaction).where(
            Transaction.posted_at >= start,
            Transaction.pending.is_(False),
            Transaction.is_split_parent.is_(False),
        )
    ):
        _, outflow = classify(t.amount_minor, account_type.get(t.account_id, "depository"), t.category)
        if outflow > 0:
            out[(_month_key(t.posted_at), t.category)] += outflow
    return out


def carryover_minor(limit_minor: int, prev_spent_minor: int | None) -> int:
    """Last month's unspent budget (positive) or overspend (negative), one month deep.

    Clamped to ±limit so a wild month can at most double or zero-out this month.
    """
    if prev_spent_minor is None:
        return 0
    return max(-limit_minor, min(limit_minor, limit_minor - prev_spent_minor))


def budget_statuses(db: Session) -> list[BudgetStatus]:
    spend = monthly_category_spend(db, months=2)
    this_month, prev_month = _months_back(2)[1], _months_back(2)[0]
    out: list[BudgetStatus] = []
    for b in db.scalars(select(Budget).order_by(Budget.category)):
        carry = (
            carryover_minor(b.limit_minor, spend.get((prev_month, b.category), 0))
            if b.rollover
            else 0
        )
        out.append(
            BudgetStatus(
                category=b.category,
                limit_minor=b.limit_minor,
                spent_minor=spend.get((this_month, b.category), 0),
                rollover=b.rollover,
                carryover_minor=carry,
                effective_limit_minor=max(0, b.limit_minor + carry),
            )
        )
    return out


def budget_history(db: Session, months: int = 6) -> list[BudgetHistory]:
    """Per budgeted category: the last N months of spend vs the current limit.

    Limits aren't versioned; history compares each month against the limit as it
    stands today (documented trade-off — good enough to answer "am I improving?").
    """
    month_keys = _months_back(months)
    spend = monthly_category_spend(db, months)
    out: list[BudgetHistory] = []
    for b in db.scalars(select(Budget).order_by(Budget.category)):
        rows = [
            BudgetMonth(
                month=m,
                spent_minor=spend.get((m, b.category), 0),
                limit_minor=b.limit_minor,
                over=spend.get((m, b.category), 0) > b.limit_minor,
            )
            for m in month_keys
        ]
        out.append(BudgetHistory(category=b.category, months=rows))
    return out
