"""Deterministic demo data: a realistic six-month household, no bank required.

Purpose: let people try every feature (and let us eyeball dashboards) before paying
for SimpleFIN. Same generator every time (fixed RNG seed, dates relative to today),
so charts always look alive and screenshots are reproducible.

All demo accounts carry the `demo-` external-id prefix so removal is surgical.
Transactions are categorized through the real categorizer — demo mode exercises the
same code paths a real sync does.
"""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    Account,
    AccountSetting,
    Budget,
    Holding,
    NetWorthSnapshot,
    Profile,
    Transaction,
)
from . import categorize
from .insights import record_snapshot

DEMO_PREFIX = "demo-"
_RNG_SEED = 20260101
_HISTORY_DAYS = 185


def _today() -> date:
    """UTC calendar date — matches how the dashboard buckets days, so seeded
    'today' activity actually lands on the dashboard's 'today'."""
    return datetime.now(timezone.utc).date()


def _month_mult(d: date) -> float:
    """Stable per-month discretionary-spending multiplier (lean vs heavy months).

    The current month is pinned heavy and the previous month lean so the
    dashboard's cumulative-pace lines visibly diverge; older months vary randomly.
    """
    today = _today()
    if (d.year, d.month) == (today.year, today.month):
        return 1.35
    prev = (today.replace(day=1) - timedelta(days=1))
    if (d.year, d.month) == (prev.year, prev.month):
        return 0.78
    return random.Random(f"{_RNG_SEED}:{d.strftime('%Y-%m')}").uniform(0.7, 1.4)


# One-off purchases sprinkled across months (payee, description, amount_minor).
_ONE_OFFS: list[tuple[str, str, int]] = [
    ("Jiffy Lube", "JIFFY LUBE OIL CHANGE", -8_900),
    ("AutoZone", "AUTOZONE #2213", -14_350),
    ("Ticketmaster", "TICKETMASTER CONCERT TIX", -18_400),
    ("Best Buy", "BEST BUY #442", -24_999),
    ("IKEA", "IKEA HOME FURNISHINGS", -31_250),
    ("CVS Pharmacy", "CVS PHARMACY #8841", -6_450),
    ("LabCorp", "LABCORP MEDICAL SERVICES", -9_500),
    ("Etsy", "ETSY.COM PURCHASE", -5_875),
    ("Delta Air", "DELTA AIR LINES ATL", -38_720),
    ("Fandango", "FANDANGO MOVIE TICKETS", -3_150),
    ("Nintendo", "NINTENDO ESHOP", -6_499),
    ("Home Depot", "HOME DEPOT #331", -12_780),
]


class DemoError(ValueError):
    """Seed guard violations (vault not empty, etc.)."""


def has_demo_data(db: Session) -> bool:
    return (
        db.scalar(select(Account.id).where(Account.external_id.like(f"{DEMO_PREFIX}%")).limit(1))
        is not None
    )


def _dt(d: date, hour: int = 12) -> datetime:
    return datetime.combine(d, time(hour), tzinfo=timezone.utc)


def _monthly_dates(day_of_month: int, *, months: int = 7) -> list[date]:
    """Occurrences of a monthly bill on `day_of_month`, walking back from today."""
    today = _today()
    out: list[date] = []
    year, month = today.year, today.month
    for _ in range(months):
        d = date(year, month, min(day_of_month, 28))
        if d <= today:
            out.append(d)
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    return out


def _every(days: float, *, start_days_ago: int = _HISTORY_DAYS, phase: float = 0) -> list[date]:
    """Dates every `days` days from roughly `start_days_ago` up to today."""
    today = _today()
    out: list[date] = []
    ago = phase
    while ago <= start_days_ago:
        out.append(today - timedelta(days=round(ago)))
        ago += days
    return out


class _Seeder:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.rng = random.Random(_RNG_SEED)
        self.txn_count = 0
        self._txn_id = 0

    def account(self, slug: str, name: str, account_type: str, balance_minor: int) -> Account:
        acct = Account(
            external_id=f"{DEMO_PREFIX}{slug}",
            org_name="Demo Bank" if account_type != "investment" else "Demo Brokerage",
            name=name,
            account_type=account_type,
            balance_minor=balance_minor,
            available_minor=balance_minor if balance_minor > 0 else None,
            balance_date=datetime.now(timezone.utc),
        )
        self.db.add(acct)
        self.db.flush()
        return acct

    def txn(
        self,
        acct: Account,
        when: date,
        amount_minor: int,
        payee: str,
        description: str,
    ) -> None:
        self._txn_id += 1
        category = categorize.categorize_text(
            payee, description, [], amount_minor=amount_minor, account_type=acct.account_type
        )
        self.db.add(
            Transaction(
                account_id=acct.id,
                external_id=f"{DEMO_PREFIX}txn-{self._txn_id}",
                posted_at=_dt(when, hour=self.rng.randint(8, 20)),
                amount_minor=amount_minor,
                payee=payee,
                description=description,
                category=category,
                category_source="auto",
            )
        )
        self.txn_count += 1

    def vary(self, base: int, spread: float) -> int:
        """A value near `base`, within ±spread (fraction)."""
        return int(base * self.rng.uniform(1 - spread, 1 + spread))

    def discretionary(self, base: int, spread: float, when: date) -> int:
        """Like `vary`, additionally scaled by the month's lean/heavy multiplier."""
        return int(self.vary(base, spread) * _month_mult(when))


