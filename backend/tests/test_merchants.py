"""Per-merchant aggregation."""

from __future__ import annotations

from app.services.merchants import merchant_summaries

from .helpers import make_account, make_txn


def test_merchants_aggregate_and_sort(db):
    acct = make_account(db)
    for days, amt in ((5, -4_000), (12, -6_000), (30, -5_000)):
        make_txn(db, acct, amount_minor=amt, days_ago=days, payee="Kroger", category="groceries")
    for days, amt in ((3, -50_000), (40, -45_000)):
        make_txn(db, acct, amount_minor=amt, days_ago=days, payee="Amazon", category="shopping")
    make_txn(db, acct, amount_minor=-2_000, days_ago=2, payee="One Timer", category="dining")

    results = merchant_summaries(db)
    names = [m.name for m in results]
    assert names == ["Amazon", "Kroger"]  # sorted by total desc; one-timer filtered out
    amazon = results[0]
    assert amazon.total_minor == 95_000
    assert amazon.txn_count == 2
    assert amazon.category == "shopping"
    assert amazon.avg_txn_minor == 47_500


def test_monthly_average_matches_a_true_monthly_bill(db):
    """Seven monthly rent payments should average to ~the rent, not rent*7/6."""
    acct = make_account(db)
    for i in range(7):
        make_txn(db, acct, amount_minor=-165_000, days_ago=2 + i * 30, payee="Oakwood", category="housing")
    m = merchant_summaries(db)[0]
    assert abs(m.monthly_avg_minor - 165_000) < 8_000


def test_transfers_and_income_excluded(db):
    acct = make_account(db)
    for days in (5, 35):
        make_txn(db, acct, amount_minor=-60_000, days_ago=days, payee="Card Payment", category="transfer")
        make_txn(db, acct, amount_minor=260_000, days_ago=days, payee="Acme Payroll", category="income")
    assert merchant_summaries(db) == []


def test_merchant_key_groups_variants(db):
    acct = make_account(db)
    make_txn(db, acct, amount_minor=-1_000, days_ago=3, payee="Trader Joe's", category="groceries")
    make_txn(db, acct, amount_minor=-2_000, days_ago=9, payee="TRADER JOE'S", category="groceries")
    results = merchant_summaries(db)
    assert len(results) == 1
    assert results[0].txn_count == 2
