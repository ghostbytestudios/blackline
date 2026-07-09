"""Test data builders shared across test modules."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import Account, Transaction

_ID_COUNTER = iter(range(1, 1_000_000))


def make_account(
    db: Session,
    *,
    name: str = "Checking",
    account_type: str = "depository",
    balance_minor: int = 100_000,
) -> Account:
    acct = Account(
        external_id=f"test-{next(_ID_COUNTER)}",
        name=name,
        account_type=account_type,
        balance_minor=balance_minor,
    )
    db.add(acct)
    db.flush()
    return acct


def make_txn(
    db: Session,
    account: Account,
    *,
    amount_minor: int,
    days_ago: float = 0,
    payee: str | None = None,
    description: str = "",
    category: str = "uncategorized",
    pending: bool = False,
) -> Transaction:
    txn = Transaction(
        account_id=account.id,
        external_id=f"test-txn-{next(_ID_COUNTER)}",
        posted_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
        amount_minor=amount_minor,
        payee=payee,
        description=description,
        category=category,
        pending=pending,
    )
    db.add(txn)
    db.flush()
    return txn
