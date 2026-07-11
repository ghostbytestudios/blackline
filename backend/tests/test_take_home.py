"""Take-home resolution: manual override > observed payroll > estimate from gross."""

from __future__ import annotations

from app.models import Profile
from app.services.insights import take_home_monthly_minor

from .helpers import make_account, make_txn


def _add_payroll(db, acct, *, amount=250_000, count=4, interval=14):
    for i in range(count):
        make_txn(db, acct, amount_minor=amount, days_ago=2 + i * interval,
                 payee="ACME CORP PAYROLL", category="income")


def test_no_data_resolves_none(db):
    amount, source = take_home_monthly_minor(db)
    assert (amount, source) == (0, "none")


def test_estimate_from_gross_when_nothing_observed(db):
    db.add(Profile(id=1, gross_annual_income_minor=9_600_000_00))  # $96k
    db.commit()
    amount, source = take_home_monthly_minor(db)
    assert source == "estimated"
    assert amount == 600_000_00  # 96k/12 * 0.75 = $6,000/mo


def test_observed_payroll_beats_estimate(db):
    db.add(Profile(id=1, gross_annual_income_minor=9_600_000_00))
    db.commit()
    acct = make_account(db)
    _add_payroll(db, acct)  # $2,500 biweekly ≈ $5,435/mo
    amount, source = take_home_monthly_minor(db)
    assert source == "observed"
    assert 530_000 <= amount <= 560_000


def test_manual_override_beats_everything(db):
    db.add(Profile(id=1, gross_annual_income_minor=9_600_000_00,
                   net_monthly_income_minor=512_345))
    db.commit()
    acct = make_account(db)
    _add_payroll(db, acct)
    amount, source = take_home_monthly_minor(db)
    assert (amount, source) == (512_345, "manual")


def test_inbound_transfers_do_not_count_as_take_home(db):
    """A monthly transfer from savings looks like recurring income to the stream
    detector, but its category says transfer — it must not inflate take-home."""
    checking = make_account(db, name="Checking")
    savings = make_account(db, name="Savings")
    for i in range(4):
        make_txn(db, checking, amount_minor=100_000, days_ago=2 + i * 30,
                 payee="FROM SAVINGS", category="transfer")
        make_txn(db, savings, amount_minor=-100_000, days_ago=2 + i * 30,
                 payee="TO CHECKING", category="transfer")
    amount, source = take_home_monthly_minor(db)
    assert (amount, source) == (0, "none")
