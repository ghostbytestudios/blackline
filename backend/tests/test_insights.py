"""Cash-flow classification and summary aggregation."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.models import AccountSetting, NetWorthSnapshot
from app.services.insights import (
    build_summary,
    classify,
    effective_account_types,
    record_snapshot,
)

from .helpers import make_account, make_txn


class TestClassify:
    def test_transfer_excluded_entirely(self):
        assert classify(-50_000, "depository", "transfer") == (0, 0)
        assert classify(50_000, "credit", "transfer") == (0, 0)

    def test_atm_excluded(self):
        assert classify(-4_000, "depository", "atm") == (0, 0)

    def test_asset_positive_is_income(self):
        assert classify(260_000, "depository", "income") == (260_000, 0)

    def test_asset_negative_is_spending(self):
        assert classify(-1_549, "depository", "subscriptions") == (0, 1_549)

    def test_liability_charge_is_spending_regardless_of_sign(self):
        # A card purchase (negative on the card ledger) is money out of your pocket…
        assert classify(-2_500, "credit", "dining") == (0, 2_500)
        # …and so is loan interest, even though it may post positive on the loan ledger.
        assert classify(6_500, "loan", "interest") == (0, 6_500)


class TestEffectiveAccountTypes:
    def test_override_wins_over_auto_type(self, db):
        acct = make_account(db, account_type="depository")
        db.add(AccountSetting(account_id=acct.id, type_override="savings"))
        db.commit()
        assert effective_account_types(db)[acct.id] == "savings"

    def test_no_override_uses_auto_type(self, db):
        acct = make_account(db, account_type="credit")
        assert effective_account_types(db)[acct.id] == "credit"


class TestBuildSummary:
    def test_totals_and_trends(self, db):
        acct = make_account(db)
        make_txn(db, acct, amount_minor=260_000, days_ago=5, category="income")
        make_txn(db, acct, amount_minor=-100_000, days_ago=4, category="housing")
        make_txn(db, acct, amount_minor=-40_000, days_ago=3, category="groceries")
        make_txn(db, acct, amount_minor=-60_000, days_ago=2, category="transfer")  # excluded
        make_txn(db, acct, amount_minor=-999, days_ago=1, category="dining", pending=True)  # excluded
        db.commit()

        s = build_summary(db, days=30)
        assert s.total_inflow_minor == 260_000
        assert s.total_outflow_minor == 140_000
        assert s.net_minor == 120_000
        cats = {c.category: c.total_minor for c in s.top_categories}
        assert cats == {"housing": 100_000, "groceries": 40_000}
        assert len(s.monthly_trends) >= 1

    def test_liability_spending_counted_from_user_perspective(self, db):
        card = make_account(db, account_type="credit")
        make_txn(db, card, amount_minor=-3_000, days_ago=2, category="dining")
        make_txn(db, card, amount_minor=50_000, days_ago=1, category="transfer")  # card payment
        db.commit()

        s = build_summary(db, days=30)
        assert s.total_outflow_minor == 3_000
        assert s.total_inflow_minor == 0


class TestRecordSnapshot:
    def test_snapshot_splits_assets_and_liabilities(self, db):
        make_account(db, balance_minor=500_000, account_type="depository")
        make_account(db, balance_minor=-150_000, account_type="credit")
        db.commit()

        record_snapshot(db)
        snap = db.scalars(select(NetWorthSnapshot)).one()
        assert snap.assets_minor == 500_000
        assert snap.liabilities_minor == 150_000
        assert snap.net_worth_minor == 350_000
        assert snap.as_of == datetime.now(UTC).date()

    def test_same_day_snapshot_upserts_not_duplicates(self, db):
        acct = make_account(db, balance_minor=100_000)
        db.commit()
        record_snapshot(db)
        acct.balance_minor = 120_000
        db.commit()
        record_snapshot(db)

        snaps = list(db.scalars(select(NetWorthSnapshot)))
        assert len(snaps) == 1
        assert snaps[0].net_worth_minor == 120_000

    def test_snapshot_respects_type_override(self, db):
        """An account re-labeled as a loan moves to the liability side."""
        acct = make_account(db, balance_minor=-200_000, account_type="depository")
        db.add(AccountSetting(account_id=acct.id, type_override="loan"))
        db.commit()

        record_snapshot(db)
        snap = db.scalars(select(NetWorthSnapshot)).one()
        assert snap.liabilities_minor == 200_000
        assert snap.assets_minor == 0
