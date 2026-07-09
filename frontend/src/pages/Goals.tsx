import { useState } from "react";
import { CheckCircle2, AlertTriangle, Plus, Target, Trash2 } from "lucide-react";
import { useAccounts, useCreateGoal, useDeleteGoal, useGoals } from "../hooks/useApi";
import { Card, EmptyState, Loading, PageHeader } from "../components/ui";
import { formatMoney, formatDate } from "../lib/format";
import { ApiError } from "../lib/api";
import type { Goal } from "../lib/types";

const ASSET_TYPES = new Set(["depository", "checking", "savings", "investment", "cash"]);

function GoalCard({ goal, accountName }: { goal: Goal; accountName: (id: number) => string }) {
  const del = useDeleteGoal();
  const reached = goal.current_minor >= goal.target_minor;
  const pct = Math.min(goal.progress_pct, 100);

  return (
    <Card>
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2 font-semibold text-slate-100">
          <Target className="h-5 w-5 text-accent-soft" />
          {goal.name}
        </div>
        <div className="flex items-center gap-2">
          {reached ? (
            <span className="flex items-center gap-1 rounded border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-xs font-medium text-emerald-400">
              <CheckCircle2 className="h-3 w-3" /> reached
            </span>
          ) : goal.on_track === true ? (
            <span className="flex items-center gap-1 rounded border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-xs font-medium text-emerald-400">
              <CheckCircle2 className="h-3 w-3" /> on track
            </span>
          ) : goal.on_track === false ? (
            <span className="flex items-center gap-1 rounded border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 text-xs font-medium text-amber-400">
              <AlertTriangle className="h-3 w-3" /> behind
            </span>
          ) : null}
          <button
            onClick={() => del.mutate(goal.id)}
            className="text-slate-600 hover:text-red-500"
            title="Delete goal"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="mt-3 flex items-baseline justify-between">
        <span className="font-mono text-2xl font-bold tnum text-slate-100">
          {formatMoney(goal.current_minor)}
        </span>
        <span className="text-sm text-slate-400">of {formatMoney(goal.target_minor)}</span>
      </div>
      <div className="mt-2 h-2.5 w-full overflow-hidden rounded-full bg-ink-700">
        <div
          className={`h-full rounded-full ${reached ? "bg-emerald-500" : "bg-accent"}`}
          style={{ width: `${Math.max(pct, 2)}%` }}
        />
      </div>
      <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
        <span>{goal.progress_pct.toFixed(0)}% saved since {formatDate(goal.created_at)}</span>
        {goal.target_date && (
          <span>
            by {formatDate(goal.target_date)}
            {goal.required_monthly_minor !== null && goal.required_monthly_minor > 0 && (
              <> · needs {formatMoney(goal.required_monthly_minor)}/mo</>
            )}
          </span>
        )}
      </div>
      <div className="mt-2 text-xs text-slate-500">
        Funded by: {goal.account_ids.map(accountName).join(", ")}
      </div>
    </Card>
  );
}

function NewGoalForm() {
  const { data: accounts } = useAccounts();
  const create = useCreateGoal();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [target, setTarget] = useState("");
  const [dateStr, setDateStr] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const eligible = (accounts ?? []).filter((a) => ASSET_TYPES.has(a.account_type));
  const err = create.error instanceof ApiError ? create.error.message : null;

  const toggle = (id: number) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const submit = () => {
    const dollars = parseFloat(target);
    if (!name.trim() || isNaN(dollars) || dollars <= 0 || selected.size === 0) return;
    create.mutate(
      {
        name: name.trim(),
        target_minor: Math.round(dollars * 100),
        target_date: dateStr || null,
        account_ids: [...selected],
      },
      {
        onSuccess: () => {
          setOpen(false);
          setName("");
          setTarget("");
          setDateStr("");
          setSelected(new Set());
        },
      },
    );
  };

  if (!open) {
    return (
      <div className="mb-5">
        <button
          onClick={() => setOpen(true)}
          className="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" /> New goal
        </button>
      </div>
    );
  }

  return (
    <Card className="mb-5">
      <div className="mb-3 font-semibold text-slate-100">New goal</div>
      <div className="flex flex-wrap items-center gap-2">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Goal name (e.g. House down payment)"
          autoFocus
          className="min-w-[14rem] flex-1 rounded-lg border border-ink-700 px-3 py-2 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
        />
        <div className="relative">
          <span className="absolute left-2 top-1/2 -translate-y-1/2 text-sm text-slate-500">$</span>
          <input
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            inputMode="decimal"
            placeholder="25000"
            className="w-32 rounded-lg border border-ink-700 py-2 pl-5 pr-2 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </div>
        <input
          type="date"
          value={dateStr}
          onChange={(e) => setDateStr(e.target.value)}
          title="Target date (optional)"
          className="rounded-lg border border-ink-700 px-3 py-2 text-sm text-slate-400"
        />
      </div>
      <div className="mt-3 text-sm text-slate-400">Funded by:</div>
      <div className="mt-1.5 flex flex-wrap gap-2">
        {eligible.map((a) => (
          <button
            key={a.id}
            onClick={() => toggle(a.id)}
            className={`rounded-lg border px-3 py-1.5 text-sm ${
              selected.has(a.id)
                ? "border-accent bg-accent/15 text-accent-soft"
                : "border-ink-700 text-slate-400 hover:bg-ink-700/60"
            }`}
          >
            {a.name}
          </button>
        ))}
        {eligible.length === 0 && (
          <span className="text-sm text-slate-500">No asset accounts available yet.</span>
        )}
      </div>
      {err && <p className="mt-2 text-sm text-red-400">{err}</p>}
      <div className="mt-4 flex gap-2">
        <button
          onClick={submit}
          disabled={create.isPending || !name.trim() || !target || selected.size === 0}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {create.isPending ? "Creating…" : "Create goal"}
        </button>
        <button
          onClick={() => setOpen(false)}
          className="rounded-lg border border-ink-700 px-4 py-2 text-sm text-slate-400 hover:bg-ink-700/60"
        >
          Cancel
        </button>
      </div>
    </Card>
  );
}

export default function Goals() {
  const { data, isLoading } = useGoals();
  const { data: accounts } = useAccounts();
  if (isLoading) return <Loading />;
  const goals = data ?? [];
  const accountName = (id: number) => accounts?.find((a) => a.id === id)?.name ?? `#${id}`;

  return (
    <div>
      <PageHeader title="Goals" />
      <NewGoalForm />
      {goals.length === 0 ? (
        <EmptyState
          title="No goals yet"
          hint="Create a goal and link the accounts that fund it — progress tracks money saved from that moment on."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {goals.map((g) => (
            <GoalCard key={g.id} goal={g} accountName={accountName} />
          ))}
        </div>
      )}
    </div>
  );
}
