import { useState } from "react";
import { useAccounts, useSetCategory, useTransactions } from "../hooks/useApi";
import { Card, EmptyState, Loading, PageHeader } from "../components/ui";
import { formatMoney, formatDate, titleCase } from "../lib/format";

const CATEGORIES = [
  "groceries", "dining", "transport", "travel", "shopping", "subscriptions",
  "entertainment", "utilities", "housing", "health", "insurance", "loans",
  "income", "transfer", "atm", "fees", "uncategorized",
];

export default function Transactions() {
  const [accountId, setAccountId] = useState<number | undefined>(undefined);
  const accounts = useAccounts();
  const { data, isLoading } = useTransactions({ accountId });
  const setCategory = useSetCategory();

  const acctName = (id: number) =>
    accounts.data?.find((a) => a.id === id)?.name ?? "Account";

  return (
    <div>
      <PageHeader
        title="Transactions"
        action={
          <select
            value={accountId ?? ""}
            onChange={(e) => setAccountId(e.target.value ? Number(e.target.value) : undefined)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="">All accounts</option>
            {(accounts.data ?? []).map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        }
      />

      {isLoading ? (
        <Loading />
      ) : (data ?? []).length === 0 ? (
        <EmptyState title="No transactions" hint="Sync an account to populate your ledger." />
      ) : (
        <Card className="overflow-hidden p-0">
          <table className="w-full text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-5 py-3 font-semibold">Date</th>
                <th className="px-5 py-3 font-semibold">Description</th>
                <th className="px-5 py-3 font-semibold">Account</th>
                <th className="px-5 py-3 font-semibold">Category</th>
                <th className="px-5 py-3 text-right font-semibold">Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(data ?? []).map((t) => (
                <tr key={t.id} className="hover:bg-slate-50">
                  <td className="whitespace-nowrap px-5 py-3 text-slate-500">
                    {formatDate(t.posted_at)}
                  </td>
                  <td className="px-5 py-3">
                    <div className="font-medium text-slate-800">
                      {t.payee || t.description || "—"}
                    </div>
                    {t.pending && <span className="text-xs text-amber-600">pending</span>}
                  </td>
                  <td className="px-5 py-3 text-slate-500">{acctName(t.account_id)}</td>
                  <td className="px-5 py-3">
                    <select
                      value={t.category}
                      onChange={(e) => setCategory.mutate({ id: t.id, category: e.target.value })}
                      className="rounded border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700"
                    >
                      {CATEGORIES.map((c) => (
                        <option key={c} value={c}>
                          {titleCase(c)}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td
                    className={`whitespace-nowrap px-5 py-3 text-right font-mono font-semibold tnum ${
                      t.amount_minor < 0 ? "text-red-500" : "text-emerald-600"
                    }`}
                  >
                    {formatMoney(t.amount_minor)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
