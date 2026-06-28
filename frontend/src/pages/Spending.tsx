import {
  Bar,
  BarChart,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useEffect, useState } from "react";
import { Trash2, Sparkles } from "lucide-react";
import {
  useBudgets,
  useDeleteBudget,
  useInsights,
  useProfile,
  useSetBudget,
  useSuggestBudgets,
} from "../hooks/useApi";
import { Card, EmptyState, Loading, PageHeader } from "../components/ui";
import { formatMoney, fromMinor, titleCase } from "../lib/format";
import type { BudgetStatus } from "../lib/types";

function BudgetRow({ budget }: { budget: BudgetStatus }) {
  const setBudget = useSetBudget();
  const delBudget = useDeleteBudget();
  const [limit, setLimit] = useState(String(budget.limit_minor / 100));

  // Keep the input in sync if the budget changes elsewhere (e.g. suggest).
  useEffect(() => setLimit(String(budget.limit_minor / 100)), [budget.limit_minor]);

  const commit = () => {
    const dollars = parseFloat(limit);
    if (isNaN(dollars) || dollars < 0) {
      setLimit(String(budget.limit_minor / 100)); // revert invalid input
      return;
    }
    const minor = Math.round(dollars * 100);
    if (minor !== budget.limit_minor) setBudget.mutate({ category: budget.category, limit_minor: minor });
  };

  const pct = budget.limit_minor > 0 ? (budget.spent_minor / budget.limit_minor) * 100 : 0;
  const over = budget.spent_minor > budget.limit_minor;
  const barColor = over ? "bg-red-500" : pct >= 80 ? "bg-amber-400" : "bg-accent";

  return (
    <div>
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-slate-700">{titleCase(budget.category)}</span>
        <div className="flex items-center gap-2">
          <span className={`font-mono tnum ${over ? "text-red-500" : "text-slate-500"}`}>
            {formatMoney(budget.spent_minor)}
          </span>
          <span className="text-slate-400">/</span>
          <div className="relative">
            <span className="absolute left-1.5 top-1/2 -translate-y-1/2 text-xs text-slate-400">$</span>
            <input
              value={limit}
              onChange={(e) => setLimit(e.target.value)}
              onBlur={commit}
              onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
              inputMode="decimal"
              className="w-20 rounded border border-slate-200 py-1 pl-4 pr-1 text-right font-mono text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </div>
          <button
            onClick={() => delBudget.mutate(budget.category)}
            className="text-slate-300 hover:text-red-500"
            title="Remove budget"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>
      <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-slate-100">
        <div className={`h-full rounded-full ${barColor}`} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
    </div>
  );
}

const BUDGET_CATEGORIES = [
  "groceries", "dining", "transport", "travel", "shopping", "subscriptions",
  "entertainment", "utilities", "housing", "health", "insurance", "fees",
];

