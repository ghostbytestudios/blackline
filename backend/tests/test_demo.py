"""Demo seeder: deterministic, realistic, guard-railed, fully removable."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.models import Account, Budget, NetWorthSnapshot, Transaction
from app.services import demo
from app.services.insights import build_insight_cards, build_summary
from app.services.recurring import detect_recurring

from .helpers import make_account


def test_seed_populates_a_full_household(db):
    counts = demo.seed(db)
    assert counts["accounts"] == 5
    assert counts["transactions"] > 200
    assert demo.has_demo_data(db) is True

    types = {a.account_type for a in db.scalars(select(Account))}
    assert types == {"depository", "credit", "investment", "loan"}


def test_seed_refuses_non_empty_vault(db):
    make_account(db, name="Real Account")
    db.commit()
    with pytest.raises(demo.DemoError):
        demo.seed(db)


def test_demo_data_feeds_recurring_detection(db):
    demo.seed(db)
    names = {r.name.lower() for r in detect_recurring(db)}
    # Fixed-price bills must be found; variable spend must not.
    assert any("netflix" in n for n in names)
    assert any("honda" in n or "auto loan" in n for n in names)
    assert not any("kroger" in n or "amazon" in n for n in names)


def test_demo_data_feeds_insights(db):
    demo.seed(db)
    summary = build_summary(db, days=90)
    assert summary.total_inflow_minor > 0
    assert summary.total_outflow_minor > 0
    assert len(summary.monthly_trends) >= 3
    assert len(build_insight_cards(db, days=180)) > 0


def test_seed_is_deterministic(db):
    counts = demo.seed(db)
    total = db.scalar(select(func.sum(Transaction.amount_minor)))
    demo.remove(db)
    counts2 = demo.seed(db)
    assert counts == counts2
    assert db.scalar(select(func.sum(Transaction.amount_minor))) == total


def test_remove_clears_everything(db):
    demo.seed(db)
    demo.remove(db)
    assert demo.has_demo_data(db) is False
    assert db.scalar(select(func.count(Account.id))) == 0
    assert db.scalar(select(func.count(Transaction.id))) == 0
    assert db.scalar(select(func.count(Budget.id))) == 0
    assert db.scalar(select(func.count(NetWorthSnapshot.id))) == 0
    # Removal returns the vault to a seedable state.
    demo.seed(db)
    assert demo.has_demo_data(db) is True
