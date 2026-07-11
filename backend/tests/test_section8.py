"""Section 8: transfer matching, category rules manager, transaction splitting."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import CategoryRule, Transaction
from app.routers.transactions import (
    delete_rule,
    list_rules,
    split_transaction,
    unsplit_transaction,
)
from app.schemas import SplitPart, SplitRequest
from app.services import categorize
from app.services.budgets import monthly_category_spend
from app.services.insights import build_summary
from app.services.transfers import match_transfers

from .helpers import make_account, make_txn


def _days_ago(n: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=n)


# --- transfer matching --------------------------------------------------------


def test_transfer_pair_matched_and_categorized(db):
    checking = make_account(db, name="Checking")
    savings = make_account(db, name="Savings")
    out_leg = make_txn(db, checking, amount_minor=-50_000, days_ago=3, payee="ACH WITHDRAWAL")
    in_leg = make_txn(db, savings, amount_minor=50_000, days_ago=2, payee="ACH DEPOSIT")

    assert match_transfers(db) == 1
    assert out_leg.transfer_peer_id == in_leg.id
    assert in_leg.transfer_peer_id == out_leg.id
    assert out_leg.category == "transfer"
    assert in_leg.category == "transfer"


def test_no_match_same_account_or_wide_gap_or_diff_amount(db):
    a = make_account(db, name="A")
    b = make_account(db, name="B")
    # Same account: refund next to a purchase must not pair.
    make_txn(db, a, amount_minor=-2_000, days_ago=5)
    make_txn(db, a, amount_minor=2_000, days_ago=4)
    # Different accounts but 4 days apart (> window).
    make_txn(db, a, amount_minor=-7_500, days_ago=9)
    make_txn(db, b, amount_minor=7_500, days_ago=5)
    # Different amounts.
    make_txn(db, a, amount_minor=-3_000, days_ago=2)
    make_txn(db, b, amount_minor=3_100, days_ago=2)

    assert match_transfers(db) == 0


def test_income_leg_never_pairs(db):
    checking = make_account(db, name="Checking")
    other = make_account(db, name="Other")
    make_txn(db, other, amount_minor=-250_000, days_ago=1, payee="MORTGAGE PMT")
    make_txn(
        db, checking, amount_minor=250_000, days_ago=1, payee="PAYROLL", category="income"
    )
    assert match_transfers(db) == 0


def test_matching_is_idempotent_and_prefers_closest_date(db):
    a = make_account(db, name="A")
    b = make_account(db, name="B")
    debit = make_txn(db, a, amount_minor=-10_000, days_ago=3)
    far = make_txn(db, b, amount_minor=10_000, days_ago=5)
    near = make_txn(db, b, amount_minor=10_000, days_ago=3)

    assert match_transfers(db) == 1
    assert debit.transfer_peer_id == near.id
    assert far.transfer_peer_id is None
    # Re-running finds nothing new (the leftover credit has no partner).
    assert match_transfers(db) == 0


def test_user_set_category_survives_matching(db):
    a = make_account(db, name="A")
    b = make_account(db, name="B")
    debit = make_txn(db, a, amount_minor=-40_000, days_ago=1)
    debit.category = "housing"
    debit.category_source = "user"
    credit = make_txn(db, b, amount_minor=40_000, days_ago=1)
    db.flush()

    assert match_transfers(db) == 1
    assert debit.category == "housing"  # user choice untouched
    assert credit.category == "transfer"  # auto leg still normalized


def test_recategorize_all_preserves_matched_legs(db):
    a = make_account(db, name="A")
    b = make_account(db, name="B")
    debit = make_txn(db, a, amount_minor=-15_000, days_ago=1, payee="ZELLE TO SELF")
    make_txn(db, b, amount_minor=15_000, days_ago=1, payee="ZELLE FROM SELF")
    match_transfers(db)
    db.commit()

    categorize.recategorize_all(db)
    assert debit.category == "transfer"


# --- category rules manager ----------------------------------------------------


def test_list_rules_reports_first_match_counts(db):
    acct = make_account(db)
    make_txn(db, acct, amount_minor=-1_000, payee="STARBUCKS #1")
    make_txn(db, acct, amount_minor=-1_200, payee="STARBUCKS #2")
    make_txn(db, acct, amount_minor=-900, payee="PEETS COFFEE")
    db.add(CategoryRule(pattern="starbucks", category="dining", priority=50))
    db.add(CategoryRule(pattern="coffee", category="dining", priority=100))
    db.commit()

    rules = list_rules(db=db)
    by_pattern = {r.pattern: r for r in rules}
    assert by_pattern["starbucks"].match_count == 2
    # "coffee" only gets the txn the higher-priority rule didn't claim.
    assert by_pattern["coffee"].match_count == 1


def test_delete_rule_reverts_categories(db):
    acct = make_account(db)
    txn = make_txn(db, acct, amount_minor=-5_000, payee="SOME OBSCURE SHOP")
    db.add(CategoryRule(pattern="obscure shop", category="shopping"))
    db.commit()
    categorize.recategorize_all(db)
    assert txn.category == "shopping"

    rule = db.scalar(select(CategoryRule))
    result = delete_rule(rule.id, db=db)
    assert result["deleted"] == rule.id
    db.refresh(txn)
    assert txn.category == "uncategorized"


def test_delete_missing_rule_404s(db):
    with pytest.raises(HTTPException) as exc:
        delete_rule(999, db=db)
    assert exc.value.status_code == 404


# --- transaction splitting -------------------------------------------------------


def _split(db, txn, parts):
    return split_transaction(txn.id, SplitRequest(parts=parts), db=db)


def test_split_creates_children_and_flags_parent(db):
    acct = make_account(db)
    txn = make_txn(db, acct, amount_minor=-10_000, payee="COSTCO", category="shopping")
    rows = _split(
        db,
        txn,
        [
            SplitPart(category="groceries", amount_minor=-7_000),
            SplitPart(category="shopping", amount_minor=-3_000, note="new lamp"),
        ],
    )
    assert rows[0].id == txn.id and rows[0].is_split_parent
    children = rows[1:]
    assert [c.amount_minor for c in children] == [-7_000, -3_000]
    assert all(c.parent_id == txn.id for c in children)
    assert all(c.payee == "COSTCO" for c in children)
    assert children[1].note == "new lamp"


@pytest.mark.parametrize(
    "parts",
    [
        # Doesn't add up.
        [SplitPart(category="a", amount_minor=-5_000), SplitPart(category="b", amount_minor=-4_000)],
        # Wrong direction on one part.
        [SplitPart(category="a", amount_minor=-11_000), SplitPart(category="b", amount_minor=1_000)],
    ],
)
def test_split_validation_rejects_bad_parts(db, parts):
    acct = make_account(db)
    txn = make_txn(db, acct, amount_minor=-10_000)
    with pytest.raises(HTTPException) as exc:
        _split(db, txn, parts)
    assert exc.value.status_code == 422


def test_cannot_split_a_split_part(db):
    acct = make_account(db)
    txn = make_txn(db, acct, amount_minor=-10_000)
    rows = _split(
        db,
        txn,
        [SplitPart(category="a", amount_minor=-6_000), SplitPart(category="b", amount_minor=-4_000)],
    )
    child = rows[1]
    with pytest.raises(HTTPException) as exc:
        _split(db, child, [SplitPart(category="x", amount_minor=-3_000), SplitPart(category="y", amount_minor=-3_000)])
    assert exc.value.status_code == 422


def test_resplit_replaces_children(db):
    acct = make_account(db)
    txn = make_txn(db, acct, amount_minor=-10_000)
    _split(db, txn, [SplitPart(category="a", amount_minor=-5_000), SplitPart(category="b", amount_minor=-5_000)])
    _split(db, txn, [SplitPart(category="c", amount_minor=-9_000), SplitPart(category="d", amount_minor=-1_000)])
    children = list(db.scalars(select(Transaction).where(Transaction.parent_id == txn.id)))
    assert sorted(c.category for c in children) == ["c", "d"]
    assert len(children) == 2


def test_unsplit_restores_original(db):
    acct = make_account(db)
    txn = make_txn(db, acct, amount_minor=-10_000, category="shopping")
    _split(db, txn, [SplitPart(category="a", amount_minor=-6_000), SplitPart(category="b", amount_minor=-4_000)])
    restored = unsplit_transaction(txn.id, db=db)
    assert restored.is_split_parent is False
    assert restored.category == "shopping"
    assert db.scalar(select(Transaction).where(Transaction.parent_id == txn.id)) is None


def test_aggregations_count_children_not_parent(db):
    acct = make_account(db)
    txn = make_txn(db, acct, amount_minor=-10_000, days_ago=1, payee="COSTCO", category="shopping")
    _split(
        db,
        txn,
        [SplitPart(category="groceries", amount_minor=-7_000), SplitPart(category="shopping", amount_minor=-3_000)],
    )

    summary = build_summary(db, days=30)
    # Total spend is exactly the original $100 — no double counting.
    assert summary.total_outflow_minor == 10_000
    by_cat = {c.category: c.total_minor for c in summary.top_categories}
    assert by_cat == {"groceries": 7_000, "shopping": 3_000}

    month_key = datetime.now(timezone.utc).strftime("%Y-%m")
    spend = monthly_category_spend(db, months=1)
    assert spend[(month_key, "groceries")] == 7_000
    assert spend[(month_key, "shopping")] == 3_000
