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
import { RefreshCcw, Trash2, Sparkles } from "lucide-react";
import {
  useBudgetHistory,
  useBudgets,
  useDeleteBudget,
  useInsights,
  useProfile,
  useSetBudget,
  useSetProfile,
  useSuggestBudgets,
} from "../hooks/useApi";
import { Card, EmptyState, Loading, PageHeader } from "../components/ui";
import { formatMoney, fromMinor, titleCase } from "../lib/format";
import {
  AXIS_LINE,
  AXIS_TICK,
  LEGEND_STYLE,
  SERIES,
  TOOLTIP_ITEM_STYLE,
  TOOLTIP_LABEL_STYLE,
  TOOLTIP_STYLE,
} from "../lib/chartTheme";
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
    if (minor !== budget.limit_minor)
      setBudget.mutate({ category: budget.category, limit_minor: minor, rollover: budget.rollover });
  };

  const effective = budget.effective_limit_minor || budget.limit_minor;
  const pct = effective > 0 ? (budget.spent_minor / effective) * 100 : 0;
  const over = budget.spent_minor > effective;
  const barColor = over ? "bg-red-500/100" : pct >= 80 ? "bg-amber-400" : "bg-accent";

  return (
    <div>
      <div className="flex items-center justify-between text-sm">
        <span className="flex items-center gap-2 font-medium text-slate-300">
          {titleCase(budget.category)}
          {budget.rollover && budget.carryover_minor !== 0 && (
            <span
              className={`text-xs ${budget.carryover_minor > 0 ? "text-emerald-400" : "text-red-400"}`}
              title="Carried over from last month"
            >
              {budget.carryover_minor > 0 ? "+" : "−"}
              {formatMoney(Math.abs(budget.carryover_minor))} carried
            </span>
          )}
        </span>
        <div className="flex items-center gap-2">
          <span className={`font-mono tnum ${over ? "text-red-500" : "text-slate-400"}`}>
            {formatMoney(budget.spent_minor)}
          </span>
          <span className="text-slate-500">/</span>
          <div className="relative">
            <span className="absolute left-1.5 top-1/2 -translate-y-1/2 text-xs text-slate-500">$</span>
            <input
              value={limit}
              onChange={(e) => setLimit(e.target.value)}
              onBlur={commit}
              onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
              inputMode="decimal"
              className="w-20 rounded border border-ink-700 py-1 pl-4 pr-1 text-right font-mono text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </div>
          <button
            onClick={() =>
              setBudget.mutate({
                category: budget.category,
                limit_minor: budget.limit_minor,
                rollover: !budget.rollover,
              })
            }
            className={budget.rollover ? "text-accent-soft" : "text-slate-600 hover:text-slate-400"}
            title={
              budget.rollover
                ? "Rollover on: last month's leftover adjusts this month's limit"
                : "Rollover off — click to carry last month's leftover forward"
            }
          >
            <RefreshCcw className="h-4 w-4" />
          </button>
          <button
            onClick={() => delBudget.mutate(budget.category)}
            className="text-slate-600 hover:text-red-500"
            title="Remove budget"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>
      <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-ink-700">
        <div className={`h-full rounded-full ${barColor}`} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
    </div>
  );
}

