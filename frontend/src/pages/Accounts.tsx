import { useState } from "react";
import { Target, Check, X } from "lucide-react";
import { useAccounts, useUpdateAccountSettings } from "../hooks/useApi";
import { Card, EmptyState, Loading, PageHeader } from "../components/ui";
import { formatMoney, formatDate } from "../lib/format";
import type { Account } from "../lib/types";

const ROLES = [
  { value: "depository", label: "Bank" },
  { value: "checking", label: "Checking" },
  { value: "savings", label: "Savings" },
  { value: "investment", label: "Investment" },
  { value: "cash", label: "Cash" },
  { value: "credit", label: "Credit" },
  { value: "loan", label: "Loan" },
  { value: "other", label: "Other" },
];

const ASSET_ROLES = new Set(["depository", "checking", "savings", "investment", "cash"]);

function GoalSection({ account }: { account: Account }) {
  const update = useUpdateAccountSettings();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(account.goal_name ?? "");
  const [amt, setAmt] = useState(
    account.goal_target_minor ? String(account.goal_target_minor / 100) : "",
  );

  const hasGoal = (account.goal_target_minor ?? 0) > 0;
  const target = account.goal_target_minor ?? 0;
  const pct = hasGoal ? (account.balance_minor / target) * 100 : 0;
  const reached = hasGoal && account.balance_minor >= target;
  const remaining = Math.max(target - account.balance_minor, 0);

  const save = () => {
    const dollars = parseFloat(amt);
    if (isNaN(dollars) || dollars <= 0) return;
    update.mutate(
      { id: account.id, goal_name: name || null, goal_target_minor: Math.round(dollars * 100) },
      { onSuccess: () => setEditing(false) },
    );
  };
  const clear = () =>
    update.mutate({ id: account.id, goal_name: null, goal_target_minor: null });

  if (editing) {
    return (
      <div className="mt-3 space-y-2 rounded-lg bg-slate-50 p-3">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Goal name (e.g. Emergency Fund)"
          className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
        />
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <span className="absolute left-2 top-1/2 -translate-y-1/2 text-sm text-slate-400">$</span>
            <input
              value={amt}
              onChange={(e) => setAmt(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && save()}
              inputMode="decimal"
              placeholder="10000"
              className="w-full rounded border border-slate-300 py-1.5 pl-5 pr-2 text-sm"
            />
          </div>
          <button onClick={save} className="rounded bg-accent p-1.5 text-white hover:bg-blue-700">
            <Check className="h-4 w-4" />
          </button>
          <button
            onClick={() => setEditing(false)}
            className="rounded border border-slate-300 p-1.5 text-slate-500 hover:bg-white"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
    );
  }

  if (!hasGoal) {
    return (
      <button
        onClick={() => setEditing(true)}
        className="mt-3 flex items-center gap-1.5 text-sm font-medium text-accent hover:underline"
      >
        <Target className="h-4 w-4" />
        Set savings goal
      </button>
    );
  }

  return (
    <div className="mt-3">
      <div className="flex items-center justify-between text-sm">
        <span className="flex items-center gap-1.5 font-medium text-slate-700">
          <Target className="h-4 w-4 text-accent" />
          {account.goal_name || "Savings goal"}
        </span>
        <span className="font-mono tnum text-slate-500">
          {formatMoney(account.balance_minor)} / {formatMoney(target)}
        </span>
      </div>
      <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className={`h-full rounded-full ${reached ? "bg-emerald-500" : "bg-accent"}`}
          style={{ width: `${Math.min(Math.max(pct, 0), 100)}%` }}
        />
      </div>
      <div className="mt-1.5 flex items-center justify-between text-xs">
        <span className={reached ? "font-medium text-emerald-600" : "text-slate-500"}>
          {reached ? "🎉 Goal reached!" : `${pct.toFixed(0)}% — ${formatMoney(remaining)} to go`}
        </span>
        <div className="flex gap-3">
          <button onClick={() => setEditing(true)} className="text-accent hover:underline">
            Edit
          </button>
          <button onClick={clear} className="text-slate-400 hover:text-red-500">
            Remove
          </button>
        </div>
      </div>
    </div>
  );
}

function AccountCard({ account }: { account: Account }) {
  const update = useUpdateAccountSettings();
  return (
    <Card>
      <div className="flex items-start justify-between">
        <div>
          <div className="font-semibold text-slate-900">{account.name}</div>
          <div className="text-xs text-slate-400">{account.org_name ?? "—"}</div>
        </div>
        <select
          value={account.account_type}
          onChange={(e) => update.mutate({ id: account.id, type_override: e.target.value })}
          className="rounded border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-600"
        >
          {ROLES.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
      </div>
      <div
        className={`mt-4 font-mono text-2xl font-bold tnum ${
          account.balance_minor < 0 ? "text-red-500" : "text-slate-900"
        }`}
      >
        {formatMoney(account.balance_minor, account.currency)}
      </div>
      <div className="mt-1 text-xs text-slate-400">As of {formatDate(account.balance_date)}</div>
      {ASSET_ROLES.has(account.account_type) && <GoalSection account={account} />}
    </Card>
  );
}

export default function Accounts() {
  const { data, isLoading } = useAccounts();
  if (isLoading) return <Loading />;
  const accounts = data ?? [];

  return (
    <div>
      <PageHeader title="Accounts" />
      {accounts.length === 0 ? (
        <EmptyState title="No accounts linked yet" hint="Connect a bank in Settings, then Sync." />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {accounts.map((a) => (
            <AccountCard key={a.id} account={a} />
          ))}
        </div>
      )}
    </div>
  );
}
