"""Transaction categorization.

Three tiers, deterministic and explainable, evaluated in order:
  1. User-defined rules (CategoryRule) — including rules *learned* from manual corrections.
  2. Structural patterns — card payments, transfers, fees, insurance (matched on the raw
     bank description, which carries ACH/EPAY markers the clean payee does not).
  3. Merchant keyword map — matched primarily against SimpleFIN's clean `payee` field.

A user-set category (category_source == "user") is never overwritten by auto-categorization.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CategoryRule, Transaction

# --- Tier 2: structural patterns (substring match on payee+description) ---
# Order matters: first hit wins. These catch internal money movement so it is excluded
# from spending analysis, plus recurring bill types the merchant map would miss.
STRUCTURAL: list[tuple[str, str]] = [
    ("mobile payment - thank you", "transfer"),
    ("amex epayment", "transfer"),
    ("crd epay", "transfer"),
    ("credit crd", "transfer"),
    ("epayment", "transfer"),
    ("online payment", "transfer"),
    ("autopay", "transfer"),
    ("ach pmt", "transfer"),
    ("ach transfer", "transfer"),
    ("p&c", "insurance"),
    ("autopay insurance", "insurance"),
    ("overdraft", "fees"),
    ("service charge", "fees"),
    ("late fee", "fees"),
    ("interest charged", "fees"),
    ("foreign transaction fee", "fees"),
    ("atm withdrawal", "atm"),
    ("withdrawal", "atm"),
]

# --- Tier 3: merchant / keyword map (substring match on payee+description) ---
KEYWORDS: dict[str, str] = {
    # Dining (incl. Toast "TST*" and Square "SQ *" POS prefixes)
    "starbucks": "dining", "mcdonald": "dining", "chipotle": "dining", "doordash": "dining",
    "uber eats": "dining", "grubhub": "dining", "restaurant": "dining", "coffee": "dining",
    "taqueria": "dining", "taco": "dining", "pizza": "dining", "grill": "dining",
    "kitchen": "dining", "cafe": "dining", "diner": "dining", "bar & grill": "dining",
    "panera": "dining", "chick-fil-a": "dining", "wendys": "dining", "dunkin": "dining",
    "tst*": "dining", "sq *": "dining", "five guys": "dining", "subway": "dining",
    "yard house": "dining", "buffalo wild": "dining", "olive garden": "dining",
    # Groceries
    "whole foods": "groceries", "trader joe": "groceries", "safeway": "groceries",
    "kroger": "groceries", "aldi": "groceries", "costco": "groceries", "grocery": "groceries",
    "publix": "groceries", "harris teeter": "groceries", "wegmans": "groceries",
    "food lion": "groceries", "giant": "groceries", "sprouts": "groceries",
    # Fuel & convenience & transport
    "wawa": "transport", "7-eleven": "transport", "shell": "transport", "chevron": "transport",
    "exxon": "transport", "bp ": "transport", "sunoco": "transport", "fuel": "transport",
    "circle k": "transport", "a-plus": "transport", "gas": "transport", "parking": "transport",
    "uber": "transport", "lyft": "transport", "transit": "transport", "toll": "transport",
    "ezpass": "transport", "e-zpass": "transport", "amtrak": "transport", "delta air": "transport",
    "love's": "transport", "loves travel": "transport", "sam's xpress": "transport",
    "car wash": "transport", "autozone": "transport", "jiffy lube": "transport",
    # Travel / lodging
    "hyatt": "travel", "marriott": "travel", "hilton": "travel", "airbnb": "travel",
    "hotel": "travel", "expedia": "travel", "booking.com": "travel", "airlines": "travel",
    # Shopping
    "amazon": "shopping", "target": "shopping", "walmart": "shopping", "best buy": "shopping",
    "ebay": "shopping", "etsy": "shopping", "home depot": "shopping", "lowes": "shopping",
    "ikea": "shopping", "macy": "shopping", "nordstrom": "shopping", "apple store": "shopping",
    # Subscriptions / software
    "netflix": "subscriptions", "spotify": "subscriptions", "hulu": "subscriptions",
    "hbo": "subscriptions", "disney": "subscriptions", "youtube": "subscriptions",
    "apple.com/bill": "subscriptions", "anthropic": "subscriptions", "openai": "subscriptions",
    "github": "subscriptions", "google storage": "subscriptions", "patreon": "subscriptions",
    "prime video": "subscriptions", "audible": "subscriptions", "icloud": "subscriptions",
    "netlify": "subscriptions", "adobe": "subscriptions", "notion": "subscriptions",
    # Entertainment
    "amc ": "entertainment", "cinema": "entertainment", "movie": "entertainment",
    "theaters": "entertainment", "ticketmaster": "entertainment", "fandango": "entertainment",
    "steam": "entertainment", "playstation": "entertainment", "xbox": "entertainment",
    "nintendo": "entertainment", "regal": "entertainment",
    # Student loans / debt servicers
    "nelnet": "loans", "mohela": "loans", "sallie mae": "loans", "great lakes": "loans",
    # Utilities / telecom
    "comcast": "utilities", "xfinity": "utilities", "verizon": "utilities", "at&t": "utilities",
    "t-mobile": "utilities", "pg&e": "utilities", "electric": "utilities", "water": "utilities",
    "internet": "utilities", "dominion energy": "utilities", "mobile phone": "utilities",
    # Housing
    "rent": "housing", "mortgage": "housing", "hoa": "housing", "property mgmt": "housing",
    "apartment": "housing", "leasing": "housing",
    # Health & fitness
    "pharmacy": "health", "cvs": "health", "walgreens": "health", "doctor": "health",
    "vitamin shoppe": "health", "gnc": "health", "dental": "health", "medical": "health",
    "planet fitness": "health", "gym": "health", "lifetime fitness": "health",
    # Insurance
    "geico": "insurance", "state farm": "insurance", "progressive": "insurance",
    "allstate": "insurance", "insurance": "insurance",
    # Income
    "payroll": "income", "direct dep": "income", "direct deposit": "income",
    "dividend": "income", "interest paid": "income",
    # Financial / fees
    "transfer": "transfer", "atm": "atm", "fee": "fees",
}

_STATE_SUFFIX = re.compile(r"\s+[a-z]{2}$")  # trailing " VA", " NY", etc.
_STORE_NUM = re.compile(r"#?\d{3,}")  # store numbers / masked card digits


def _load_rules(db: Session) -> list[CategoryRule]:
    return list(db.scalars(select(CategoryRule).order_by(CategoryRule.priority.asc())))


def categorize_text(payee: str | None, description: str, rules: list[CategoryRule]) -> str:
    """Return a category using user rules, then structural patterns, then the merchant map."""
    payee_l = (payee or "").lower()
    desc_l = (description or "").lower()
    combined = f"{payee_l} {desc_l}"

    for rule in rules:
        if rule.pattern.lower() in combined:
            return rule.category
    for needle, category in STRUCTURAL:
        if needle in combined:
            return category
    for needle, category in KEYWORDS.items():
        if needle in combined:
            return category
    return "uncategorized"


def categorize_one(db: Session, payee: str | None, description: str) -> str:
    return categorize_text(payee, description, _load_rules(db))


def derive_pattern(payee: str | None, description: str) -> str | None:
    """Derive a stable, learnable substring rule from a transaction.

    Prefers the clean `payee`; falls back to a normalized slice of the description
    (state suffix and store/card numbers stripped). Returns None if nothing usable.
    """
    if payee and payee.strip().lower() not in {"payment", "purchase", ""}:
        return payee.strip().lower()
    text = (description or "").lower()
    text = _STORE_NUM.sub("", text)
    text = _STATE_SUFFIX.sub("", text).strip()
    words = [w for w in re.split(r"[\s*\-]+", text) if len(w) > 2]
    candidate = " ".join(words[:3]).strip()
    return candidate if len(candidate) >= 4 else None


def upsert_rule(db: Session, pattern: str, category: str, priority: int = 50) -> CategoryRule:
    existing = db.scalar(select(CategoryRule).where(CategoryRule.pattern == pattern))
    if existing is None:
        rule = CategoryRule(pattern=pattern, category=category, priority=priority)
        db.add(rule)
        db.flush()
        return rule
    existing.category = category
    existing.priority = min(existing.priority, priority)
    return existing


def learn_from_correction(db: Session, txn: Transaction, category: str) -> int:
    """Turn a manual correction into a rule and propagate it to auto transactions.

    Returns the number of other transactions re-categorized by the new rule.
    """
    pattern = derive_pattern(txn.payee, txn.description)
    if pattern is None:
        return 0
    upsert_rule(db, pattern, category)
    return recategorize_all(db)


def recategorize_all(db: Session) -> int:
    """Re-run categorization on auto-categorized transactions. Returns count changed."""
    rules = _load_rules(db)
    changed = 0
    for txn in db.scalars(select(Transaction).where(Transaction.category_source == "auto")):
        new_cat = categorize_text(txn.payee, txn.description, rules)
        if new_cat != txn.category:
            txn.category = new_cat
            changed += 1
    db.commit()
    return changed
