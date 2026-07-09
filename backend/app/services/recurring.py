"""Recurring charge / subscription detection.

Goal: surface real recurring *bills and subscriptions* (Netflix, insurance, car/loan
payments, utilities) while ignoring ordinary variable retail (Walmart, groceries,
restaurants).

The discriminator is a fixed price on a regular cadence:
  - A subscription/bill charges (nearly) the *same amount* every period.
  - Retail shopping varies basket to basket, so it is filtered out by the amount test.

We look at money actually leaving the user:
  - Asset accounts (checking/cash/savings): any debit, regardless of category, so that
    autopay bills the bank labels "transfer" (e.g. a car/loan payment) are included.
  - Liability accounts (credit cards): individual charges (a subscription billed to a
    card), but not principal/payment "transfer" entries.
  - ATM withdrawals are never recurring bills, so they are excluded.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Transaction
from ..schemas import RecurringCharge
from .insights import LIABILITY_TYPES, effective_account_types

# Categories that are never a recurring bill regardless of pattern.
_NEVER_RECURRING = {"atm"}

# (low, high) day ranges for each cadence label, with the representative period.
# Ranges are a little generous to tolerate weekend/billing-date drift.
_CADENCES = [
    ("weekly", 5, 10, 7),
    ("biweekly", 11, 18, 14),
    ("monthly", 24, 38, 30.44),
    ("quarterly", 80, 100, 91.3),
    ("yearly", 350, 385, 365),
]

# Minimum share of charges that must share the exact same amount for a group to look
# like a fixed-price subscription/bill (vs. variable retail).
_MODAL_AMOUNT_FRACTION = 0.5
# Fallback: allow tiny variation (tax/fx) even if not exactly modal.
_MAX_AMOUNT_CV = 0.05

_NORMALIZE = re.compile(r"[^a-z0-9 ]+")


def _cadence(median_interval: float) -> tuple[str, float] | None:
    for label, lo, hi, period in _CADENCES:
        if lo <= median_interval <= hi:
            return label, period
    return None


def _merchant_key(t: Transaction) -> str:
    """Normalize a payee into a stable grouping key (lowercase, de-punctuated)."""
    raw = (t.payee or t.description or "").lower()
    return _NORMALIZE.sub(" ", raw).strip()


def _recurring_outflow(amount_minor: int, account_type: str, category: str) -> int:
    """Money leaving the user for *this* txn, for recurring-bill purposes (0 if N/A)."""
    if category in _NEVER_RECURRING:
        return 0
    if account_type in LIABILITY_TYPES:
        # A real charge on a card (e.g. a subscription); skip principal/payment transfers.
        if category == "transfer":
            return 0
        return abs(amount_minor)
    # Asset account: any debit counts, including autopay bills labeled "transfer".
    return -amount_minor if amount_minor < 0 else 0


def detect_recurring(db: Session, days: int = 200) -> list[RecurringCharge]:
    start = datetime.now(timezone.utc) - timedelta(days=days)
    account_type = effective_account_types(db)

    groups: dict[str, list[Transaction]] = defaultdict(list)
    for t in db.scalars(
        select(Transaction).where(Transaction.posted_at >= start, Transaction.pending.is_(False))
    ):
        acct = account_type.get(t.account_id, "depository")
        if _recurring_outflow(t.amount_minor, acct, t.category) <= 0:
            continue
        key = _merchant_key(t)
        if key:
            groups[key].append(t)

    results: list[RecurringCharge] = []
    for txns in groups.values():
        # Need at least two charges to establish a cadence. Two is enough to catch a
        # monthly bill that only appears 2-3x in SimpleFIN's ~90-day window.
        if len(txns) < 2:
            continue
        txns.sort(key=lambda x: x.posted_at)
        amounts = [abs(t.amount_minor) for t in txns]
        mean_amt = statistics.mean(amounts)
        if mean_amt <= 0:
            continue

        # Fixed-price test: most charges share one exact *repeated* amount, or variance
        # is tiny. The modal test needs modal_count >= 2 — with two charges of different
        # amounts, "1 of 2" is not a mode, it's just two purchases at the same store.
        amount_counts = Counter(amounts)
        modal_amount, modal_count = amount_counts.most_common(1)[0]
        modal_fraction = modal_count / len(amounts)
        cv = statistics.pstdev(amounts) / mean_amt
        modal_ok = modal_count >= 2 and modal_fraction >= _MODAL_AMOUNT_FRACTION
        if not modal_ok and cv > _MAX_AMOUNT_CV:
            continue  # variable amounts -> retail, not a subscription/bill

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
        # Interval regularity (only meaningful with 3+ charges / 2+ intervals).
        if len(intervals) >= 2 and statistics.pstdev(intervals) > median_interval * 0.5:
            continue

        # The subscription price is the modal amount (falls back to median if no mode).
        typical = int(modal_amount if modal_count > 1 else statistics.median(amounts))
        monthly_estimate = int(typical * (30.44 / period))
        results.append(
            RecurringCharge(
                name=(txns[-1].payee or txns[-1].description or "")[:120],
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
