"""Investment portfolio aggregation across all holdings."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account, Holding, PortfolioSnapshot
from ..schemas import PortfolioHolding, PortfolioSummary


def record_portfolio_snapshot(db: Session) -> None:
    """Upsert today's portfolio value/cost snapshot. Idempotent; no-op if no holdings."""
    totals = db.execute(
        select(Holding.market_value_minor, Holding.cost_basis_minor)
    ).all()
    if not totals:
        return
    value = sum(mv or 0 for mv, _ in totals)
    cost = sum(cb or 0 for _, cb in totals)
    today = datetime.now(UTC).date()
    snap = db.scalar(select(PortfolioSnapshot).where(PortfolioSnapshot.as_of == today))
    if snap is None:
        snap = PortfolioSnapshot(as_of=today)
        db.add(snap)
    snap.total_value_minor = int(value)
    snap.total_cost_minor = int(cost)
    db.commit()


def build_portfolio(db: Session) -> PortfolioSummary:
    account_name = {a.id: a.name for a in db.scalars(select(Account))}
    items: list[PortfolioHolding] = []
    total_value = 0
    total_cost = 0

    for h in db.scalars(select(Holding)):
        mv = h.market_value_minor or 0
        cb = h.cost_basis_minor or 0
        total_value += mv
        total_cost += cb
        gain = (mv - cb) if cb > 0 else None
        gain_pct = ((mv - cb) / cb * 100) if cb > 0 else None
        items.append(
            PortfolioHolding(
                id=h.id,
                account_id=h.account_id,
                account_name=account_name.get(h.account_id, "Account"),
                symbol=h.symbol,
                description=h.description,
                shares=h.shares,
                market_value_minor=h.market_value_minor,
                cost_basis_minor=h.cost_basis_minor,
                currency=h.currency,
                gain_minor=gain,
                gain_pct=gain_pct,
            )
        )

    items.sort(key=lambda x: x.market_value_minor or 0, reverse=True)
    total_gain = (total_value - total_cost) if total_cost > 0 else None
    gain_pct = ((total_value - total_cost) / total_cost * 100) if total_cost > 0 else None

    return PortfolioSummary(
        total_value_minor=total_value,
        total_cost_minor=total_cost,
        total_gain_minor=total_gain,
        gain_pct=gain_pct,
        holding_count=len(items),
        holdings=items,
    )
