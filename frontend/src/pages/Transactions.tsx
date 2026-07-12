import { Fragment, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowLeftRight,
  ChevronLeft,
  ChevronRight,
  CornerDownRight,
  FileUp,
  NotebookPen,
  Plus,
  Search,
  Split,
  Tag,
  Trash2,
} from "lucide-react";
import {
  useAccounts,
  useAnnotateTransaction,
  useSetCategory,
  useSplitTransaction,
  useTransactions,
  useUnsplitTransaction,
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

/** Inline editor: divide one charge across categories. Amounts are entered as
 * positive dollars; the original's direction is applied on save.
 * Exported for component tests. */
export function SplitRow({
  txn,
  children,
  onDone,
}: {
  txn: Transaction;
  children: Transaction[];
  onDone: () => void;
}) {
  const split = useSplitTransaction();
  const unsplit = useUnsplitTransaction();
  const totalAbs = Math.abs(txn.amount_minor);
  const sign = txn.amount_minor < 0 ? -1 : 1;
  const toDollars = (minor: number) => (Math.abs(minor) / 100).toFixed(2);

  const [parts, setParts] = useState<{ category: string; amount: string }[]>(() =>
    children.length > 0
      ? children.map((c) => ({ category: c.category, amount: toDollars(c.amount_minor) }))
      : [
          { category: txn.category, amount: toDollars(txn.amount_minor) },
          { category: "uncategorized", amount: "0.00" },
        ],
  );

  const minorOf = (s: string) => {
    const v = Math.round(parseFloat(s) * 100);
    return Number.isFinite(v) ? Math.abs(v) : NaN;
  };
  const assigned = parts.reduce((sum, p) => sum + (minorOf(p.amount) || 0), 0);
  const remainder = totalAbs - assigned;
  const valid =
    remainder === 0 && parts.length >= 2 && parts.every((p) => (minorOf(p.amount) || 0) > 0);

  const update = (i: number, patch: Partial<{ category: string; amount: string }>) =>
    setParts((prev) => prev.map((p, j) => (j === i ? { ...p, ...patch } : p)));

  const save = () =>
    split.mutate(
      {
        id: txn.id,
        parts: parts.map((p) => ({ category: p.category, amount_minor: sign * minorOf(p.amount) })),
      },
      { onSuccess: onDone },
    );

  return (
    <tr className="bg-ink-900/60">
      <td colSpan={6} className="px-5 py-3">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <span className="text-sm font-medium text-slate-300">
            Split {formatMoney(sign * totalAbs)}
          </span>
          {parts.map((p, i) => (
            <span key={i} className="flex items-center gap-1.5">
              <select
                value={p.category}
                onChange={(e) => update(i, { category: e.target.value })}
                className="rounded border border-ink-700 bg-ink-800 px-2 py-1 text-xs text-slate-300"
              >
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {titleCase(c)}
                  </option>
                ))}
              </select>
              <span className="text-xs text-slate-500">$</span>
              <input
                value={p.amount}
                onChange={(e) => update(i, { amount: e.target.value })}
                inputMode="decimal"
                className="w-20 rounded-lg border border-ink-700 px-2 py-1 text-right font-mono text-xs tnum"
              />
              {parts.length > 2 && (
                <button
                  onClick={() => setParts((prev) => prev.filter((_, j) => j !== i))}
                  className="text-slate-600 hover:text-red-400"
                  title="Remove part"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              )}
            </span>
          ))}
          <button
            onClick={() => setParts((prev) => [...prev, { category: "uncategorized", amount: "0.00" }])}
            className="flex items-center gap-1 rounded-lg border border-ink-700 px-2 py-1 text-xs text-slate-400 hover:bg-ink-700/60"
          >
            <Plus className="h-3.5 w-3.5" /> Part
          </button>
          <span
            className={`font-mono text-xs tnum ${remainder === 0 ? "text-emerald-400" : "text-amber-400"}`}
          >
            {remainder === 0 ? "✓ adds up" : `${formatMoney(-sign * remainder)} left to assign`}
          </span>
          <button
            onClick={save}
            disabled={!valid || split.isPending}
            className="rounded-lg bg-accent px-3 py-1.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {txn.is_split_parent ? "Update split" : "Split"}
          </button>
          {txn.is_split_parent && (
            <button
              onClick={() => unsplit.mutate(txn.id, { onSuccess: onDone })}
              disabled={unsplit.isPending}
              className="rounded-lg border border-ink-700 px-3 py-1.5 text-sm text-slate-400 hover:bg-ink-700/60"
            >
              Unsplit
            </button>
          )}
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
  const [splittingId, setSplittingId] = useState<number | null>(null);
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

  // Split children render indented under their parent, not as standalone rows.
  const { all, childrenBy } = useMemo(() => {
    const txns = data ?? [];
    const byParent = new Map<number, Transaction[]>();
    for (const t of txns) {
      if (t.parent_id != null) {
        byParent.set(t.parent_id, [...(byParent.get(t.parent_id) ?? []), t]);
      }
    }
    return { all: txns.filter((t) => t.parent_id == null), childrenBy: byParent };
  }, [data]);
  const total = all.length;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  // Render-time state adjustments (no effects): snap back to page 1 when the
  // filters change, and keep the page in range if the list shrinks.
  const [prevFilter, setPrevFilter] = useState({ accountId, q });
  if (prevFilter.accountId !== accountId || prevFilter.q !== q) {
    setPrevFilter({ accountId, q });
    setPage(1);
  }
  if (page > totalPages) setPage(totalPages);

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
                      <div className="flex items-center gap-2 font-medium text-slate-200">
                        {t.payee || t.description || "—"}
                        {t.transfer_peer_id != null && (
                          <span
                            title="Matched internal transfer — excluded from income & spending"
                            className="flex items-center gap-1 rounded bg-ink-900/70 px-1.5 py-0.5 text-[11px] font-medium text-slate-400"
                          >
                            <ArrowLeftRight className="h-3 w-3" /> transfer
                          </span>
                        )}
                        {t.is_split_parent && (
                          <span
                            title="Split into parts below — the parts count, this row doesn't"
                            className="flex items-center gap-1 rounded bg-accent/15 px-1.5 py-0.5 text-[11px] font-medium text-accent-soft"
                          >
                            <Split className="h-3 w-3" /> split
                          </span>
                        )}
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
                            t.is_split_parent
                              ? "text-slate-600 line-through" // parts below carry the money
                              : cf < 0
                                ? "text-red-400"
                                : "text-emerald-400"
                          }`}
                        >
                          {formatMoney(cf)}
                        </td>
                      );
                    })()}
                    <td className="whitespace-nowrap px-2 py-3 text-center">
                      <button
                        onClick={() => setEditingId(editingId === t.id ? null : t.id)}
                        title={t.note || t.tags.length ? "Edit note & tags" : "Add note & tags"}
                        className={`${
                          t.note || t.tags.length ? "text-accent-soft" : "text-slate-600"
                        } hover:text-accent-soft`}
                      >
                        <NotebookPen className="h-4 w-4" />
                      </button>
                      {!t.pending && (
                        <button
                          onClick={() => setSplittingId(splittingId === t.id ? null : t.id)}
                          title={t.is_split_parent ? "Edit split" : "Split across categories"}
                          className={`ml-1.5 ${
                            t.is_split_parent ? "text-accent-soft" : "text-slate-600"
                          } hover:text-accent-soft`}
                        >
                          <Split className="h-4 w-4" />
                        </button>
                      )}
                    </td>
                  </tr>
                  {editingId === t.id && (
                    <AnnotateRow txn={t} onDone={() => setEditingId(null)} />
                  )}
                  {splittingId === t.id && (
                    <SplitRow
                      txn={t}
                      children={childrenBy.get(t.id) ?? []}
                      onDone={() => setSplittingId(null)}
                    />
                  )}
                  {(childrenBy.get(t.id) ?? []).map((c) => (
                    <tr key={c.id} className="bg-ink-900/40 text-sm">
                      <td className="px-5 py-2" />
                      <td className="px-5 py-2">
                        <div className="flex items-center gap-2 text-slate-400">
                          <CornerDownRight className="h-3.5 w-3.5 text-slate-600" />
                          {c.note || titleCase(c.category)}
                        </div>
                      </td>
                      <td className="px-5 py-2" />
                      <td className="px-5 py-2">
                        <select
                          value={c.category}
                          onChange={(e) =>
                            setCategory.mutate({ id: c.id, category: e.target.value })
                          }
                          className="rounded border border-ink-700 bg-ink-800 px-2 py-1 text-xs text-slate-400"
                        >
                          {CATEGORIES.map((cat) => (
                            <option key={cat} value={cat}>
                              {titleCase(cat)}
                            </option>
                          ))}
                        </select>
                      </td>
                      {(() => {
                        const cf = cashFlowMinor(c.amount_minor, acctType(c.account_id));
                        return (
                          <td
                            className={`whitespace-nowrap px-5 py-2 text-right font-mono tnum ${
                              cf < 0 ? "text-red-400/80" : "text-emerald-400/80"
                            }`}
                          >
                            {formatMoney(cf)}
                          </td>
                        );
                      })()}
                      <td className="px-2 py-2" />
                    </tr>
                  ))}
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