def seed(db: Session) -> dict:
    """Populate an *empty* vault with the demo household. Raises DemoError otherwise."""
    if db.scalar(select(func.count(Account.id))):
        raise DemoError("Vault already has accounts; demo data only loads into an empty vault.")

    s = _Seeder(db)

    checking = s.account("checking", "Everyday Checking", "depository", 623_412)
    savings = s.account("savings", "High-Yield Savings", "depository", 1_264_508)
    card = s.account("card", "Sapphire Visa", "credit", -87_361)
    invest = s.account("invest", "Brokerage", "investment", 3_417_500)
    loan = s.account("loan", "Auto Loan", "loan", -1_412_766)

    db.add(AccountSetting(account_id=savings.id, type_override="savings",
                          goal_name="Emergency Fund", goal_target_minor=1_500_000))

    # --- Checking: income + the household's bills and day-to-day spending ---
    for d in _every(14, phase=3):  # biweekly payroll
        s.txn(checking, d, 265_400, "Acme Corp Payroll", "ACME CORP DIRECT DEPOSIT PPD")
    for i, d in enumerate(_monthly_dates(25)):  # quarterly bonus
        if i % 3 == 1:
            s.txn(checking, d, 185_000, "Acme Corp Bonus", "ACME CORP BONUS DIRECT DEPOSIT PPD")
    for d in _monthly_dates(1):
        s.txn(checking, d, -165_000, "Oakwood Apartments", "OAKWOOD APTS LEASING PAYMENT")
    for d in _monthly_dates(5):
        s.txn(checking, d, s.vary(-9_200, 0.25), "Dominion Energy", "DOMINION ENERGY UTIL EPAY")
    for d in _monthly_dates(8):
        s.txn(checking, d, -7_999, "Xfinity", "XFINITY INTERNET AUTOPAY")
    for d in _monthly_dates(12):
        s.txn(checking, d, -6_500, "T-Mobile", "T-MOBILE MOBILE PHONE PMT")
    for d in _monthly_dates(10):
        s.txn(checking, d, -38_500, "Honda Financial", "HONDA FIN AUTO LOAN PAYMENT ACH")
    for d in _monthly_dates(15):
        s.txn(checking, d, -14_240, "Geico", "GEICO INSURANCE PREM AUTOPAY")
    for d in _monthly_dates(2):
        s.txn(checking, d, -40_000, "Transfer to Savings", "ACH TRANSFER TO HIGH YIELD SAVINGS")
    for d in _monthly_dates(20):
        s.txn(checking, d, -60_000, "Card Payment", "CARDMEMBER SERV EPAYMENT")
    for d in _every(5.5, phase=1):
        store = s.rng.choice(["Kroger", "Trader Joe's", "Whole Foods"])
        s.txn(checking, d, s.discretionary(-6_800, 0.55, d), store, f"{store.upper()} #{s.rng.randint(100, 999)}")
    for d in _every(7, phase=4):
        stop = s.rng.choice(["Shell", "Wawa"])
        s.txn(checking, d, s.discretionary(-4_100, 0.3, d), stop, f"{stop.upper()} FUEL {s.rng.randint(1000, 9999)}")
    for d in _every(9, phase=6):
        s.txn(checking, d, -4_000, "ATM", "ATM WITHDRAWAL #4821")

    # --- Savings: inbound transfer + interest ---
    for d in _monthly_dates(2):
        s.txn(savings, d, 40_000, "Transfer from Checking", "TRANSFER FROM CHECKING")
    for d in _monthly_dates(28):
        s.txn(savings, d, s.vary(2_350, 0.1), "Interest", "INTEREST PAID")

    # --- Credit card: subscriptions + discretionary spending + monthly payment ---
    for day, payee, desc, amt in (
        (3, "Netflix", "NETFLIX.COM", -1_549),
        (7, "Spotify", "SPOTIFY USA", -1_199),
        (11, "Apple", "APPLE.COM/BILL ICLOUD", -299),
        (17, "GitHub", "GITHUB INC", -400),
    ):
        for d in _monthly_dates(day):
            s.txn(card, d, amt, payee, desc)
    for d in _every(6, phase=2):
        s.txn(card, d, s.discretionary(-4_300, 0.7, d), "Amazon", f"AMAZON.COM*{s.rng.randint(10000, 99999)}")
    for d in _every(4, phase=1.5):
        spot = s.rng.choice(["Chipotle", "Starbucks", "TST* Corner Bistro", "Panera Bread"])
        s.txn(card, d, s.discretionary(-2_400, 0.6, d), spot, spot.upper())
    for d in _every(21, phase=9):
        s.txn(card, d, s.discretionary(-3_200, 0.5, d), "Steam", "STEAM GAMES")
    s.txn(card, _today() - timedelta(days=47), -28_450, "Marriott", "MARRIOTT RICHMOND VA")
    for d in _monthly_dates(20):
        s.txn(card, d, 60_000, "Payment", "PAYMENT - THANK YOU")

    # --- One-off purchases: 1-3 per month, alternating between checking and card ---
    for anchor in _monthly_dates(15):
        month_rng = random.Random(f"{_RNG_SEED}:oneoff:{anchor.strftime('%Y-%m')}")
        picks = month_rng.sample(_ONE_OFFS, k=month_rng.randint(1, 3))
        for payee, desc, amt in picks:
            when = anchor.replace(day=month_rng.randint(2, 27))
            if when > _today():
                continue
            target = card if month_rng.random() < 0.6 else checking
            # Wide price variance so repeated picks never mimic a fixed-price bill.
            s.txn(target, when, int(amt * month_rng.uniform(0.72, 1.28)), payee, desc)

    # --- Guaranteed current-month texture: early one-offs make the pace chart's
    # divergence visible, and "today" should never be empty on the dashboard. ---
    today = _today()
    for day, payee, desc, amt in (
        (2, "Delta Air", "DELTA AIR LINES ATL", -41_230),
        (5, "Best Buy", "BEST BUY #442", -22_460),
    ):
        if day <= today.day:
            s.txn(card, today.replace(day=day), amt, payee, desc)
    s.txn(checking, today, -1_285, "Starbucks", "STARBUCKS #1234")
    s.txn(card, today, -5_240, "Chipotle", "CHIPOTLE ONLINE")
    s.txn(checking, today, s.discretionary(-7_400, 0.2, today), "Kroger", "KROGER #481")

    # --- Auto loan: principal (transfer) + interest (real expense) ---
    for d in _monthly_dates(10):
        s.txn(loan, d, 32_000, "Honda Financial", "AUTO LOAN PAYMENT - PRINCIPAL")
        s.txn(loan, d, -6_500, "Honda Financial", "INTEREST CHARGED")

    # --- Brokerage holdings ---
    for ext, symbol, desc, shares, mv, cost in (
        ("h-vti", "VTI", "Vanguard Total Stock Market ETF", "45.2000", 1_310_000, 1_100_000),
        ("h-aapl", "AAPL", "Apple Inc.", "30.0000", 690_000, 480_000),
        ("h-bnd", "BND", "Vanguard Total Bond Market ETF", "80.0000", 570_000, 600_000),
        ("h-cash", None, "Money Market Sweep", None, 847_500, 847_500),
    ):
        db.add(Holding(
            account_id=invest.id, external_id=f"{DEMO_PREFIX}{ext}", symbol=symbol,
            description=desc, shares=shares, market_value_minor=mv, cost_basis_minor=cost,
            currency="USD", as_of=datetime.now(timezone.utc),
        ))

    # --- Profile + budgets (some comfortably under, one on pace to bust) ---
    profile = db.get(Profile, 1) or Profile(id=1)
    profile.gross_annual_income_minor = 9_500_000
    db.add(profile)
    for cat, limit in (
        ("groceries", 45_000), ("dining", 30_000), ("shopping", 25_000),
        ("entertainment", 8_000), ("transport", 45_000), ("utilities", 30_000),
    ):
        db.add(Budget(category=cat, limit_minor=limit))

    # --- Net-worth history: a random walk with upward drift (market wobble included),
    # liabilities shrinking as the loan amortizes. Walked backward from today so the
    # series always ends at the seeded balances. ---
    net_today = 623_412 + 1_264_508 - 87_361 + 3_417_500 - 1_412_766
    liab_today = 87_361 + 1_412_766
    net = float(net_today)
    for days_ago in range(1, 181):
        d = _today() - timedelta(days=days_ago)
        net -= s.rng.gauss(3_400, 14_000)  # drift ~$34/day, wobble like a real portfolio
        liab = liab_today + int(days_ago * 1_051)  # loan principal walking back up
        db.add(NetWorthSnapshot(
            as_of=d, net_worth_minor=int(net), assets_minor=int(net) + liab,
            liabilities_minor=liab,
        ))
    db.commit()
    record_snapshot(db)  # today's point from the seeded balances

    return {
        "accounts": 5,
        "transactions": s.txn_count,
        "holdings": 4,
        "snapshots": 181,
    }


def remove(db: Session) -> dict:
    """Remove demo data. Snapshots/budgets/profile are wiped too: seeding is only
    allowed into an empty vault, so at removal time they are demo artifacts."""
    demo_accounts = list(
        db.scalars(select(Account).where(Account.external_id.like(f"{DEMO_PREFIX}%")))
    )
    for acct in demo_accounts:  # ORM delete cascades to transactions + holdings
        db.delete(acct)
    db.execute(NetWorthSnapshot.__table__.delete())
    db.execute(Budget.__table__.delete())
    db.execute(AccountSetting.__table__.delete())
    profile = db.get(Profile, 1)
    if profile:
        profile.gross_annual_income_minor = 0
    db.commit()
    return {"accounts_removed": len(demo_accounts)}