function Budgets() {
  const { data: budgets } = useBudgets();
  const { data: profile } = useProfile();
  const setBudget = useSetBudget();
  const suggest = useSuggestBudgets();
  const [newCat, setNewCat] = useState("groceries");
  const [newAmt, setNewAmt] = useState("");

  const hasIncome = (profile?.gross_annual_income_minor ?? 0) > 0;
  const rows = budgets ?? [];
  const used = new Set(rows.map((b) => b.category));
  const available = BUDGET_CATEGORIES.filter((c) => !used.has(c));

  const add = () => {
    const dollars = parseFloat(newAmt);
    if (!newCat || isNaN(dollars) || dollars <= 0) return;
    setBudget.mutate({ category: newCat, limit_minor: Math.round(dollars * 100) });
    setNewAmt("");
  };

  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-semibold text-slate-900">Monthly Budgets</h2>
        {hasIncome && (
          <button
            onClick={() => suggest.mutate()}
            disabled={suggest.isPending}
            className="flex items-center gap-1.5 rounded-lg border border-accent px-3 py-1.5 text-sm font-medium text-accent hover:bg-blue-50 disabled:opacity-50"
            title="Fill in recommended budgets from your income (won't overwrite existing)"
          >
            <Sparkles className="h-4 w-4" />
            {suggest.isPending ? "Suggesting…" : "Suggest from income"}
          </button>
        )}
      </div>
      {rows.length === 0 ? (
        <p className="mb-4 text-sm text-slate-400">
          No budgets yet. Add one below to get over-budget alerts in Insights.
        </p>
      ) : (
        <div className="mb-4 space-y-3">
          {rows.map((b) => (
            <BudgetRow key={b.category} budget={b} />
          ))}
        </div>
      )}

      {available.length > 0 && (
        <div className="flex items-center gap-2">
          <select
            value={newCat}
            onChange={(e) => setNewCat(e.target.value)}
            className="rounded-lg border border-slate-300 px-2 py-2 text-sm"
          >
            {available.map((c) => (
              <option key={c} value={c}>
                {titleCase(c)}
              </option>
            ))}
          </select>
          <div className="relative">
            <span className="absolute left-2 top-1/2 -translate-y-1/2 text-sm text-slate-400">$</span>
            <input
              value={newAmt}
              onChange={(e) => setNewAmt(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && add()}
              inputMode="decimal"
              placeholder="500"
              className="w-28 rounded-lg border border-slate-300 py-2 pl-5 pr-2 text-sm"
            />
          </div>
          <button
            onClick={add}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
          >
            Add budget
          </button>
        </div>
      )}
    </Card>
  );
}

const COLORS = [
  "#2563eb", "#7c3aed", "#db2777", "#ea580c", "#16a34a",
  "#0891b2", "#ca8a04", "#dc2626", "#4f46e5", "#0d9488",
];

export default function Spending() {
  const { data, isLoading } = useInsights(120);
  const s = data;
  const cats = s?.top_categories ?? [];

  const pieData = cats.map((c) => ({ name: titleCase(c.category), value: fromMinor(c.total_minor) }));
  const barData = (s?.monthly_trends ?? []).map((m) => ({
    month: m.month,
    Spending: fromMinor(m.outflow_minor),
    Income: fromMinor(m.inflow_minor),
  }));

  return (
    <div>
      <PageHeader title="Spending Analysis" />
      <div className="mb-5">
        <Budgets />
      </div>
      {isLoading ? (
        <Loading />
      ) : cats.length === 0 ? (
        <EmptyState title="No spending data yet" hint="Sync transactions to see category breakdowns." />
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <Card>
            <h2 className="mb-2 font-semibold text-slate-900">By Category</h2>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={60} outerRadius={100}>
                  {pieData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v: number) => `$${v.toFixed(2)}`} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </Card>

          <Card>
            <h2 className="mb-2 font-semibold text-slate-900">Income vs Spending</h2>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={barData}>
                <XAxis dataKey="month" fontSize={12} />
                <YAxis fontSize={12} />
                <Tooltip formatter={(v: number) => `$${v.toFixed(2)}`} />
                <Legend />
                <Bar dataKey="Income" fill="#16a34a" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Spending" fill="#dc2626" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          <Card className="lg:col-span-2">
            <h2 className="mb-3 font-semibold text-slate-900">Top Categories</h2>
            <div className="divide-y divide-slate-100">
              {cats.map((c, i) => (
                <div key={c.category} className="flex items-center justify-between py-2.5">
                  <div className="flex items-center gap-2">
                    <span
                      className="h-3 w-3 rounded-full"
                      style={{ background: COLORS[i % COLORS.length] }}
                    />
                    <span className="font-medium text-slate-800">{titleCase(c.category)}</span>
                    <span className="text-xs text-slate-400">({c.txn_count} txns)</span>
                  </div>
                  <span className="font-mono font-semibold tnum text-slate-900">
                    {formatMoney(c.total_minor)}
                  </span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
