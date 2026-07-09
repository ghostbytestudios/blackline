"""Pydantic API contracts (request/response models)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# --- Lock / session ---
class UnlockRequest(BaseModel):
    passphrase: str = Field(min_length=8, max_length=1024)


class SetupTokenRequest(BaseModel):
    setup_token: str = Field(min_length=1, max_length=8192)


class ChangePassphraseRequest(BaseModel):
    current_passphrase: str = Field(min_length=1, max_length=1024)
    new_passphrase: str = Field(min_length=8, max_length=1024)


class ResetVaultRequest(BaseModel):
    """Destroys the vault. `confirm` must be the exact phrase, typed by the user."""

    confirm: str


class MerchantSummary(BaseModel):
    name: str
    category: str
    txn_count: int
    total_minor: int
    avg_txn_minor: int
    monthly_avg_minor: int
    last_date: date


# --- Dashboard ---
class DailyOutflowPoint(BaseModel):
    day: int  # day of month (1-based)
    cumulative_outflow_minor: int


class DashboardSummary(BaseModel):
    as_of: date
    spent_today_minor: int
    spent_yesterday_minor: int
    spent_mtd_minor: int
    income_mtd_minor: int
    days_in_month: int
    this_month: list[DailyOutflowPoint]  # cumulative, through today
    last_month: list[DailyOutflowPoint]  # cumulative, full month


class StatusResponse(BaseModel):
    initialized: bool
    unlocked: bool
    connected: bool  # SimpleFIN access URL present
    account_count: int
    last_sync: datetime | None = None
    demo_data: bool = False  # demo household loaded (see services/demo.py)


# --- Domain read models ---
class AccountOut(BaseModel):
    id: int
    name: str
    org_name: str | None
    account_type: str  # effective type (user override applied)
    type_override: str | None = None
    currency: str
    balance_minor: int
    available_minor: int | None
    balance_date: datetime | None
    is_active: bool
    goal_name: str | None = None
    goal_target_minor: int | None = None


class AccountSettingIn(BaseModel):
    type_override: str | None = Field(default=None, max_length=32)
    goal_name: str | None = Field(default=None, max_length=120)
    goal_target_minor: int | None = Field(default=None, ge=0)


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
    note: str | None = None
    tags: list[str] = []

    @field_validator("tags", mode="before")
    @classmethod
    def _tags_from_csv(cls, v: object) -> object:
        # Stored as a comma-separated string; exposed as a list.
        if isinstance(v, str):
            return [t for t in v.split(",") if t]
        return v


class TransactionAnnotate(BaseModel):
    """Note/tags update. Omitted fields are left unchanged."""

    note: str | None = Field(default=None, max_length=2000)
    tags: list[str] | None = Field(default=None, max_length=20)


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


class PortfolioHolding(BaseModel):
    id: int
    account_id: int
    account_name: str
    symbol: str | None
    description: str | None
    shares: str | None
    market_value_minor: int | None
    cost_basis_minor: int | None
    currency: str
    gain_minor: int | None = None
    gain_pct: float | None = None


class PortfolioSummary(BaseModel):
    total_value_minor: int
    total_cost_minor: int
    total_gain_minor: int | None
    gain_pct: float | None
    holding_count: int
    holdings: list[PortfolioHolding]


class RecurringCharge(BaseModel):
    name: str
    category: str
    cadence: str  # weekly | biweekly | monthly | quarterly | yearly | irregular
    typical_amount_minor: int
    occurrences: int
    last_date: date
    monthly_estimate_minor: int
    next_date: date  # projected next charge (last_date + cadence period)
    days_until: int  # negative = past due / possibly lapsed


class CategoryUpdate(BaseModel):
    category: str = Field(min_length=1, max_length=64)


class CategoryRuleIn(BaseModel):
    pattern: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=64)
    priority: int = 100


class ProfileIn(BaseModel):
    gross_annual_income_minor: int = Field(ge=0, le=1_000_000_000_00)


class ProfileOut(BaseModel):
    gross_annual_income_minor: int


class BudgetIn(BaseModel):
    category: str = Field(min_length=1, max_length=64)
    limit_minor: int = Field(ge=0)
    rollover: bool = False


class BudgetStatus(BaseModel):
    category: str
    limit_minor: int
    spent_minor: int  # current calendar month
    rollover: bool = False
    carryover_minor: int = 0  # last month's unspent (+) / overspend (-), if rollover
    effective_limit_minor: int = 0  # limit + carryover (floored at 0)


class BudgetMonth(BaseModel):
    month: str  # "YYYY-MM"
    spent_minor: int
    limit_minor: int  # the limit as it stands today (limits aren't versioned)
    over: bool


class BudgetHistory(BaseModel):
    category: str
    months: list[BudgetMonth]  # oldest first, includes current month


class GoalIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    target_minor: int = Field(gt=0)
    target_date: date | None = None
    account_ids: list[int] = Field(min_length=1)


class GoalOut(BaseModel):
    id: int
    name: str
    target_minor: int
    target_date: date | None
    start_minor: int
    account_ids: list[int]
    created_at: datetime
    # Computed:
    current_minor: int  # combined balance of linked accounts today
    progress_pct: float  # saved-since-start / (target - start)
    required_monthly_minor: int | None  # to hit target_date from here
    on_track: bool | None  # progress vs elapsed time (needs a target_date)


class PortfolioPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    as_of: date
    total_value_minor: int
    total_cost_minor: int


class ForecastPoint(BaseModel):
    date: date
    balance_minor: int


class ForecastSummary(BaseModel):
    start_balance_minor: int  # liquid accounts today
    end_balance_minor: int
    expected_income_minor: int  # scheduled recurring inflows within the horizon
    expected_bills_minor: int  # scheduled recurring outflows within the horizon
    discretionary_daily_minor: int  # flat daily burn for the non-recurring rest
    days: int
    points: list[ForecastPoint]


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


class NetWorthPoint(BaseModel):
    as_of: date
    net_worth_minor: int
    assets_minor: int
    liabilities_minor: int


class InsightCard(BaseModel):
    id: str
    title: str
    detail: str
    severity: str  # "critical" | "warning" | "info"
    icon: str  # hint for the frontend icon
    action_label: str | None = None
    action_route: str | None = None


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


# --- Statement import (CSV/OFX) ---

# Bank exports are small; this cap (~8 MB of text) only guards against abuse.
_MAX_IMPORT_CHARS = 8_000_000


class ColumnMapping(BaseModel):
    """CSV column assignments (0-based indexes). `amount` is a single signed
    column; alternatively `debit`/`credit` are separate unsigned columns."""

    date: int = Field(ge=0)
    amount: int | None = Field(default=None, ge=0)
    debit: int | None = Field(default=None, ge=0)
    credit: int | None = Field(default=None, ge=0)
    payee: int | None = Field(default=None, ge=0)
    description: int | None = Field(default=None, ge=0)
    memo: int | None = Field(default=None, ge=0)
    date_format: str | None = Field(default=None, max_length=32)  # strptime; None = auto
    flip_amounts: bool = False  # file records spending as positive

    @model_validator(mode="after")
    def _needs_an_amount(self) -> "ColumnMapping":
        if self.amount is None and self.debit is None and self.credit is None:
            raise ValueError("Map either an amount column or debit/credit columns.")
        return self


class ImportPreviewRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=_MAX_IMPORT_CHARS)


class ImportPreview(BaseModel):
    kind: str  # "csv" | "ofx"
    headers: list[str]
    sample_rows: list[list[str]]
    row_count: int
    suggested_mapping: ColumnMapping | None = None  # CSV only
    currency: str | None = None  # OFX CURDEF, if present
    warnings: list[str] = []


class ImportCommitRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=_MAX_IMPORT_CHARS)
    account_id: int
    mapping: ColumnMapping | None = None  # required for CSV, ignored for OFX
    skip_duplicates: bool = True


class ImportResult(BaseModel):
    total_rows: int
    inserted: int
    duplicates_skipped: int
    unparsed_skipped: int
    warnings: list[str] = []


class ManualAccountIn(BaseModel):
    """A hand-created account to hold imported statements (no provider link)."""

    name: str = Field(min_length=1, max_length=255)
    account_type: str = "checking"
    currency: str = Field(default="USD", min_length=3, max_length=8)
    balance_minor: int = 0
