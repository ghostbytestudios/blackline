import { Area, AreaChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { usePortfolio, usePortfolioHistory } from "../hooks/useApi";
import { Card, EmptyState, Loading, PageHeader } from "../components/ui";
import { formatMoney, formatDate, fromMinor } from "../lib/format";
import { AXIS_LINE, AXIS_TICK, SERIES, TOOLTIP_ITEM_STYLE, TOOLTIP_LABEL_STYLE, TOOLTIP_STYLE } from "../lib/chartTheme";

const COLORS = [
  "#2563eb", "#7c3aed", "#db2777", "#ea580c", "#16a34a",
  "#0891b2", "#ca8a04", "#dc2626", "#4f46e5", "#0d9488",
];

function ValueHistoryCard() {
  const { data } = usePortfolioHistory();
  const points = data ?? [];
  if (points.length < 2) return null;
  const series = points.map((pt) => ({
    label: formatDate(pt.as_of),
    Value: fromMinor(pt.total_value_minor),
    Cost: fromMinor(pt.total_cost_minor),
  }));

  return (
    <Card className="mt-5">
      <h2 className="mb-2 font-semibold text-slate-100">Portfolio value</h2>
      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={series}>
          <defs>
            <linearGradient id="pv" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={SERIES.primary} stopOpacity={0.3} />
              <stop offset="100%" stopColor={SERIES.primary} stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis dataKey="label" tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={AXIS_LINE} />
          <YAxis tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={AXIS_LINE} domain={["auto", "auto"]} />
          <Tooltip
            formatter={(v) => `$${Number(v).toFixed(2)}`}
            contentStyle={TOOLTIP_STYLE}
            itemStyle={TOOLTIP_ITEM_STYLE}
            labelStyle={TOOLTIP_LABEL_STYLE}
          />
          <Area type="monotone" dataKey="Value" stroke={SERIES.primary} strokeWidth={2} fill="url(#pv)" />
          <Area type="monotone" dataKey="Cost" stroke={SERIES.compare} strokeWidth={1.5} strokeDasharray="4 3" fill="none" />
        </AreaChart>
      </ResponsiveContainer>
      <p className="mt-1 text-xs text-slate-500">
        A value point is recorded on each sync; the dashed line is your cost basis.
      </p>
    </Card>
  );
}

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
              <div className="text-sm font-medium text-slate-400">Total Value</div>
              <div className="mt-1 font-mono text-3xl font-bold tnum text-slate-100">
                {formatMoney(p?.total_value_minor ?? 0)}
              </div>
            </Card>
            <Card>
              <div className="text-sm font-medium text-slate-400">Holdings</div>
              <div className="mt-1 font-mono text-3xl font-bold tnum text-slate-100">
                {p?.holding_count ?? 0}
              </div>
            </Card>
            <Card>
              <div className="text-sm font-medium text-slate-400">Total Gain/Loss</div>
              <div
                className={`mt-1 font-mono text-3xl font-bold tnum ${
                  p?.total_gain_minor == null
                    ? "text-slate-500"
                    : p.total_gain_minor >= 0
                      ? "text-emerald-400"
                      : "text-red-400"
                }`}
              >
                {p?.total_gain_minor == null
                  ? "—"
                  : `${p.total_gain_minor >= 0 ? "+" : ""}${formatMoney(p.total_gain_minor)} (${(p.gain_pct ?? 0).toFixed(1)}%)`}
              </div>
            </Card>
          </div>

          <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
            <Card className="lg:col-span-1">
              <h2 className="mb-2 font-semibold text-slate-100">Allocation</h2>
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={95} stroke="none">
                    {pieData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(v) => `$${Number(v).toFixed(2)}`}
                    contentStyle={TOOLTIP_STYLE}
                    itemStyle={TOOLTIP_ITEM_STYLE}
                    labelStyle={TOOLTIP_LABEL_STYLE}
                  />
                </PieChart>
              </ResponsiveContainer>
            </Card>

            <Card className="lg:col-span-2 overflow-hidden p-0">
              <table className="w-full text-sm">
                <thead className="border-b border-ink-700 bg-ink-900/60 text-left text-xs uppercase tracking-wider text-slate-400">
                  <tr>
                    <th className="px-5 py-3 font-semibold">Holding</th>
                    <th className="px-5 py-3 font-semibold">Account</th>
                    <th className="px-5 py-3 text-right font-semibold">Shares</th>
                    <th className="px-5 py-3 text-right font-semibold">Value</th>
                    <th className="px-5 py-3 text-right font-semibold">Gain</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-700">
                  {holdings.map((h) => (
                    <tr key={h.id} className="hover:bg-ink-700/60">
                      <td className="px-5 py-3">
                        <div className="font-medium text-slate-200">{h.symbol || "—"}</div>
                        <div className="max-w-[220px] truncate text-xs text-slate-500">
                          {h.description}
                        </div>
                      </td>
                      <td className="max-w-[160px] truncate px-5 py-3 text-slate-400">
                        {h.account_name}
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 text-right font-mono tnum text-slate-400">
                        {h.shares ?? "—"}
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 text-right font-mono font-semibold tnum text-slate-100">
                        {formatMoney(h.market_value_minor ?? 0, h.currency)}
                      </td>
                      <td
                        className={`whitespace-nowrap px-5 py-3 text-right font-mono tnum ${
                          h.gain_minor == null
                            ? "text-slate-500"
                            : h.gain_minor >= 0
                              ? "text-emerald-400"
                              : "text-red-400"
                        }`}
                      >
                        {h.gain_minor == null
                          ? "—"
                          : `${h.gain_minor >= 0 ? "+" : ""}${formatMoney(h.gain_minor)} (${(h.gain_pct ?? 0).toFixed(1)}%)`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          </div>
          <ValueHistoryCard />
          {p?.total_gain_minor == null && (
            <p className="mt-3 text-xs text-slate-500">
              Gain/loss is unavailable because your provider didn't report cost basis for these
              holdings.
            </p>
          )}
        </>
      )}
    </div>
  );
}
