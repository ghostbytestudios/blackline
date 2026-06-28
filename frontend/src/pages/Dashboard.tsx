import { Link } from "react-router-dom";
import {
  ArrowLeftRight,
  CalendarDays,
  TrendingDown,
  TrendingUp,
  Activity,
} from "lucide-react";
import type { ReactNode } from "react";
import { useAccounts, useInsights, useTransactions } from "../hooks/useApi";
import { Card, CategoryChip, Loading } from "../components/ui";
import { formatMoney, formatDate, formatPercent, cashFlowMinor } from "../lib/format";
import type { Account } from "../lib/types";

function Kpi({
  label,
  value,
  delta,
  icon,
}: {
  label: string;
  value: string;
  delta?: { pct: number; goodWhenUp: boolean };
  icon: ReactNode;
}) {
  return (
    <Card>
      <div className="flex items-start justify-between">
        <span className="text-sm font-medium text-slate-500">{label}</span>
        <span className="text-slate-400">{icon}</span>
      </div>
      <div className="mt-3 font-mono text-3xl font-bold tracking-tight tnum text-slate-900">
        {value}
      </div>
      {delta && (
        <div
          className={`mt-2 flex items-center gap-1 text-sm font-medium ${
            (delta.pct >= 0) === delta.goodWhenUp ? "text-emerald-600" : "text-red-500"
          }`}
        >
          {delta.pct >= 0 ? (
            <TrendingUp className="h-4 w-4" />
          ) : (
            <TrendingDown className="h-4 w-4" />
          )}
          {formatPercent(Math.abs(delta.pct))} from last month
        </div>
      )}
    </Card>
  );
}

export default function Dashboard() {
  const insights = useInsights(120);
  const accounts = useAccounts();
  const txns = useTransactions();

  if (insights.isLoading) return <Loading label="Crunching your numbers…" />;

  const s = insights.data;
  const trends = s?.monthly_trends ?? [];
  const last = trends.at(-1);
  const prev = trends.at(-2);

  const monthlySpend = last?.outflow_minor ?? 0;
  const monthlyIncome = last?.inflow_minor ?? 0;
  const savingsRate =
    monthlyIncome > 0 ? ((monthlyIncome - monthlySpend) / monthlyIncome) * 100 : 0;

  const spendDelta =
    prev && prev.outflow_minor > 0
      ? ((monthlySpend - prev.outflow_minor) / prev.outflow_minor) * 100
      : undefined;
  const incomeDelta =
    prev && prev.inflow_minor > 0
      ? ((monthlyIncome - prev.inflow_minor) / prev.inflow_minor) * 100
      : undefined;

  const accts: Account[] = accounts.data ?? [];
  const acctName = (id: number) => accts.find((a) => a.id === id)?.name ?? "Account";
  const acctType = (id: number) => accts.find((a) => a.id === id)?.account_type;
  const assets = accts
    .filter((a) => a.balance_minor > 0)
    .reduce((sum, a) => sum + a.balance_minor, 0);
  const liabilities = accts
    .filter((a) => a.balance_minor < 0)
    .reduce((sum, a) => sum + Math.abs(a.balance_minor), 0);

  const recent = (txns.data ?? []).slice(0, 7);

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold text-slate-900">Dashboard</h1>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        <Kpi
          label="Net Worth"
          value={formatMoney(s?.net_worth_minor ?? 0)}
          icon={<CalendarDays className="h-5 w-5" />}
        />
        <Kpi
          label="Monthly Spend"
          value={formatMoney(monthlySpend)}
          delta={spendDelta !== undefined ? { pct: spendDelta, goodWhenUp: false } : undefined}
          icon={<TrendingDown className="h-5 w-5" />}
        />
        <Kpi
          label="Monthly Income"
          value={formatMoney(monthlyIncome)}
          delta={incomeDelta !== undefined ? { pct: incomeDelta, goodWhenUp: true } : undefined}
          icon={<TrendingUp className="h-5 w-5" />}
        />
        <Kpi
          label="Savings Rate"
          value={formatPercent(savingsRate)}
          icon={<Activity className="h-5 w-5" />}
        />
      </div>

      <Card className="mt-6">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2 font-semibold text-slate-900">
            <ArrowLeftRight className="h-5 w-5 text-accent" />
            Recent Activity
          </div>
          <Link to="/transactions" className="text-sm font-medium text-accent hover:underline">
            View all
          </Link>
        </div>
        {recent.length === 0 ? (
          <div className="py-8 text-center text-sm text-slate-400">
            No transactions yet. Connect an account in Settings, then Sync.
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {recent.map((t) => (
              <div key={t.id} className="flex items-center justify-between py-3">
                <div>
                  <div className="font-medium text-slate-800">
                    {t.payee || t.description || "Transaction"}
                  </div>
                  <div className="text-xs text-slate-400">
                    {formatDate(t.posted_at)} • {acctName(t.account_id)}
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {(() => {
                    const cf = cashFlowMinor(t.amount_minor, acctType(t.account_id));
                    return (
                      <span
                        className={`font-mono text-sm font-semibold tnum ${
                          cf < 0 ? "text-red-500" : "text-emerald-600"
                        }`}
                      >
                        {formatMoney(cf)}
                      </span>
                    );
                  })()}
                  <CategoryChip category={t.category} />
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <div className="mt-6 grid grid-cols-1 gap-5 sm:grid-cols-2">
        <div className="rounded-xl bg-ink-900 p-5 text-white shadow-sm">
          <div className="text-sm font-medium text-slate-300">Total Assets</div>
          <div className="mt-2 font-mono text-3xl font-bold tnum">{formatMoney(assets)}</div>
        </div>
        <Card>
          <div className="text-sm font-medium text-slate-500">Total Liabilities</div>
          <div className="mt-2 font-mono text-3xl font-bold tnum text-slate-900">
            {formatMoney(liabilities)}
          </div>
        </Card>
      </div>
    </div>
  );
}
