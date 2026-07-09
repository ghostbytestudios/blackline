import { Fragment, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ChevronLeft, ChevronRight, FileUp, NotebookPen, Search, Tag } from "lucide-react";
import {
  useAccounts,
  useAnnotateTransaction,
  useSetCategory,
  useTransactions,
} from "../hooks/useApi";
import { Card, EmptyState, Loading, PageHeader } from "../components/ui";
import { formatMoney, formatDate, titleCase, cashFlowMinor } from "../lib/format";
import type { Transaction } from "../lib/types";

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

function AnnotateRow({ txn, onDone }: { txn: Transaction; onDone: () => void }) {
  const annotate = useAnnotateTransaction();
  const [note, setNote] = useState(txn.note ?? "");
  const [tags, setTags] = useState(txn.tags.join(", "));

  const save = () =>
    annotate.mutate(
      {
        id: txn.id,
        note,
        tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
      },
      { onSuccess: onDone },
    );

  return (
    <tr className="bg-ink-900/60">
      <td colSpan={6} className="px-5 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && save()}
            placeholder="Add a note…"
            autoFocus
            className="min-w-[16rem] flex-1 rounded-lg border border-ink-700 px-3 py-1.5 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          />
          <div className="relative">
            <Tag className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
            <input
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && save()}
              placeholder="tags, comma, separated"
              className="w-56 rounded-lg border border-ink-700 py-1.5 pl-7 pr-3 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </div>
          <button
            onClick={save}
            disabled={annotate.isPending}
            className="rounded-lg bg-accent px-3 py-1.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
          >
            Save
          </button>
          <button
            onClick={onDone}
            className="rounded-lg border border-ink-700 px-3 py-1.5 text-sm text-slate-400 hover:bg-ink-700/60"
          >
            Cancel
          </button>
        </div>
      </td>
    </tr>
  );
}

export default function Transactions() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [accountId, setAccountId] = useState<number | undefined>(undefined);
  const [qInput, setQInput] = useState(searchParams.get("q") ?? "");
  const [q, setQ] = useState(qInput);
  const [page, setPage] = useState(1);
  const [editingId, setEditingId] = useState<number | null>(null);
  const accounts = useAccounts();
  const { data, isLoading } = useTransactions({ accountId, q: q || undefined, limit: 1000 });
  const setCategory = useSetCategory();

  // Debounce typing into the actual query (and keep it shareable via the URL).
  useEffect(() => {
    const handle = setTimeout(() => {
      setQ(qInput.trim());
      setSearchParams(qInput.trim() ? { q: qInput.trim() } : {}, { replace: true });
    }, 300);
    return () => clearTimeout(handle);
  }, [qInput, setSearchParams]);

  const all = useMemo(() => data ?? [], [data]);
  const total = all.length;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  // Reset to the first page whenever the filters change.
  useEffect(() => setPage(1), [accountId, q]);
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
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
              <input
                value={qInput}
                onChange={(e) => setQInput(e.target.value)}
                placeholder="Search payee, description, notes…"
                className="w-72 rounded-lg border border-ink-700 py-2 pl-8 pr-3 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
              />
            </div>
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
            <Link
              to="/import"
              className="flex items-center gap-1.5 rounded-lg border border-ink-700 px-3 py-2 text-sm text-slate-400 hover:bg-ink-700/60 hover:text-slate-200"
            >
              <FileUp className="h-4 w-4" /> Import
            </Link>
          </div>
        }
      />

      {isLoading ? (
        <Loading />
      ) : total === 0 ? (
        <EmptyState
          title={q ? "No matches" : "No transactions"}
          hint={q ? "Try a different search." : "Sync an account to populate your ledger."}
        />
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
                <th className="w-10 px-2 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-700">
              {rows.map((t) => (
                <Fragment key={t.id}>
                  <tr className="hover:bg-ink-700/60">
                    <td className="whitespace-nowrap px-5 py-3 text-slate-400">
                      {formatDate(t.posted_at)}
                    </td>
                    <td className="px-5 py-3">
                      <div className="font-medium text-slate-200">
                        {t.payee || t.description || "—"}
                      </div>
                      {t.pending && <span className="text-xs text-amber-400">pending</span>}
                      {t.note && (
                        <div className="mt-0.5 max-w-[28rem] truncate text-xs italic text-slate-500">
                          {t.note}
                        </div>
                      )}
                      {t.tags.length > 0 && (
                        <div className="mt-1 flex flex-wrap gap-1">
                          {t.tags.map((tag) => (
                            <span
                              key={tag}
                              className="rounded bg-accent/15 px-1.5 py-0.5 text-[11px] font-medium text-accent-soft"
                            >
                              #{tag}
                            </span>
                          ))}
                        </div>
                      )}
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
                            cf < 0 ? "text-red-400" : "text-emerald-400"
                          }`}
                        >
                          {formatMoney(cf)}
                        </td>
                      );
                    })()}
                    <td className="px-2 py-3 text-center">
                      <button
                        onClick={() => setEditingId(editingId === t.id ? null : t.id)}
                        title={t.note || t.tags.length ? "Edit note & tags" : "Add note & tags"}
                        className={`${
                          t.note || t.tags.length ? "text-accent-soft" : "text-slate-600"
                        } hover:text-accent-soft`}
                      >
                        <NotebookPen className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                  {editingId === t.id && (
                    <AnnotateRow txn={t} onDone={() => setEditingId(null)} />
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>

          <div className="flex flex-col items-center justify-between gap-3 border-t border-ink-700 px-5 py-3 text-sm sm:flex-row">
            <span className="text-slate-400">
              Showing {startIdx + 1}–{Math.min(startIdx + PAGE_SIZE, total)} of {total}
              {q && <> for “{q}”</>}
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
