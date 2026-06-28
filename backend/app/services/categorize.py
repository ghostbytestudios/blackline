"""Transaction categorization.

Two-tier, deterministic, and explainable:
  1. User-defined rules (CategoryRule), ordered by priority.
  2. Built-in keyword heuristics as a fallback.

We never auto-overwrite a category a user set manually (category_source == "user").
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CategoryRule

# Built-in keyword → category map. Lowercase substring match on payee + description.
DEFAULT_KEYWORDS: dict[str, str] = {
    # Food & dining
    "starbucks": "dining", "mcdonald": "dining", "chipotle": "dining", "doordash": "dining",
    "uber eats": "dining", "grubhub": "dining", "restaurant": "dining", "coffee": "dining",
    # Groceries
    "whole foods": "groceries", "trader joe": "groceries", "safeway": "groceries",
    "kroger": "groceries", "aldi": "groceries", "costco": "groceries", "grocery": "groceries",
    # Transport
    "uber": "transport", "lyft": "transport", "shell": "transport", "chevron": "transport",
    "exxon": "transport", "gas": "transport", "parking": "transport", "transit": "transport",
    # Shopping
    "amazon": "shopping", "target": "shopping", "walmart": "shopping", "best buy": "shopping",
    # Subscriptions / entertainment
    "netflix": "subscriptions", "spotify": "subscriptions", "hulu": "subscriptions",
    "disney": "subscriptions", "apple.com/bill": "subscriptions", "youtube": "subscriptions",
    # Utilities & bills
    "comcast": "utilities", "xfinity": "utilities", "verizon": "utilities", "at&t": "utilities",
    "pg&e": "utilities", "electric": "utilities", "water": "utilities", "internet": "utilities",
    # Housing
    "rent": "housing", "mortgage": "housing", "hoa": "housing",
    # Income
    "payroll": "income", "direct dep": "income", "deposit": "income", "interest": "income",
    # Health
    "pharmacy": "health", "cvs": "health", "walgreens": "health", "doctor": "health",
    # Financial
    "transfer": "transfer", "withdrawal": "atm", "atm": "atm", "fee": "fees",
}


def _load_rules(db: Session) -> list[CategoryRule]:
    return list(db.scalars(select(CategoryRule).order_by(CategoryRule.priority.asc())))


def categorize_text(text: str, rules: list[CategoryRule]) -> str:
    """Return a category for the given text using user rules then built-in keywords."""
    hay = text.lower()
    for rule in rules:
        if rule.pattern.lower() in hay:
            return rule.category
    for keyword, category in DEFAULT_KEYWORDS.items():
        if keyword in hay:
            return category
    return "uncategorized"


def categorize_one(db: Session, payee: str | None, description: str) -> str:
    rules = _load_rules(db)
    return categorize_text(f"{payee or ''} {description}", rules)


def recategorize_all(db: Session) -> int:
    """Re-run categorization on auto-categorized transactions. Returns count changed."""
    from ..models import Transaction

    rules = _load_rules(db)
    changed = 0
    for txn in db.scalars(select(Transaction).where(Transaction.category_source == "auto")):
        new_cat = categorize_text(f"{txn.payee or ''} {txn.description}", rules)
        if new_cat != txn.category:
            txn.category = new_cat
            changed += 1
    db.commit()
    return changed
