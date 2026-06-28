"""Pydantic API contracts (request/response models)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# --- Lock / session ---
class UnlockRequest(BaseModel):
    passphrase: str = Field(min_length=8, max_length=1024)


class SetupTokenRequest(BaseModel):
    setup_token: str = Field(min_length=1, max_length=8192)


class StatusResponse(BaseModel):
    initialized: bool
    unlocked: bool
    connected: bool  # SimpleFIN access URL present
    account_count: int
    last_sync: datetime | None = None


# --- Domain read models ---
class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    org_name: str | None
    account_type: str
    currency: str
    balance_minor: int
    available_minor: int | None
    balance_date: datetime | None
    is_active: bool


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    account_id: int
    posted_at: datetime
    amount_minor: int
    description: str
    payee: str | None
    pending: bool
    category: str
    category_source: str


class HoldingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    account_id: int
    symbol: str | None
    description: str | None
    shares: str | None
    market_value_minor: int | None
    cost_basis_minor: int | None
    currency: str
    as_of: datetime | None


class CategoryUpdate(BaseModel):
    category: str = Field(min_length=1, max_length=64)


class CategoryRuleIn(BaseModel):
    pattern: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=64)
    priority: int = 100


class SyncResult(BaseModel):
    accounts_upserted: int
    transactions_inserted: int
    holdings_upserted: int
    errors: list[str] = []


# --- Insights ---
class CategorySpend(BaseModel):
    category: str
    total_minor: int
    txn_count: int


class MonthlyTrend(BaseModel):
    month: str  # YYYY-MM
    inflow_minor: int
    outflow_minor: int
    net_minor: int


class InsightsSummary(BaseModel):
    range_start: datetime
    range_end: datetime
    total_inflow_minor: int
    total_outflow_minor: int
    net_minor: int
    net_worth_minor: int
    top_categories: list[CategorySpend]
    monthly_trends: list[MonthlyTrend]
    observations: list[str]
