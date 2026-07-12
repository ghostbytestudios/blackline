"""Recurring detection: fixed price + regular cadence in, variable retail out."""

from __future__ import annotations

from app.services.recurring import detect_recurring

from .helpers import make_account, make_txn


def add_series(db, acct, *, amount, interval_days, count, payee, category="uncategorized", jitter=()):
    """Add `count` charges, newest `interval_days*0 .. oldest interval_days*(count-1)` ago."""
    for i in range(count):
        amt = amount if not jitter else amount + jitter[i % len(jitter)]
        make_txn(
            db, acct,
            amount_minor=amt,
            days_ago=2 + i * interval_days,
            payee=payee,
            description=payee.upper(),
            category=category,
        )


def test_monthly_subscription_detected(db):
    acct = make_account(db)
    add_series(db, acct, amount=-1549, interval_days=30, count=4, payee="Netflix", category="subscriptions")
    results = detect_recurring(db)
    assert len(results) == 1
    r = results[0]
    assert r.cadence == "monthly"
    assert r.typical_amount_minor == 1549
    assert r.occurrences == 4
    assert abs(r.monthly_estimate_minor - 1549) <= 25  # 30.44/30 normalization


def test_variable_retail_rejected(db):
    """Same store, same cadence, but varying basket sizes -> not a bill."""
    acct = make_account(db)
    for i, amt in enumerate([-4312, -9877, -2210, -15641]):
        make_txn(db, acct, amount_minor=amt, days_ago=2 + i * 30, payee="Walmart", category="shopping")
    assert detect_recurring(db) == []


def test_small_fixed_price_drift_tolerated(db):
    """Tax/fx wobble under 5% CV still counts as a fixed-price bill."""
    acct = make_account(db)
    add_series(db, acct, amount=-10000, interval_days=30, count=4, payee="Geico", jitter=(0, 150, -150, 100))
    results = detect_recurring(db)
    assert len(results) == 1


def test_atm_never_recurring(db):
    acct = make_account(db)
    add_series(db, acct, amount=-4000, interval_days=7, count=6, payee="ATM Withdrawal", category="atm")
    assert detect_recurring(db) == []


def test_biweekly_cadence_labeled(db):
    acct = make_account(db)
    add_series(db, acct, amount=-2500, interval_days=14, count=5, payee="Planet Fitness", category="health")
    results = detect_recurring(db)
    assert len(results) == 1
    assert results[0].cadence == "biweekly"
    # ~2.17 charges per month
    assert 5200 <= results[0].monthly_estimate_minor <= 5700


def test_card_subscription_detected_but_card_payment_excluded(db):
    card = make_account(db, name="Visa", account_type="credit")
    # Real subscription charged to the card (negative on the card ledger).
    add_series(db, card, amount=-1199, interval_days=30, count=4, payee="Spotify", category="subscriptions")
    # Monthly payment toward the card: category transfer -> excluded.
    add_series(db, card, amount=60000, interval_days=30, count=4, payee="Payment Thank You", category="transfer")
    results = detect_recurring(db)
    assert [r.name for r in results] == ["Spotify"]


def test_checking_autopay_transfer_included(db):
    """A fixed car payment the bank labels 'transfer' still leaves the wallet monthly."""
    acct = make_account(db)
    add_series(db, acct, amount=-38500, interval_days=30, count=4, payee="Honda Financial", category="transfer")
    results = detect_recurring(db)
    assert len(results) == 1
    assert results[0].typical_amount_minor == 38500


def test_two_occurrences_enough_for_monthly(db):
    acct = make_account(db)
    add_series(db, acct, amount=-999, interval_days=31, count=2, payee="Hulu", category="subscriptions")
    results = detect_recurring(db)
    assert len(results) == 1


def test_next_due_projection(db):
    """next_date = last charge + cadence period; days_until counts from today."""
    acct = make_account(db)
    add_series(db, acct, amount=-1549, interval_days=30, count=3, payee="Netflix", category="subscriptions")
    r = detect_recurring(db)[0]
    assert (r.next_date - r.last_date).days == 30
    # Last charge was 2 days ago (add_series newest offset), so ~28 days out.
    assert 26 <= r.days_until <= 30


def test_two_differing_amounts_not_a_bill(db):
    """Two purchases at the same store a month apart, ~12% apart in price, are just
    shopping — '1 of 2 amounts' must not count as a mode."""
    acct = make_account(db)
    make_txn(db, acct, amount_minor=-24_999, days_ago=35, payee="Best Buy", category="shopping")
    make_txn(db, acct, amount_minor=-22_100, days_ago=4, payee="Best Buy", category="shopping")
    assert detect_recurring(db) == []


def test_irregular_intervals_rejected(db):
    acct = make_account(db)
    for days in (2, 5, 40, 45):
        make_txn(db, acct, amount_minor=-5000, days_ago=days, payee="Rando Shop")
    assert detect_recurring(db) == []


