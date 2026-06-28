import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { usePortfolio } from "../hooks/useApi";
import { Card, EmptyState, Loading, PageHeader } from "../components/ui";
import { formatMoney, fromMinor } from "../lib/format";

const COLORS = [
  "#2563eb", "#7c3aed", "#db2777", "#ea580c", "#16a34a",
  "#0891b2", "#ca8a04", "#dc2626", "#4f46e5", "#0d9488",
];

export default function Investments() {
  const { data, isLoading } = usePortfolio();
  if (isLoading) return <Loading />;
  const p = data;
  const holdings = p?.holdings ?? [];

  const pieData = holdings
    .filter((h) => (h.market_value_minor ?? 0) > 0)
    .map((h) => ({ name: h.symbol || h.description || "?", value: fromMinor(h.market_value_minor ?? 0) }));

  return (
    <div>
      <PageHeader title="Investments" />
      {holdings.length === 0 ? (
        <EmptyState
          title="No holdings found"
          hint="Mark accounts as Investment and sync — holdings appear here when your provider reports them."
        />
      ) : (
        <>
          <div className="mb-5 grid grid-cols-1 gap-5 sm:grid-cols-3">
            <Card>
              <div className="text-sm font-medium text-slate-500">Total Value</div>
              <div className="mt-1 font-mono text-3xl font-bold tnum text-slate-900">
                {formatMoney(p?.total_value_minor ?? 0)}
              </div>
            </Card>
            <Card>
              <div className="text-sm font-medium text-slate-500">Holdings</div>
              <div className="mt-1 font-mono text-3xl font-bold tnum text-slate-900">
                {p?.holding_count ?? 0}
              </div>
            </Card>
            <Card>
              <div className="text-sm font-medium text-slate-500">Total Gain/Loss</div>
              <div className="mt-1 font-mono text-3xl font-bold tnum text-slate-400">
                {p?.total_gain_minor == null
                  ? "—"
                  : `${formatMoney(p.total_gain_minor)} (${(p.gain_pct ?? 0).toFixed(1)}%)`}
              </div>
            </Card>
          </div>

          <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
            <Card className="lg:col-span-1">
              <h2 className="mb-2 font-semibold text-slate-900">Allocation</h2>
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={95}>
                    {pieData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v: number) => `$${v.toFixed(2)}`} />
                </PieChart>
              </ResponsiveContainer>
            </Card>

            <Card className="lg:col-span-2 overflow-hidden p-0">
              <table className="w-full text-sm">
                <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wider text-slate-500">
                  <tr>
                    <th className="px-5 py-3 font-semibold">Holding</th>
                    <th className="px-5 py-3 font-semibold">Account</th>
                    <th className="px-5 py-3 text-right font-semibold">Shares</th>
                    <th className="px-5 py-3 text-right font-semibold">Value</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {holdings.map((h) => (
                    <tr key={h.id} className="hover:bg-slate-50">
                      <td className="px-5 py-3">
                        <div className="font-medium text-slate-800">{h.symbol || "—"}</div>
                        <div className="max-w-[220px] truncate text-xs text-slate-400">
                          {h.description}
                        </div>
                      </td>
                      <td className="max-w-[160px] truncate px-5 py-3 text-slate-500">
                        {h.account_name}
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 text-right font-mono tnum text-slate-500">
                        {h.shares ?? "—"}
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 text-right font-mono font-semibold tnum text-slate-900">
                        {formatMoney(h.market_value_minor ?? 0, h.currency)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          </div>
          {p?.total_gain_minor == null && (
            <p className="mt-3 text-xs text-slate-400">
              Gain/loss is unavailable because your provider didn't report cost basis for these
              holdings.
            </p>
          )}
        </>
      )}
    </div>
  );
}