function BudgetHistoryCard() {
  const { data } = useBudgetHistory(6);
  const rows = (data ?? []).filter((h) => h.months.some((m) => m.spent_minor > 0));
  if (rows.length === 0) return null;

  return (
    <Card className="mt-5">
      <h2 className="mb-1 font-semibold text-slate-100">Budget History</h2>
      <p className="mb-3 text-xs text-slate-500">
        Spend vs. today&apos;s limit, last 6 months. Green = under, red = over.
      </p>
      <div className="space-y-2.5">
        {rows.map((h) => (
          <div key={h.category} className="flex items-center gap-3 text-sm">
            <span className="w-28 shrink-0 font-medium text-slate-300">
              {titleCase(h.category)}
            </span>
            <div className="flex flex-1 gap-1.5">
              {h.months.map((m) => {
                const pct = m.limit_minor > 0 ? Math.round((m.spent_minor / m.limit_minor) * 100) : 0;
                return (
                  <div
                    key={m.month}
                    title={`${m.month}: ${formatMoney(m.spent_minor)} of ${formatMoney(m.limit_minor)} (${pct}%)`}
                    className={`h-6 flex-1 rounded flex items-center justify-center text-[10px] font-mono font-semibold ${
                      m.spent_minor === 0
                        ? "bg-ink-700/50 text-slate-600"
                        : m.over
                          ? "bg-red-500/25 text-red-300"
                          : "bg-emerald-500/20 text-emerald-300"
                    }`}
                  >
                    {m.spent_minor > 0 ? `${pct}%` : "–"}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
        <div className="flex items-center gap-3 pt-1 text-[10px] uppercase tracking-wider text-slate-500">
          <span className="w-28 shrink-0" />
          <div className="flex flex-1 gap-1.5">
            {(rows[0]?.months ?? []).map((m) => (
              <span key={m.month} className="flex-1 text-center">
                {m.month.slice(5)}
              </span>
            ))}
          </div>
        </div>
      </div>
    </Card>
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
  const setProfile = useSetProfile();
  const suggest = useSuggestBudgets();
  const [newCat, setNewCat] = useState("groceries");
  const [newAmt, setNewAmt] = useState("");
  const [showIncomePrompt, setShowIncomePrompt] = useState(false);
  const [incomeInput, setIncomeInput] = useState("");

  const hasIncome = (profile?.gross_annual_income_minor ?? 0) > 0;

  const saveIncomeAndSuggest = () => {
    const dollars = parseFloat(incomeInput.replace(/,/g, ""));
    if (isNaN(dollars) || dollars <= 0) return;
    setProfile.mutate({ gross_annual_income_minor: Math.round(dollars * 100) }, {
      onSuccess: () => {
        setShowIncomePrompt(false);
        suggest.mutate();
      },
    });
  };
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
        <h2 className="font-semibold text-slate-100">Monthly Budgets</h2>
        <button
          onClick={() => (hasIncome ? suggest.mutate() : setShowIncomePrompt((s) => !s))}
          disabled={suggest.isPending}
          className="flex items-center gap-1.5 rounded-lg border border-accent px-3 py-1.5 text-sm font-medium text-accent hover:bg-blue-500/10 disabled:opacity-50"
          title="Fill in a starter budget from your income using the 50/30/20 guideline (won't overwrite budgets you've set)"
        >
          <Sparkles className="h-4 w-4" />
          {suggest.isPending ? "Suggesting…" : "Suggest budgets (50/30/20)"}
        </button>
      </div>
      {showIncomePrompt && !hasIncome && (
        <div className="mb-4 flex flex-wrap items-center gap-2 rounded-lg border border-dashed border-ink-700 p-3">
          <span className="text-sm text-slate-400">
            Suggestions are based on your gross income — enter it once:
          </span>
          <span className="text-xs text-slate-500">$</span>
          <input
            value={incomeInput}
            onChange={(e) => setIncomeInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && saveIncomeAndSuggest()}
            placeholder="95000"
            inputMode="decimal"
            autoFocus
            className="w-28 rounded-lg border border-ink-700 px-3 py-1.5 text-right font-mono text-sm tnum focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          />
          <span className="text-xs text-slate-500">/ year</span>
          <button
            onClick={saveIncomeAndSuggest}
            disabled={setProfile.isPending || suggest.isPending}
            className="rounded-lg bg-accent px-3 py-1.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
          >
            Create budgets
          </button>
        </div>
      )}
      {rows.length === 0 ? (
        <p className="mb-4 text-sm text-slate-500">
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
            className="rounded-lg border border-ink-700 px-2 py-2 text-sm"
          >
            {available.map((c) => (
              <option key={c} value={c}>
                {titleCase(c)}
              </option>
            ))}
          </select>
          <div className="relative">
            <span className="absolute left-2 top-1/2 -translate-y-1/2 text-sm text-slate-500">$</span>
            <input
              value={newAmt}
              onChange={(e) => setNewAmt(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && add()}
              inputMode="decimal"
              placeholder="500"
              className="w-28 rounded-lg border border-ink-700 py-2 pl-5 pr-2 text-sm"
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
        <BudgetHistoryCard />
      </div>
      {isLoading ? (
        <Loading />
      ) : cats.length === 0 ? (
        <EmptyState title="No spending data yet" hint="Sync transactions to see category breakdowns." />
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <Card>
            <h2 className="mb-2 font-semibold text-slate-100">By Category</h2>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={60} outerRadius={100} stroke="none">
                  {pieData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(v: number) => `$${v.toFixed(2)}`}
                  contentStyle={TOOLTIP_STYLE}
                  itemStyle={TOOLTIP_ITEM_STYLE}
                  labelStyle={TOOLTIP_LABEL_STYLE}
                />
                <Legend wrapperStyle={LEGEND_STYLE} />
              </PieChart>
            </ResponsiveContainer>
          </Card>

          <Card>
            <h2 className="mb-2 font-semibold text-slate-100">Income vs Spending</h2>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={barData}>
                <XAxis dataKey="month" tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={AXIS_LINE} />
                <YAxis tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={AXIS_LINE} />
                <Tooltip
                  formatter={(v: number) => `$${v.toFixed(2)}`}
                  contentStyle={TOOLTIP_STYLE}
                  itemStyle={TOOLTIP_ITEM_STYLE}
                  labelStyle={TOOLTIP_LABEL_STYLE}
                  cursor={{ fill: "#1b2740", opacity: 0.5 }}
                />
                <Legend wrapperStyle={LEGEND_STYLE} />
                <Bar dataKey="Income" fill={SERIES.income} radius={[4, 4, 0, 0]} />
                <Bar dataKey="Spending" fill={SERIES.spending} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          <Card className="lg:col-span-2">
            <h2 className="mb-3 font-semibold text-slate-100">Top Categories</h2>
            <div className="divide-y divide-ink-700">
              {cats.map((c, i) => (
                <div key={c.category} className="flex items-center justify-between py-2.5">
                  <div className="flex items-center gap-2">
                    <span
                      className="h-3 w-3 rounded-full"
                      style={{ background: COLORS[i % COLORS.length] }}
                    />
                    <span className="font-medium text-slate-200">{titleCase(c.category)}</span>
                    <span className="text-xs text-slate-500">({c.txn_count} txns)</span>
                  </div>
                  <span className="font-mono font-semibold tnum text-slate-100">
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
