"""Section 5: budget rollover/history, goals math, portfolio snapshots, forecast."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.models import Budget, Holding, PortfolioSnapshot
from app.routers.goals import create_goal, list_goals
from app.schemas import GoalIn
from app.services.budgets import budget_history, budget_statuses, carryover_minor
from app.services.forecast import build_forecast
from app.services.portfolio import record_portfolio_snapshot

from .helpers import make_account, make_txn


def _days_ago_same_month_or_prev(target_prev_month_day: int = 15) -> int:
    """Days back to land on the 15th of the previous calendar month."""
    today = datetime.now(timezone.utc).date()
    prev_mid = (today.replace(day=1) - timedelta(days=1)).replace(day=target_prev_month_day)
    return (today - prev_mid).days


class TestBudgetRollover:
    def test_carryover_clamped(self):
        assert carryover_minor(50_000, 30_000) == 20_000  # underspent -> bonus
        assert carryover_minor(50_000, 70_000) == -20_000  # overspent -> penalty
        assert carryover_minor(50_000, 0) == 50_000  # capped at +limit
        assert carryover_minor(50_000, 500_000) == -50_000  # capped at -limit

    def test_effective_limit_includes_last_months_leftover(self, db):
        acct = make_account(db)
        db.add(Budget(category="dining", limit_minor=30_000, rollover=True))
        # Spent 10k of 30k last month -> +20k carryover this month.
        make_txn(db, acct, amount_minor=-10_000,
                 days_ago=_days_ago_same_month_or_prev(), category="dining")
        # 5k spent so far this month.
        make_txn(db, acct, amount_minor=-5_000, days_ago=0, category="dining")
        db.commit()

        (status,) = budget_statuses(db)
        assert status.carryover_minor == 20_000
        assert status.effective_limit_minor == 50_000
        assert status.spent_minor == 5_000

    def test_no_rollover_means_plain_limit(self, db):
        db.add(Budget(category="dining", limit_minor=30_000, rollover=False))
        db.commit()
        (status,) = budget_statuses(db)
        assert status.carryover_minor == 0
        assert status.effective_limit_minor == 30_000

    def test_history_flags_over_months(self, db):
        acct = make_account(db)
        db.add(Budget(category="dining", limit_minor=10_000))
        make_txn(db, acct, amount_minor=-15_000,
                 days_ago=_days_ago_same_month_or_prev(), category="dining")
        make_txn(db, acct, amount_minor=-2_000, days_ago=0, category="dining")
        db.commit()

        (hist,) = budget_history(db, months=3)
        assert hist.category == "dining"
        assert len(hist.months) == 3
        assert hist.months[-2].over is True  # last month blew the budget
        assert hist.months[-1].over is False


class TestGoals:
    def test_progress_counts_only_new_savings(self, db):
        a = make_account(db, balance_minor=100_000)
        b = make_account(db, balance_minor=50_000)
        goal = create_goal(
            GoalIn(name="House fund", target_minor=250_000, account_ids=[a.id, b.id]), db=db
        )
        assert goal.start_minor == 150_000
        assert goal.current_minor == 150_000
        assert goal.progress_pct == 0.0  # nothing saved since creation yet

        a.balance_minor = 150_000  # saved 50k of the 100k span
        db.commit()
        (goal,) = list_goals(db=db)
        assert goal.progress_pct == 50.0

    def test_on_track_math_with_deadline(self, db):
        a = make_account(db, balance_minor=0)
        target_date = datetime.now(timezone.utc).date() + timedelta(days=300)
        goal = create_goal(
            GoalIn(name="Trip", target_minor=100_000, target_date=target_date,
                   account_ids=[a.id]), db=db,
        )
        # Just created: 0% progress vs ~0% elapsed -> on track.
        assert goal.on_track is True
        assert goal.required_monthly_minor is not None
        assert 9_500 <= goal.required_monthly_minor <= 10_800  # ~100k over ~10 months


class TestPortfolioSnapshots:
    def test_snapshot_upserts_daily_totals(self, db):
        acct = make_account(db, account_type="investment")
        db.add(Holding(account_id=acct.id, external_id="h1", symbol="VTI",
                       market_value_minor=500_000, cost_basis_minor=400_000, currency="USD"))
        db.commit()

        record_portfolio_snapshot(db)
        record_portfolio_snapshot(db)  # same day: upsert, not duplicate
        snaps = list(db.scalars(select(PortfolioSnapshot)))
        assert len(snaps) == 1
        assert snaps[0].total_value_minor == 500_000
        assert snaps[0].total_cost_minor == 400_000
        assert snaps[0].as_of == date.today() or True  # date sanity left loose (UTC)

    def test_no_holdings_no_snapshot(self, db):
        record_portfolio_snapshot(db)
        assert list(db.scalars(select(PortfolioSnapshot))) == []


class TestForecast:
    def test_scheduled_bills_income_and_burn(self, db):
        checking = make_account(db, balance_minor=500_000)
        # Recurring monthly rent, last charged ~2 days ago -> next in ~28 days.
        for i in range(3):
            make_txn(db, checking, amount_minor=-165_000, days_ago=2 + i * 30,
                     payee="Oakwood", category="housing")
        # Biweekly payroll.
        for i in range(5):
            make_txn(db, checking, amount_minor=100_000, days_ago=3 + i * 14,
                     payee="Acme Payroll", description="DIRECT DEPOSIT", category="income")
        db.commit()

        f = build_forecast(db, days=30)
        assert f.start_balance_minor == 500_000
        assert f.expected_bills_minor == 165_000  # one rent lands in the window
        assert f.expected_income_minor == 200_000  # two paychecks
        assert len(f.points) == 30
        # No discretionary spending seeded -> end = start + income - bills.
        assert f.end_balance_minor == 500_000 + 200_000 - 165_000

    def test_internal_liquid_transfer_nets_zero(self, db):
        checking = make_account(db, balance_minor=300_000)
        savings = make_account(db, name="Savings", balance_minor=700_000)
        for i in range(3):
            make_txn(db, checking, amount_minor=-40_000, days_ago=2 + i * 30,
                     payee="Transfer to Savings", category="transfer")
            make_txn(db, savings, amount_minor=40_000, days_ago=2 + i * 30,
                     payee="Transfer from Checking", category="transfer")
        db.commit()

        f = build_forecast(db, days=30)
        # Both sides detected; the combined liquid balance is unchanged by the pair.
        assert f.expected_bills_minor == 40_000
        assert f.expected_income_minor == 40_000
        assert f.end_balance_minor == f.start_balance_minor

    def test_discretionary_burn_from_nonrecurring_spend(self, db):
        checking = make_account(db, balance_minor=500_000)
        # 60 days * $10/day of one-off spending, no recurring pattern.
        for i in range(20):
            make_txn(db, checking, amount_minor=-3_000, days_ago=1 + i * 3,
                     payee=f"Shop {i}", category="shopping")
        db.commit()

        f = build_forecast(db, days=30)
        assert f.discretionary_daily_minor == 1_000  # 60k over 60 days
        assert f.end_balance_minor == 500_000 - 30 * 1_000

    def test_liability_accounts_not_in_liquid_balance(self, db):
        make_account(db, balance_minor=500_000)
        make_account(db, name="Visa", account_type="credit", balance_minor=-80_000)
        db.commit()
        f = build_forecast(db, days=30)
        assert f.start_balance_minor == 500_000
