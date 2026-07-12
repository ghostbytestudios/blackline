"""Internal transfer matching: link the two ledger legs of money moved between
your own accounts so it never counts as income or spending.

A candidate pair is: same absolute amount, opposite raw ledger signs, *different*
accounts, posted within ±2 days. Matching is greedy by closest date, each leg
pairs at most once, and matched legs get category "transfer" (only when the
category is auto-assigned — user-set categories are never touched, and
`recategorize_all` skips matched legs so rules can't undo a match).

Guards against false positives:
- Amounts under $1 are ignored.
- Income-categorized credits are never treated as the receiving leg (a paycheck
  arriving near an unrelated equal-sized payment shouldn't pair).
- Pending rows and split parents/children don't participate.

Runs after every sync and statement import, and on demand via the API.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Transaction

_WINDOW_DAYS = 2
_MIN_AMOUNT_MINOR = 100  # ignore sub-$1 noise


def match_transfers(db: Session, days: int = 90) -> int:
    """Pair unmatched transfer legs in the recent window. Returns pairs created.

    Flushes but does not commit — callers own the transaction.
    """
    start = datetime.now(UTC) - timedelta(days=days)
    candidates = [
        t
        for t in db.scalars(
            select(Transaction)
            .where(
                Transaction.posted_at >= start,
                Transaction.pending.is_(False),
                Transaction.transfer_peer_id.is_(None),
                Transaction.is_split_parent.is_(False),
                Transaction.parent_id.is_(None),
            )
            .order_by(Transaction.posted_at)
        )
        if abs(t.amount_minor) >= _MIN_AMOUNT_MINOR and t.category != "income"
    ]

    # Receiving legs indexed by amount; each may absorb one sending leg.
    credits_by_amount: dict[int, list[Transaction]] = {}
    for t in candidates:
        if t.amount_minor > 0:
            credits_by_amount.setdefault(t.amount_minor, []).append(t)

    pairs = 0
    for debit in candidates:
        if debit.amount_minor >= 0 or debit.transfer_peer_id is not None:
            continue
        pool = credits_by_amount.get(-debit.amount_minor, [])
        best: Transaction | None = None
        best_gap: int | None = None
        for credit in pool:
            if credit.transfer_peer_id is not None or credit.account_id == debit.account_id:
                continue
            gap = abs((credit.posted_at.date() - debit.posted_at.date()).days)
            if gap > _WINDOW_DAYS:
                continue
            if best_gap is None or gap < best_gap:
                best, best_gap = credit, gap
                if gap == 0:
                    break
        if best is None:
            continue
        debit.transfer_peer_id = best.id
        best.transfer_peer_id = debit.id
        for leg in (debit, best):
            if leg.category_source == "auto":
                leg.category = "transfer"
        pairs += 1

    if pairs:
        db.flush()
    return pairs
