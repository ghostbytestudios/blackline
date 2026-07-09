import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useInsights, useNetWorthHistory } from "../hooks/useApi";
import { Card, Loading, PageHeader } from "../components/ui";
import { formatMoney, fromMinor, formatDate } from "../lib/format";
import {
  AXIS_LINE,
  AXIS_TICK,
  SERIES,
  TOOLTIP_ITEM_STYLE,
  TOOLTIP_LABEL_STYLE,
  TOOLTIP_STYLE,
} from "../lib/chartTheme";

export default function NetWorth() {
  const history = useNetWorthHistory();
  const insights = useInsights(365);
  if (history.isLoading) return <Loading />;

  const points = history.data ?? [];
  const hasRealHistory = points.length >= 2;
  const latest = points.at(-1);

  // Real snapshot history when we have 2+ points; otherwise estimate from cash flow.
  let series: { label: string; value: number }[];
  let estimated = false;
  if (hasRealHistory) {
    series = points.map((p) => ({ label: formatDate(p.as_of), value: fromMinor(p.net_worth_minor) }));
  } else {
    estimated = true;
    const trends = insights.data?.monthly_trends ?? [];
    const current = latest?.net_worth_minor ?? insights.data?.net_worth_minor ?? 0;
    let running = current;
    series = [...trends]
      .reverse()
      .map((m) => {
        const point = { label: m.month, value: fromMinor(running) };
        running -= m.net_minor;
        return point;
      })
      .reverse();
  }

  const current = latest?.net_worth_minor ?? insights.data?.net_worth_minor ?? 0;

  return (
    <div>
      <PageHeader title="Net Worth" />

      <div className="mb-5 grid grid-cols-1 gap-5 sm:grid-cols-3">
        <Card>
          <div className="text-sm font-medium text-slate-400">Net Worth</div>
          <div className="mt-1 font-mono text-3xl font-bold tnum text-slate-100">
            {formatMoney(current)}
          </div>
        </Card>
        <Card>
          <div className="text-sm font-medium text-slate-400">Assets</div>
          <div className="mt-1 font-mono text-3xl font-bold tnum text-emerald-400">
            {formatMoney(latest?.assets_minor ?? 0)}
          </div>
        </Card>
        <Card>
          <div className="text-sm font-medium text-slate-400">Liabilities</div>
          <div className="mt-1 font-mono text-3xl font-bold tnum text-red-500">
            {formatMoney(latest?.liabilities_minor ?? 0)}
          </div>
        </Card>
      </div>

      <Card>
        <div className="mb-1 flex items-center justify-between">
          <h2 className="font-semibold text-slate-100">History</h2>
          <span className="text-xs text-slate-500">
            {hasRealHistory ? `${points.length} daily snapshots` : "building history…"}
          </span>
        </div>
        {estimated && (
          <p className="mb-2 text-xs text-amber-400">
            Estimated from cash flow until enough daily snapshots accumulate. A real snapshot is
            recorded each time you sync (and each day you open the app).
          </p>
        )}
        <ResponsiveContainer width="100%" height={320}>
          <AreaChart data={series}>
            <defs>
              <linearGradient id="nw" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={SERIES.accent} stopOpacity={0.35} />
                <stop offset="100%" stopColor={SERIES.accent} stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="label" tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={AXIS_LINE} />
            <YAxis tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={AXIS_LINE} />
            <Tooltip
              formatter={(v: number) => `$${v.toFixed(2)}`}
              contentStyle={TOOLTIP_STYLE}
              itemStyle={TOOLTIP_ITEM_STYLE}
              labelStyle={TOOLTIP_LABEL_STYLE}
            />
            <Area type="monotone" dataKey="value" stroke={SERIES.accent} strokeWidth={2} fill="url(#nw)" />
          </AreaChart>
        </ResponsiveContainer>
      </Card>
    </div>
  );
}
