"""Recurring charge / subscription detection.

Heuristic: group outflows by merchant; a group is "recurring" when it repeats at a
regular interval with consistent amounts. We deliberately require amount consistency so
variable merchants (e.g. Amazon, groceries) are not misflagged.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Transaction
from ..schemas import RecurringCharge
from .insights import EXCLUDED_CATEGORIES, classify, effective_account_types

# (low, high) day ranges for each cadence label, with the representative period.
_CADENCES = [
    ("weekly", 5, 9, 7),
    ("biweekly", 12, 16, 14),
    ("monthly", 26, 35, 30.44),
    ("quarterly", 84, 96, 91.3),
    ("yearly", 350, 380, 365),
]


def _cadence(median_interval: float) -> tuple[str, float] | None:
    for label, lo, hi, period in _CADENCES:
        if lo <= median_interval <= hi:
            return label, period
    return None


def detect_recurring(db: Session, days: int = 200) -> list[RecurringCharge]:
    start = datetime.now(timezone.utc) - timedelta(days=days)
    account_type = effective_account_types(db)

    groups: dict[str, list[Transaction]] = defaultdict(list)
    for t in db.scalars(
        select(Transaction).where(Transaction.posted_at >= start, Transaction.pending.is_(False))
    ):
        _, outflow = classify(t.amount_minor, account_type.get(t.account_id, "depository"), t.category)
        if outflow <= 0 or t.category in EXCLUDED_CATEGORIES:
            continue
        key = (t.payee or t.description or "").strip().lower()
        if key:
            groups[key].append(t)

    results: list[RecurringCharge] = []
    for key, txns in groups.items():
        if len(txns) < 3:
            continue
        txns.sort(key=lambda x: x.posted_at)
        amounts = [abs(t.amount_minor) for t in txns]
        mean_amt = statistics.mean(amounts)
        if mean_amt <= 0:
            continue
        # Amount consistency: skip merchants whose charges vary a lot.
        if statistics.pstdev(amounts) / mean_amt > 0.2:
            continue
        intervals = [
            (txns[i].posted_at - txns[i - 1].posted_at).days for i in range(1, len(txns))
        ]
        intervals = [d for d in intervals if d > 0]
        if not intervals:
            continue
        median_interval = statistics.median(intervals)
        cadence = _cadence(median_interval)
        if cadence is None:
            continue
        label, period = cadence
        # Interval regularity check.
        if statistics.pstdev(intervals) > median_interval * 0.5:
            continue

        typical = int(statistics.median(amounts))
        monthly_estimate = int(typical * (30.44 / period))
        results.append(
            RecurringCharge(
                name=(txns[-1].payee or txns[-1].description or key)[:120],
                category=txns[-1].category,
                cadence=label,
                typical_amount_minor=typical,
                occurrences=len(txns),
                last_date=txns[-1].posted_at.date(),
                monthly_estimate_minor=monthly_estimate,
            )
        )

    results.sort(key=lambda r: r.monthly_estimate_minor, reverse=True)
    return results
