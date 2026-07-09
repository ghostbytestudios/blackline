import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useAccounts, useSetCategory, useTransactions } from "../hooks/useApi";
import { Card, EmptyState, Loading, PageHeader } from "../components/ui";
import { formatMoney, formatDate, titleCase, cashFlowMinor } from "../lib/format";

const CATEGORIES = [
  "groceries", "dining", "transport", "travel", "shopping", "subscriptions",
  "entertainment", "utilities", "housing", "health", "insurance", "loans",
  "interest", "income", "transfer", "atm", "fees", "uncategorized",
];

const PAGE_SIZE = 25;

/** Compact page-number window centered on the current page (with first/last). */
function pageWindow(current: number, total: number): (number | "…")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const pages: (number | "…")[] = [1];
  const lo = Math.max(2, current - 1);
  const hi = Math.min(total - 1, current + 1);
  if (lo > 2) pages.push("…");
  for (let p = lo; p <= hi; p++) pages.push(p);
  if (hi < total - 1) pages.push("…");
  pages.push(total);
  return pages;
}

export default function Transactions() {
  const [accountId, setAccountId] = useState<number | undefined>(undefined);
  const [page, setPage] = useState(1);
  const accounts = useAccounts();
  const { data, isLoading } = useTransactions({ accountId, limit: 1000 });
  const setCategory = useSetCategory();

  const all = useMemo(() => data ?? [], [data]);
  const total = all.length;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  // Reset to the first page whenever the account filter changes.
  useEffect(() => setPage(1), [accountId]);
  // Keep the page in range if the underlying list shrinks (e.g. after re-categorizing).
  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  const startIdx = (page - 1) * PAGE_SIZE;
  const rows = all.slice(startIdx, startIdx + PAGE_SIZE);

  const acctName = (id: number) =>
    accounts.data?.find((a) => a.id === id)?.name ?? "Account";
  const acctType = (id: number) => accounts.data?.find((a) => a.id === id)?.account_type;

  return (
    <div>
      <PageHeader
        title="Transactions"
        action={
          <select
            value={accountId ?? ""}
            onChange={(e) => setAccountId(e.target.value ? Number(e.target.value) : undefined)}
            className="rounded-lg border border-ink-700 px-3 py-2 text-sm"
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
      ) : total === 0 ? (
        <EmptyState title="No transactions" hint="Sync an account to populate your ledger." />
      ) : (
        <Card className="overflow-hidden p-0">
          <table className="w-full text-sm">
            <thead className="border-b border-ink-700 bg-ink-900/60 text-left text-xs uppercase tracking-wider text-slate-400">
              <tr>
                <th className="px-5 py-3 font-semibold">Date</th>
                <th className="px-5 py-3 font-semibold">Description</th>
                <th className="px-5 py-3 font-semibold">Account</th>
                <th className="px-5 py-3 font-semibold">Category</th>
                <th className="px-5 py-3 text-right font-semibold">Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-700">
              {rows.map((t) => (
                <tr key={t.id} className="hover:bg-ink-700/60">
                  <td className="whitespace-nowrap px-5 py-3 text-slate-400">
                    {formatDate(t.posted_at)}
                  </td>
                  <td className="px-5 py-3">
                    <div className="font-medium text-slate-200">
                      {t.payee || t.description || "—"}
                    </div>
                    {t.pending && <span className="text-xs text-amber-400">pending</span>}
                  </td>
                  <td className="px-5 py-3 text-slate-400">{acctName(t.account_id)}</td>
                  <td className="px-5 py-3">
                    <select
                      value={t.category}
                      onChange={(e) => setCategory.mutate({ id: t.id, category: e.target.value })}
                      className="rounded border border-ink-700 bg-ink-800 px-2 py-1 text-xs text-slate-300"
                    >
                      {CATEGORIES.map((c) => (
                        <option key={c} value={c}>
                          {titleCase(c)}
                        </option>
                      ))}
                    </select>
                  </td>
                  {(() => {
                    const cf = cashFlowMinor(t.amount_minor, acctType(t.account_id));
                    return (
                      <td
                        className={`whitespace-nowrap px-5 py-3 text-right font-mono font-semibold tnum ${
                          cf < 0 ? "text-red-500" : "text-emerald-400"
                        }`}
                      >
                        {formatMoney(cf)}
                      </td>
                    );
                  })()}
                </tr>
              ))}
            </tbody>
          </table>

          <div className="flex flex-col items-center justify-between gap-3 border-t border-ink-700 px-5 py-3 text-sm sm:flex-row">
            <span className="text-slate-400">
              Showing {startIdx + 1}–{Math.min(startIdx + PAGE_SIZE, total)} of {total}
            </span>
            {totalPages > 1 && (
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="flex items-center gap-1 rounded-lg border border-ink-700 px-2.5 py-1.5 font-medium text-slate-400 hover:bg-ink-700/60 disabled:opacity-40"
                >
                  <ChevronLeft className="h-4 w-4" /> Prev
                </button>
                {pageWindow(page, totalPages).map((p, i) =>
                  p === "…" ? (
                    <span key={`gap-${i}`} className="px-1.5 text-slate-500">
                      …
                    </span>
                  ) : (
                    <button
                      key={p}
                      onClick={() => setPage(p)}
                      className={`min-w-[2rem] rounded-lg px-2.5 py-1.5 font-medium ${
                        p === page
                          ? "bg-accent text-white"
                          : "border border-ink-700 text-slate-400 hover:bg-ink-700/60"
                      }`}
                    >
                      {p}
                    </button>
                  ),
                )}
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="flex items-center gap-1 rounded-lg border border-ink-700 px-2.5 py-1.5 font-medium text-slate-400 hover:bg-ink-700/60 disabled:opacity-40"
                >
                  Next <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
