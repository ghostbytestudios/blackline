import { useState } from "react";
import { Link } from "react-router-dom";
import { Store } from "lucide-react";
import { useMerchants } from "../hooks/useApi";
import { Card, CategoryChip, EmptyState, Loading, PageHeader } from "../components/ui";
import { formatMoney, formatDate } from "../lib/format";

const WINDOWS = [
  { days: 90, label: "90 days" },
  { days: 180, label: "6 months" },
  { days: 365, label: "12 months" },
];

export default function Merchants() {
  const [days, setDays] = useState(365);
  const { data, isLoading } = useMerchants(days);
  if (isLoading) return <Loading />;
  const merchants = data ?? [];
  const total = merchants.reduce((s, m) => s + m.total_minor, 0);

  return (
    <div>
      <PageHeader
        title="Merchants"
        action={
          <div className="flex gap-1 rounded-lg border border-ink-700 p-1">
            {WINDOWS.map((w) => (
              <button
                key={w.days}
                onClick={() => setDays(w.days)}
                className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                  days === w.days ? "bg-accent text-white" : "text-slate-400 hover:bg-ink-700/60"
                }`}
              >
                {w.label}
              </button>
            ))}
          </div>
        }
      />

      {merchants.length === 0 ? (
        <EmptyState
          title="No merchants yet"
          hint="Merchants appear once a payee shows up at least twice in the selected window."
        />
      ) : (
        <>
          <div className="mb-5 grid grid-cols-1 gap-5 sm:grid-cols-3">
            <Card>
              <div className="text-sm font-medium text-slate-400">Merchants</div>
              <div className="mt-1 font-mono text-3xl font-bold tnum text-slate-100">
                {merchants.length}
              </div>
            </Card>
            <Card>
              <div className="text-sm font-medium text-slate-400">Total spend</div>
              <div className="mt-1 font-mono text-3xl font-bold tnum text-slate-100">
                {formatMoney(total)}
              </div>
            </Card>
            <Card>
              <div className="text-sm font-medium text-slate-400">Top merchant</div>
              <div className="mt-1 truncate font-mono text-3xl font-bold tnum text-slate-100">
                {merchants[0]?.name ?? "—"}
              </div>
            </Card>
          </div>

          <Card className="overflow-hidden p-0">
            <table className="w-full text-sm">
              <thead className="border-b border-ink-700 bg-ink-900/60 text-left text-xs uppercase tracking-wider text-slate-400">
                <tr>
                  <th className="px-5 py-3 font-semibold">Merchant</th>
                  <th className="px-5 py-3 font-semibold">Category</th>
                  <th className="px-5 py-3 text-right font-semibold">Visits</th>
                  <th className="px-5 py-3 text-right font-semibold">Avg / visit</th>
                  <th className="px-5 py-3 text-right font-semibold">~ / month</th>
                  <th className="px-5 py-3 text-right font-semibold">Total</th>
                  <th className="px-5 py-3 font-semibold">Last seen</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-700">
                {merchants.map((m) => (
                  <tr key={m.name} className="hover:bg-ink-700/60">
                    <td className="px-5 py-3">
                      <Link
                        to={`/transactions?q=${encodeURIComponent(m.name)}`}
                        className="flex items-center gap-2 font-medium text-slate-200 hover:text-accent-soft"
                        title="View transactions"
                      >
                        <Store className="h-4 w-4 shrink-0 text-accent-soft" />
                        <span className="max-w-[220px] truncate">{m.name}</span>
                      </Link>
                    </td>
                    <td className="px-5 py-3">
                      <CategoryChip category={m.category} />
                    </td>
                    <td className="px-5 py-3 text-right font-mono tnum text-slate-400">
                      {m.txn_count}
                    </td>
                    <td className="px-5 py-3 text-right font-mono tnum text-slate-400">
                      {formatMoney(m.avg_txn_minor)}
                    </td>
                    <td className="px-5 py-3 text-right font-mono tnum text-slate-300">
                      {formatMoney(m.monthly_avg_minor)}
                    </td>
                    <td className="px-5 py-3 text-right font-mono font-semibold tnum text-slate-100">
                      {formatMoney(m.total_minor)}
                    </td>
                    <td className="whitespace-nowrap px-5 py-3 text-slate-400">
                      {formatDate(m.last_date)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </div>
  );
}
