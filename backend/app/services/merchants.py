"""Per-merchant spending aggregates (where does the money actually go?).

Groups outflows by the same normalized merchant key recurring detection uses, over a
rolling window. Transfers/ATM are excluded via the user-perspective classifier.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Transaction
from ..schemas import MerchantSummary
from .insights import classify, effective_account_types
from .recurring import _merchant_key


def merchant_summaries(db: Session, days: int = 365, min_txns: int = 2) -> list[MerchantSummary]:
    start = datetime.now(timezone.utc) - timedelta(days=days)
    account_type = effective_account_types(db)

    groups: dict[str, list[tuple[Transaction, int]]] = defaultdict(list)
    for t in db.scalars(
        select(Transaction).where(Transaction.posted_at >= start, Transaction.pending.is_(False))
    ):
        _, outflow = classify(
            t.amount_minor, account_type.get(t.account_id, "depository"), t.category
        )
        if outflow <= 0:
            continue
        key = _merchant_key(t)
        if key:
            groups[key].append((t, outflow))

    window_months = days / 30.44
    results: list[MerchantSummary] = []
    for txns in groups.values():
        if len(txns) < min_txns:
            continue
        txns.sort(key=lambda pair: pair[0].posted_at)
        total = sum(outflow for _, outflow in txns)
        newest = txns[-1][0]
        # Average over the merchant's active span plus one typical visit interval —
        # first-to-last alone would count the first visit against zero elapsed time
        # (7 monthly rents span 6 months, not 7). Capped at the window; a merchant
        # first seen 2 months ago isn't diluted across 12.
        active_days = (txns[-1][0].posted_at - txns[0][0].posted_at).days
        avg_interval = active_days / (len(txns) - 1)
        months = max(min(window_months, (active_days + avg_interval) / 30.44), 1.0)
        category = Counter(t.category for t, _ in txns).most_common(1)[0][0]
        results.append(
            MerchantSummary(
                name=(newest.payee or newest.description or "")[:120],
                category=category,
                txn_count=len(txns),
                total_minor=total,
                avg_txn_minor=total // len(txns),
                monthly_avg_minor=int(total / months),
                last_date=newest.posted_at.date(),
            )
        )

    results.sort(key=lambda m: m.total_minor, reverse=True)
    return results
