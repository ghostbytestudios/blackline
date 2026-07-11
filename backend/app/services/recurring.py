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
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Transaction
from ..schemas import RecurringCharge
from .insights import LIABILITY_TYPES, effective_account_types


@dataclass
class Stream:
    """A detected recurring flow plus the internals the forecaster needs."""

    charge: RecurringCharge
    merchant_key: str
    period_days: float

# Categories that are never a recurring bill regardless of pattern. Income-labeled
# entries (payroll, card rewards, brokerage gain postings) are inflows to the user
# even when the provider signs them oddly — they are not bills.
_NEVER_RECURRING = {"atm", "income"}

# Below this, "recurring" is bookkeeping noise (penny interest/gain-loss postings),
# not a bill anyone budgets for. 99¢ subscriptions still clear it.
_MIN_TYPICAL_MINOR = 50

# (low, high) day ranges for each cadence label, with the representative period.
# Ranges are a little generous to tolerate weekend/billing-date drift.
_CADENCES = [
    ("weekly", 5, 10, 7),
    ("biweekly", 11, 18, 14),
    ("monthly", 24, 38, 30.44),
    ("quarterly", 80, 100, 91.3),
    ("yearly", 350, 385, 365),
]

# Categories whose label already declares "this is a recurring bill". The fixed-price
# test exists to filter variable *retail* — but usage-based subscriptions (API metering,
# seat changes) and utilities legitimately vary month to month, and the user/categorizer
# has already asserted what they are. Cadence regularity is still required.
_CATEGORY_ASSERTS_RECURRING = {"subscriptions", "utilities"}

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


_DIGIT_RUN = re.compile(r"\d{3,}")  # store/confirmation/phone numbers that vary per charge


def _merchant_key(t: Transaction) -> str:
    """Normalize a payee into a stable grouping key (lowercase, de-punctuated,
    long digit runs dropped — "NETFLIX 20260601" and "NETFLIX 20260701" must
    group as one merchant or nothing ever looks recurring)."""
    raw = (t.payee or t.description or "").lower()
    raw = _DIGIT_RUN.sub(" ", raw)
    return " ".join(_NORMALIZE.sub(" ", raw).split())


def _recurring_outflow(amount_minor: int, account_type: str, category: str) -> int:
    """Money leaving the user for *this* txn, for recurring-bill purposes (0 if N/A)."""
    if category in _NEVER_RECURRING:
        return 0
    # Nobody pays bills out of a brokerage; investment accounts only contribute
    # bookkeeping noise here (gain/loss postings, dividend sweeps, reinvestments).
    if account_type == "investment":
        return 0
    if account_type in LIABILITY_TYPES:
        # A real charge on a card (e.g. a subscription) is a debit; credits are
        # payments, refunds, or rewards — never a bill. Skip payment transfers too.
        if category == "transfer" or amount_minor >= 0:
            return 0
        return -amount_minor
    # Asset account: any debit counts, including autopay bills labeled "transfer".
    return -amount_minor if amount_minor < 0 else 0


def _recurring_inflow(amount_minor: int, account_type: str, category: str) -> int:
    """Recurring money arriving (payroll, interest, inbound transfers). Raw ledger
    credits on asset accounts only — liability credits are payments, not income."""
    if account_type in LIABILITY_TYPES:
        return 0
    return amount_minor if amount_minor > 0 else 0


def detect_streams(
    db: Session,
    days: int = 200,
    direction: str = "out",
    account_ids: set[int] | None = None,
) -> list[Stream]:
    start = datetime.now(timezone.utc) - timedelta(days=days)
    account_type = effective_account_types(db)
    flow = _recurring_outflow if direction == "out" else _recurring_inflow

    groups: dict[str, list[Transaction]] = defaultdict(list)
    for t in db.scalars(
        select(Transaction).where(
            Transaction.posted_at >= start,
            Transaction.pending.is_(False),
            Transaction.is_split_parent.is_(False),
        )
    ):
        if account_ids is not None and t.account_id not in account_ids:
            continue
        acct = account_type.get(t.account_id, "depository")
        if flow(t.amount_minor, acct, t.category) <= 0:
            continue
        key = _merchant_key(t)
        if key:
            groups[key].append(t)

    results: list[Stream] = []
    for key, txns in groups.items():
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
        label_asserts = (
            Counter(t.category for t in txns).most_common(1)[0][0]
            in _CATEGORY_ASSERTS_RECURRING
        )
        if not modal_ok and cv > _MAX_AMOUNT_CV and not label_asserts:
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
        if typical < _MIN_TYPICAL_MINOR:
            continue  # penny-level bookkeeping noise, not a bill
        monthly_estimate = int(typical * (30.44 / period))
        last_date = txns[-1].posted_at.date()
        next_date = last_date + timedelta(days=round(period))
        # A stream that has missed a full cycle is very likely canceled — don't
        # keep projecting it (one period of grace tolerates billing-date drift).
        if (datetime.now(timezone.utc).date() - next_date).days > period:
            continue
        charge = RecurringCharge(
            name=(txns[-1].payee or txns[-1].description or "")[:120],
            category=txns[-1].category,
            cadence=label,
            typical_amount_minor=typical,
            occurrences=len(txns),
            last_date=last_date,
            monthly_estimate_minor=monthly_estimate,
            next_date=next_date,
            days_until=(next_date - datetime.now(timezone.utc).date()).days,
        )
        results.append(Stream(charge=charge, merchant_key=key, period_days=period))

    results.sort(key=lambda s: s.charge.monthly_estimate_minor, reverse=True)
    return results


def detect_recurring(db: Session, days: int = 400) -> list[RecurringCharge]:
    # 400-day window: a yearly subscription needs two occurrences to establish its
    # cadence, which a ~6-month window can never see. (The forecaster keeps its own
    # shorter window — a 30-day cash projection doesn't need year-old history.)
    return [s.charge for s in detect_streams(db, days=days)]
