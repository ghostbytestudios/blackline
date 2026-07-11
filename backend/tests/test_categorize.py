"""Categorization tiers: user rules > structural patterns > merchant keywords > safety net."""

from __future__ import annotations

from app.models import CategoryRule
from app.services import categorize

from .helpers import make_account, make_txn


def cat(payee=None, description="", rules=(), **kw):
    return categorize.categorize_text(payee, description, list(rules), **kw)


class TestStructuralPatterns:
    def test_card_payment_thank_you_is_transfer(self):
        assert cat(None, "PAYMENT - THANK YOU") == "transfer"

    def test_loan_principal_is_transfer(self):
        assert cat(None, "AUTO LOAN PAYMENT - PRINCIPAL") == "transfer"

    def test_interest_paid_to_you_is_income(self):
        assert cat(None, "INTEREST PAID") == "income"

    def test_loan_interest_is_interest(self):
        assert cat(None, "INTEREST CHARGED") == "interest"

    def test_overdraft_is_fees_not_transfer(self):
        assert cat(None, "OVERDRAFT SERVICE CHARGE") == "fees"

    def test_atm_withdrawal(self):
        assert cat(None, "ATM WITHDRAWAL #4821") == "atm"

    def test_investment_contribution_is_transfer(self):
        # Brokerage/IRA deposits — excluded from both income and spending,
        # whatever sign the provider reports them with.
        assert cat(None, "Contribution", amount_minor=-50_000, account_type="investment") == "transfer"
        assert cat("Vanguard", "ROTH IRA CONTRIBUTION") == "transfer"

    def test_user_rule_beats_contribution_pattern(self):
        # A donation the user has claimed with a rule stays a donation.
        rule = CategoryRule(pattern="red cross", category="shopping", priority=10)
        assert cat("Red Cross", "CHARITABLE CONTRIBUTION - RED CROSS", rules=[rule]) == "shopping"


class TestMerchantKeywords:
    def test_starbucks_is_dining(self):
        assert cat("Starbucks", "STARBUCKS #1234 SEATTLE WA") == "dining"

    def test_netflix_is_subscription(self):
        assert cat("Netflix", "NETFLIX.COM") == "subscriptions"

    def test_kroger_is_groceries(self):
        assert cat("Kroger", "KROGER #123") == "groceries"

    def test_unknown_merchant_is_uncategorized(self):
        assert cat("Bob's Widgets", "BOBS WIDGETS LLC") == "uncategorized"


class TestUserRules:
    def test_user_rule_beats_keyword(self):
        rules = [CategoryRule(pattern="starbucks", category="entertainment", priority=50)]
        assert cat("Starbucks", "STARBUCKS #1234", rules) == "entertainment"

    def test_rule_priority_order_first_match_wins(self):
        # categorize_text scans in list order; the caller sorts by priority.
        rules = [
            CategoryRule(pattern="starbucks", category="dining", priority=10),
            CategoryRule(pattern="star", category="shopping", priority=90),
        ]
        assert cat("Starbucks", "", rules) == "dining"


class TestLiabilitySafetyNet:
    def test_positive_on_credit_account_is_transfer(self):
        """An unrecognized inbound amount on a card is a payment toward the debt."""
        assert cat("Mystery", "XYZ 123", amount_minor=50_000, account_type="credit") == "transfer"

    def test_negative_on_credit_account_stays_uncategorized(self):
        assert cat("Mystery", "XYZ 123", amount_minor=-5_000, account_type="credit") == "uncategorized"

    def test_positive_on_asset_account_not_affected(self):
        assert cat("Mystery", "XYZ 123", amount_minor=50_000, account_type="depository") == "uncategorized"


class TestDerivePattern:
    def test_prefers_clean_payee(self):
        assert categorize.derive_pattern("Trader Joe's", "TRADER JOES #558 RESTON VA") == "trader joe's"

    def test_generic_payee_falls_back_to_description(self):
        pattern = categorize.derive_pattern("Payment", "TST* HAPPY TACO ARLINGTON VA 1234")
        assert pattern is not None
        assert "happy" in pattern and "taco" in pattern
        assert "1234" not in pattern  # store/card numbers stripped

    def test_unusable_text_returns_none(self):
        assert categorize.derive_pattern(None, "AB 12") is None


class TestLearnFromCorrection:
    def test_correction_creates_rule_and_propagates(self, db):
        acct = make_account(db)
        t1 = make_txn(db, acct, amount_minor=-1200, payee="Joe's Deli", description="JOES DELI 42")
        t2 = make_txn(db, acct, amount_minor=-1500, payee="Joe's Deli", description="JOES DELI 42")
        t2.category_source = "auto"

        t1.category = "dining"
        t1.category_source = "user"
        changed = categorize.learn_from_correction(db, t1, "dining")

        assert changed == 1  # t2 re-categorized; t1 is user-owned and untouched
        db.refresh(t2)
        assert t2.category == "dining"
        rule = db.query(CategoryRule).one()
        assert rule.pattern == "joe's deli"
        assert rule.category == "dining"

    def test_user_categories_never_overwritten_by_recategorize(self, db):
        acct = make_account(db)
        txn = make_txn(db, acct, amount_minor=-999, payee="Starbucks", description="STARBUCKS")
        txn.category = "my-custom"
        txn.category_source = "user"
        db.commit()

        categorize.recategorize_all(db)
        db.refresh(txn)
        assert txn.category == "my-custom"
