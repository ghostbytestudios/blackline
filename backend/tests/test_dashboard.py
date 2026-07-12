"""Dashboard aggregates: KPI tiles and the cumulative day-of-month pace series."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.services.dashboard import build_dashboard

from .helpers import make_account, make_txn


def _days_into_month() -> int:
    return datetime.now(UTC).day


def test_empty_vault_gives_zeroes(db):
    s = build_dashboard(db)
    assert s.spent_today_minor == 0
    assert s.spent_mtd_minor == 0
    assert len(s.this_month) == _days_into_month()


def test_kpis_and_cumulative_series(db):
    acct = make_account(db)
    make_txn(db, acct, amount_minor=-5_000, days_ago=0, category="dining")
    make_txn(db, acct, amount_minor=-3_000, days_ago=1, category="groceries")
    make_txn(db, acct, amount_minor=260_000, days_ago=0, category="income")
    make_txn(db, acct, amount_minor=-99_000, days_ago=0, category="transfer")  # excluded
    make_txn(db, acct, amount_minor=-7_777, days_ago=0, category="dining", pending=True)  # excluded
    db.commit()

    s = build_dashboard(db)
    assert s.spent_today_minor == 5_000
    assert s.spent_yesterday_minor == 3_000
    assert s.income_mtd_minor == 260_000
    # Yesterday may fall in the previous month; MTD then only counts today.
    expected_mtd = 8_000 if _days_into_month() >= 2 else 5_000
    assert s.spent_mtd_minor == expected_mtd
    # The series is cumulative: the last point equals month-to-date spend.
    assert s.this_month[-1].cumulative_outflow_minor == expected_mtd
    assert s.this_month[-1].day == _days_into_month()


def test_last_month_series_covers_full_month(db):
    acct = make_account(db)
    today = datetime.now(UTC)
    mid_last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=15)
    make_txn(
        db, acct, amount_minor=-10_000,
        days_ago=(today - mid_last_month).days, category="shopping",
    )
    db.commit()

    s = build_dashboard(db)
    assert s.last_month[-1].cumulative_outflow_minor == 10_000
    assert s.last_month[14].cumulative_outflow_minor == 10_000  # day 15 onward
    assert s.last_month[13].cumulative_outflow_minor == 0  # day 14: not yet
    assert len(s.last_month) in (28, 29, 30, 31)


def test_liability_charges_count_as_spending(db):
    card = make_account(db, account_type="credit")
    make_txn(db, card, amount_minor=-2_500, days_ago=0, category="dining")
    make_txn(db, card, amount_minor=60_000, days_ago=0, category="transfer")  # payment
    db.commit()

    s = build_dashboard(db)
    assert s.spent_today_minor == 2_500
