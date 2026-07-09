"""ORM models.

Domain notes:
- Money is stored as integer **minor units** (cents) to avoid float rounding errors.
- External identifiers from SimpleFIN are kept so syncs are idempotent (upsert by id).
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Secret(Base):
    """Encrypted secret vault. Holds the AES-GCM ciphertext of sensitive values
    (e.g. the SimpleFIN access URL). Plaintext is never stored."""

    __tablename__ = "secrets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary(12), nullable=False)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("external_id", name="uq_account_external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    org_name: Mapped[str | None] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str] = mapped_column(String(32), default="depository")  # depository|credit|investment|loan
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    balance_minor: Mapped[int] = mapped_column(BigInteger, default=0)
    available_minor: Mapped[int | None] = mapped_column(BigInteger)
    balance_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    holdings: Mapped[list["Holding"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("account_id", "external_id", name="uq_txn_account_external"),
        Index("ix_txn_account_posted", "account_id", "posted_at"),
        Index("ix_txn_category", "category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)  # negative = outflow
    description: Mapped[str] = mapped_column(Text, default="")
    payee: Mapped[str | None] = mapped_column(String(255))
    memo: Mapped[str | None] = mapped_column(Text)
    pending: Mapped[bool] = mapped_column(Boolean, default=False)
    category: Mapped[str] = mapped_column(String(64), default="uncategorized")
    category_source: Mapped[str] = mapped_column(String(16), default="auto")  # auto|user
    note: Mapped[str | None] = mapped_column(Text)  # user-written annotation
    tags: Mapped[str] = mapped_column(Text, default="")  # comma-separated lowercase tags
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    account: Mapped["Account"] = relationship(back_populates="transactions")


class Holding(Base):
    """Investment holdings snapshot (from SimpleFIN investment accounts)."""

    __tablename__ = "holdings"
    __table_args__ = (
        UniqueConstraint("account_id", "external_id", name="uq_holding_account_external"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(String(255))
    shares: Mapped[str | None] = mapped_column(String(64))  # decimal as string to avoid float loss
    market_value_minor: Mapped[int | None] = mapped_column(BigInteger)
    cost_basis_minor: Mapped[int | None] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    account: Mapped["Account"] = relationship(back_populates="holdings")


class CategoryRule(Base):
    """User-defined categorization rule: substring/keyword match on payee/description."""

    __tablename__ = "category_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pattern: Mapped[str] = mapped_column(String(255), nullable=False)  # lowercase substring
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100)  # lower = higher priority
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AccountSetting(Base):
    """User overrides for an account: role (type) and an optional savings goal.

    Kept separate from `accounts` so sync never clobbers user choices and so we don't
    need a schema migration on the existing table.
    """

    __tablename__ = "account_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    type_override: Mapped[str | None] = mapped_column(String(32))  # checking|savings|investment|...
    goal_name: Mapped[str | None] = mapped_column(String(120))
    goal_target_minor: Mapped[int | None] = mapped_column(BigInteger)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class Profile(Base):
    """Single-row user profile (income, etc.). Always id=1."""

    __tablename__ = "profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gross_annual_income_minor: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class Budget(Base):
    """A monthly spending limit for a category (minor units)."""

    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    limit_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Rollover: last month's unspent (or overspent) amount adjusts this month's
    # effective limit — one month deep, not compounding.
    rollover: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class Goal(Base):
    """A savings goal funded by one or more accounts (multi-account, optional deadline).

    `start_minor` freezes the linked accounts' combined balance at creation so
    progress measures money saved *since* the goal was set, and on-track compares
    saved-so-far against elapsed time.
    """

    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    target_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date)
    start_minor: Mapped[int] = mapped_column(BigInteger, default=0)
    account_ids: Mapped[str] = mapped_column(Text, default="")  # comma-separated ids
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class PortfolioSnapshot(Base):
    """Daily snapshot of total portfolio value/cost (one row per day, like net worth)."""

    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    as_of: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    total_value_minor: Mapped[int] = mapped_column(BigInteger, default=0)
    total_cost_minor: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class NetWorthSnapshot(Base):
    """Daily snapshot of net worth and its asset/liability split (one row per day)."""

    __tablename__ = "networth_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    as_of: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    net_worth_minor: Mapped[int] = mapped_column(BigInteger, default=0)
    assets_minor: Mapped[int] = mapped_column(BigInteger, default=0)
    liabilities_minor: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AuditLog(Base):
    """Local audit trail for sensitive operations (sync, secret writes, unlock)."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    event: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="")
    success: Mapped[bool] = mapped_column(Boolean, default=True)
