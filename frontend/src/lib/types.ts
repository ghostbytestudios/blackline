// Mirrors the backend Pydantic schemas (app/schemas.py).

export interface Status {
  initialized: boolean;
  unlocked: boolean;
  connected: boolean;
  account_count: number;
  last_sync: string | null;
  demo_data: boolean;
}

export interface Account {
  id: number;
  name: string;
  org_name: string | null;
  account_type: string; // effective (override applied)
  type_override: string | null;
  currency: string;
  balance_minor: number;
  available_minor: number | null;
  balance_date: string | null;
  is_active: boolean;
  goal_name: string | null;
  goal_target_minor: number | null;
}

export interface Transaction {
  id: number;
  account_id: number;
  posted_at: string;
  amount_minor: number;
  description: string;
  payee: string | null;
  pending: boolean;
  category: string;
  category_source: "auto" | "user";
  note: string | null;
  tags: string[];
}

export interface MerchantSummary {
  name: string;
  category: string;
  txn_count: number;
  total_minor: number;
  avg_txn_minor: number;
  monthly_avg_minor: number;
  last_date: string;
}

export interface CategorySpend {
  category: string;
  total_minor: number;
  txn_count: number;
}

export interface MonthlyTrend {
  month: string;
  inflow_minor: number;
  outflow_minor: number;
  net_minor: number;
}

export interface Profile {
  gross_annual_income_minor: number;
}

export interface BudgetStatus {
  category: string;
  limit_minor: number;
  spent_minor: number;
}

export interface PortfolioHolding {
  id: number;
  account_id: number;
  account_name: string;
  symbol: string | null;
  description: string | null;
  shares: string | null;
  market_value_minor: number | null;
  cost_basis_minor: number | null;
  currency: string;
  gain_minor: number | null;
  gain_pct: number | null;
}

export interface PortfolioSummary {
  total_value_minor: number;
  total_cost_minor: number;
  total_gain_minor: number | null;
  gain_pct: number | null;
  holding_count: number;
  holdings: PortfolioHolding[];
}

export interface RecurringCharge {
  name: string;
  category: string;
  cadence: string;
  typical_amount_minor: number;
  occurrences: number;
  last_date: string;
  monthly_estimate_minor: number;
  next_date: string;
  days_until: number;
}

export interface NetWorthPoint {
  as_of: string;
  net_worth_minor: number;
  assets_minor: number;
  liabilities_minor: number;
}

export interface InsightCard {
  id: string;
  title: string;
  detail: string;
  severity: "critical" | "warning" | "info";
  icon: string;
  action_label: string | null;
  action_route: string | null;
}

export interface InsightsSummary {
  range_start: string;
  range_end: string;
  total_inflow_minor: number;
  total_outflow_minor: number;
  net_minor: number;
  net_worth_minor: number;
  top_categories: CategorySpend[];
  monthly_trends: MonthlyTrend[];
  observations: string[];
}

export interface DailyOutflowPoint {
  day: number;
  cumulative_outflow_minor: number;
}

export interface DashboardSummary {
  as_of: string;
  spent_today_minor: number;
  spent_yesterday_minor: number;
  spent_mtd_minor: number;
  income_mtd_minor: number;
  days_in_month: number;
  this_month: DailyOutflowPoint[];
  last_month: DailyOutflowPoint[];
}

export interface SyncResult {
  accounts_upserted: number;
  transactions_inserted: number;
  holdings_upserted: number;
  errors: string[];
}
