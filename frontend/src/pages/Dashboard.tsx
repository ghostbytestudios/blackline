import { Link } from "react-router-dom";
import {
  ArrowDownRight,
  ArrowLeftRight,
  ArrowUpRight,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import type { ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  useAccounts,
  useBudgets,
  useDashboard,
  useInsights,
  useRecurring,
  useTransactions,
} from "../hooks/useApi";
import { Card, CategoryChip, EmptyState, Loading } from "../components/ui";
import { formatMoney, formatDate, formatPercent, fromMinor, cashFlowMinor } from "../lib/format";
import {
  AXIS_LINE,
  AXIS_TICK,
  GRID_STROKE,
  LEGEND_STYLE,
  SERIES,
  TOOLTIP_ITEM_STYLE,
  TOOLTIP_LABEL_STYLE,
  TOOLTIP_STYLE,
} from "../lib/chartTheme";
import type { Account } from "../lib/types";

function Kpi({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card className="flex flex-1 flex-col justify-center">
      <div className="font-mono text-4xl font-bold tracking-tight tnum text-slate-100">
        {value}
      </div>
      <div className="mt-1.5 text-sm font-medium text-slate-400">{label}</div>
      {sub && <div className="mt-0.5 text-xs text-slate-500">{sub}</div>}
    </Card>
  );
}

function Stat({ label, value, accent }: { label: string; value: ReactNode; accent?: string }) {
  return (
    <div className="py-3 first:pt-0 last:pb-0">
      <div className={`font-mono text-2xl font-bold tnum ${accent ?? "text-slate-100"}`}>
        {value}
      </div>
      <div className="mt-0.5 text-sm text-slate-400">{label}</div>
    </div>
  );
}

const usd = (v: number) => (Math.abs(v) >= 1000 ? `$${(v / 1000).toFixed(1)}k` : `$${v.toFixed(0)}`);

export default function Dashboard() {
  const dash = useDashboard();
  const insights = useInsights(180);
  const accounts = useAccounts();
  const txns = useTransactions({ limit: 9 });
  const budgets = useBudgets();
  const recurring = useRecurring();

  if (dash.isLoading || insights.isLoading) return <Loading label="Crunching your numbers…" />;

  const d = dash.data;
  const s = insights.data;
  const accts: Account[] = accounts.data ?? [];

  if (accts.length === 0) {
    return (
      <div>
        <h1 className="mb-6 text-2xl font-bold text-slate-100">Dashboard</h1>
        <EmptyState
          title="Nothing to show yet"
          hint="Connect a bank in Settings (or load demo data) and sync to light this up."
        />
      </div>
    );
  }

  // --- Hero: cumulative spend by day of month, this month vs last ---
  const maxDay = Math.max(d?.days_in_month ?? 0, d?.last_month.length ?? 0);
  const heroData = Array.from({ length: maxDay }, (_, i) => {
    const day = i + 1;
    const cur = d?.this_month[i];
    const prev = d?.last_month[i];
    return {
      day,
      "This month": cur ? fromMinor(cur.cumulative_outflow_minor) : undefined,
      "Last month": prev ? fromMinor(prev.cumulative_outflow_minor) : undefined,
    };
  });

  // --- Right rail stats ---
  const netWorth = s?.net_worth_minor ?? 0;
  const recurringMonthly = (recurring.data ?? []).reduce(
    (sum, r) => sum + r.monthly_estimate_minor, 0,
  );
  const budgetRows = budgets.data ?? [];
  const budgetsOnTrack = budgetRows.filter((b) => b.spent_minor <= b.limit_minor).length;

  // --- Savings rate (this month; falls back to last full month early on) ---
  const trends = s?.monthly_trends ?? [];
  const lastFull = trends.length >= 2 ? trends[trends.length - 2] : undefined;
  const income = d?.income_mtd_minor ?? 0;
  const spent = d?.spent_mtd_minor ?? 0;
  let savingsRate: number | null = null;
  let savingsLabel = "Savings rate this month";
  if (income > 0) {
    savingsRate = ((income - spent) / income) * 100;
  } else if (lastFull && lastFull.inflow_minor > 0) {
    savingsRate = ((lastFull.inflow_minor - lastFull.outflow_minor) / lastFull.inflow_minor) * 100;
    savingsLabel = "Savings rate last month";
  }
  const savingsGood = savingsRate !== null && savingsRate >= 15;

  // --- Bottom row ---
  const recent = (txns.data ?? []).slice(0, 8);
  const acctName = (id: number) => accts.find((a) => a.id === id)?.name ?? "Account";
  const acctType = (id: number) => accts.find((a) => a.id === id)?.account_type;
  const barData = trends.slice(-6).map((m) => ({
    month: m.month.slice(2), // "26-07"
    Income: fromMinor(m.inflow_minor),
    Spending: fromMinor(m.outflow_minor),
  }));

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold text-slate-100">Dashboard</h1>

      <div className="grid grid-cols-12 gap-4">
        {/* Left rail: spending KPIs */}
        <div className="col-span-12 flex flex-col gap-4 sm:flex-row lg:col-span-3 lg:flex-col">
          <Kpi label="Spent this month" value={formatMoney(d?.spent_mtd_minor ?? 0)} />
          <Kpi label="Spent today" value={formatMoney(d?.spent_today_minor ?? 0)} />
          <Kpi label="Spent yesterday" value={formatMoney(d?.spent_yesterday_minor ?? 0)} />
        </div>

        {/* Hero: cumulative spend pace */}
        <Card className="col-span-12 lg:col-span-6">
          <div className="mb-2 font-semibold text-slate-100">Cumulative spend this month</div>
          <ResponsiveContainer width="100%" height={296}>
            <LineChart data={heroData} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid vertical={false} stroke={GRID_STROKE} />
              <XAxis
                dataKey="day"
                tick={AXIS_TICK}
                axisLine={AXIS_LINE}
                tickLine={AXIS_LINE}
                ticks={[1, 8, 15, 22, maxDay]}
              />
              <YAxis
                tick={AXIS_TICK}
                axisLine={AXIS_LINE}
                tickLine={AXIS_LINE}
                tickFormatter={usd}
                width={56}
                domain={[0, "auto"]}
              />
              <Tooltip
                formatter={(v) => `$${Number(v).toFixed(2)}`}
                labelFormatter={(day) => `Day ${day}`}
                contentStyle={TOOLTIP_STYLE}
                itemStyle={TOOLTIP_ITEM_STYLE}
                labelStyle={TOOLTIP_LABEL_STYLE}
              />
              <Legend wrapperStyle={LEGEND_STYLE} align="right" verticalAlign="top" height={28} />
              <Line
                type="monotone"
                dataKey="This month"
                stroke={SERIES.primary}
                strokeWidth={2.5}
                dot={false}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="Last month"
                stroke={SERIES.compare}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </Card>

        {/* Right rail: stat stack + savings highlight */}
        <div className="col-span-12 flex flex-col gap-4 lg:col-span-3">
          <Card className="flex-1">
            <div className="divide-y divide-ink-700">
              <Stat label="Net worth" value={formatMoney(netWorth)} />
              <Stat
                label="Income this month"
                value={formatMoney(d?.income_mtd_minor ?? 0)}
                accent="text-emerald-400"
              />
              <Stat label="Recurring / month" value={formatMoney(recurringMonthly)} />
              <Stat
                label="Budgets on track"
                value={
                  budgetRows.length > 0 ? (
                    `${budgetsOnTrack} of ${budgetRows.length}`
                  ) : (
                    <Link to="/spending" className="text-lg text-accent-soft hover:underline">
                      Set budgets →
                    </Link>
                  )
                }
              />
            </div>
          </Card>
          <div
            className={`rounded-xl border-2 p-5 ${
              savingsRate === null
                ? "border-ink-700 bg-ink-800"
                : savingsGood
                  ? "border-emerald-500/70 bg-ink-800"
                  : "border-amber-500/70 bg-ink-800"
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="font-mono text-3xl font-bold tnum text-slate-100">
                {savingsRate === null ? "—" : formatPercent(savingsRate)}
              </div>
              {savingsRate !== null &&
                (savingsGood ? (
                  <CheckCircle2 className="h-7 w-7 text-emerald-400" />
                ) : (
                  <AlertTriangle className="h-7 w-7 text-amber-400" />
                ))}
            </div>
            <div className="mt-1 text-sm text-slate-400">{savingsLabel}</div>
          </div>
        </div>

        {/* Recent activity */}
        <Card className="col-span-12 lg:col-span-7">
          <div className="mb-2 flex items-center justify-between">
            <div className="flex items-center gap-2 font-semibold text-slate-100">
              <ArrowLeftRight className="h-5 w-5 text-accent-soft" />
              Recent activity
            </div>
            <Link to="/transactions" className="text-sm font-medium text-accent-soft hover:underline">
              View all
            </Link>
          </div>
          {recent.length === 0 ? (
            <div className="py-8 text-center text-sm text-slate-500">
              No transactions yet. Connect an account in Settings, then Sync.
            </div>
          ) : (
            <div className="divide-y divide-ink-700">
              {recent.map((t) => {
                const cf = cashFlowMinor(t.amount_minor, acctType(t.account_id));
                const inflow = cf >= 0;
                return (
                  <div key={t.id} className="flex items-center gap-3 py-2.5">
                    <span
                      className={`flex h-7 w-7 shrink-0 items-center justify-center rounded ${
                        inflow ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"
                      }`}
                    >
                      {inflow ? (
                        <ArrowUpRight className="h-4 w-4" />
                      ) : (
                        <ArrowDownRight className="h-4 w-4" />
                      )}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="truncate font-medium text-slate-200">
                        {t.payee || t.description || "Transaction"}
                      </div>
                      <div className="text-xs text-slate-500">
                        {formatDate(t.posted_at)} · {acctName(t.account_id)}
                      </div>
                    </div>
                    <CategoryChip category={t.category} />
                    <span
                      className={`w-24 text-right font-mono text-sm font-semibold tnum ${
                        inflow ? "text-emerald-400" : "text-red-400"
                      }`}
                    >
                      {formatMoney(cf)}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </Card>

        {/* Income vs spending by month */}
        <Card className="col-span-12 lg:col-span-5">
          <div className="mb-2 font-semibold text-slate-100">Income vs spending (by month)</div>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={barData} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid vertical={false} stroke={GRID_STROKE} />
              <XAxis dataKey="month" tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={AXIS_LINE} />
              <YAxis
                tick={AXIS_TICK}
                axisLine={AXIS_LINE}
                tickLine={AXIS_LINE}
                tickFormatter={usd}
                width={56}
              />
              <Tooltip
                formatter={(v) => `$${Number(v).toFixed(2)}`}
                contentStyle={TOOLTIP_STYLE}
                itemStyle={TOOLTIP_ITEM_STYLE}
                labelStyle={TOOLTIP_LABEL_STYLE}
                cursor={{ fill: "#1b2740", opacity: 0.5 }}
              />
              <Legend wrapperStyle={LEGEND_STYLE} align="right" verticalAlign="top" height={28} />
              <Bar dataKey="Income" fill={SERIES.primary} radius={[3, 3, 0, 0]} isAnimationActive={false} />
              <Bar dataKey="Spending" fill={SERIES.compare} radius={[3, 3, 0, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
    </div>
  );
}