def test_investment_account_noise_never_recurring(db):
    """Brokerage bookkeeping (gain/loss postings, sweeps) is not a bill."""
    brokerage = make_account(db, name="Brokerage", account_type="investment")
    add_series(db, brokerage, amount=-1, interval_days=30, count=5,
               payee="Realizedgainloss", category="interest")
    add_series(db, brokerage, amount=-52_000, interval_days=30, count=4,
               payee="Sweep to Money Market", category="uncategorized")
    assert detect_recurring(db) == []


def test_penny_noise_dropped_but_99_cent_sub_kept(db):
    acct = make_account(db)
    add_series(db, acct, amount=-1, interval_days=30, count=5,
               payee="Interest Adjustment", category="interest")
    add_series(db, acct, amount=-99, interval_days=30, count=4,
               payee="Apple iCloud", category="subscriptions")
    results = detect_recurring(db)
    assert [r.name for r in results] == ["Apple iCloud"]


def test_income_labeled_entries_never_recurring(db):
    """Monthly card rewards / income-labeled postings are inflows, not bills."""
    card = make_account(db, name="Visa", account_type="credit")
    add_series(db, card, amount=2_500, interval_days=30, count=4,
               payee="Cash Rewards", category="income")
    checking = make_account(db, name="Checking")
    add_series(db, checking, amount=-2_500, interval_days=30, count=4,
               payee="Round-Up Bonus", category="income")
    assert detect_recurring(db) == []


def test_liability_credits_never_recurring(db):
    """Refunds/rewards credited to a card are not charges, whatever the category."""
    card = make_account(db, name="Visa", account_type="credit")
    add_series(db, card, amount=1_599, interval_days=30, count=4,
               payee="Statement Credit", category="uncategorized")
    assert detect_recurring(db) == []


def test_varying_reference_numbers_still_group(db):
    """Providers append confirmation/store numbers that change every charge —
    the merchant key must ignore them or nothing ever repeats."""
    acct = make_account(db)
    for i in range(4):
        make_txn(db, acct, amount_minor=-1549, days_ago=2 + i * 30,
                 payee=f"NETFLIX.COM 86637127{i}53", description=f"NETFLIX REF 202600{i}17742",
                 category="subscriptions")
    # payee and description carry reference numbers that differ on every charge
    results = detect_recurring(db)
    assert len(results) == 1
    assert results[0].occurrences == 4


def test_canceled_subscription_stops_projecting(db):
    """A monthly sub last seen 4 months ago has missed cycles — don't project it."""
    acct = make_account(db)
    add_series(db, acct, amount=-1549, interval_days=30, count=4, payee="Old Gym")
    # Shift the whole series back 120 days: newest charge is ~4 months old.
    from datetime import timedelta

    from sqlalchemy import select

    from app.models import Transaction
    for t in db.scalars(select(Transaction)):
        t.posted_at = t.posted_at - timedelta(days=120)
    db.flush()
    assert detect_recurring(db) == []


def test_variable_amount_subscription_detected_when_labeled(db):
    """Usage-based subscriptions (e.g. Anthropic API) vary monthly — the
    'subscriptions' label overrides the fixed-price retail filter."""
    acct = make_account(db)
    for i, amt in enumerate([-2314, -4102, -1755, -2890]):
        make_txn(db, acct, amount_minor=amt, days_ago=2 + i * 30,
                 payee="Anthropic", category="subscriptions")
    results = detect_recurring(db)
    assert len(results) == 1
    assert results[0].cadence == "monthly"
    # Typical price falls back to the median when there's no repeated amount.
    assert results[0].typical_amount_minor == 2602


def test_variable_utility_bill_detected(db):
    """A real electric bill differs every month but is still a recurring bill."""
    acct = make_account(db)
    for i, amt in enumerate([-14428, -9862, -11251, -16704]):
        make_txn(db, acct, amount_minor=amt, days_ago=2 + i * 30,
                 payee="Dominion Energy", category="utilities")
    assert len(detect_recurring(db)) == 1


def test_variable_shopping_still_rejected_despite_cadence(db):
    """The label override must not weaken the retail filter for other categories."""
    acct = make_account(db)
    for i, amt in enumerate([-4312, -9877, -2210, -15641]):
        make_txn(db, acct, amount_minor=amt, days_ago=2 + i * 30,
                 payee="Target", category="shopping")
    assert detect_recurring(db) == []


def test_yearly_subscription_detected_in_wide_window(db):
    acct = make_account(db)
    add_series(db, acct, amount=-9_900, interval_days=365, count=2,
               payee="Amazon Prime Annual", category="subscriptions")
    results = detect_recurring(db)
    assert len(results) == 1
    assert results[0].cadence == "yearly"
