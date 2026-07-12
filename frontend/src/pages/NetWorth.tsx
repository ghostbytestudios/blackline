import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useForecast, useInsights, useNetWorthHistory } from "../hooks/useApi";
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

function ForecastCard() {
  const { data: f } = useForecast(30);
  if (!f || f.points.length === 0) return null;
  const series = f.points.map((p) => ({
    label: formatDate(p.date),
    Projected: fromMinor(p.balance_minor),
  }));
  const falling = f.end_balance_minor < f.start_balance_minor;
  const color = falling ? "#f59e0b" : "#10b981";

  return (
    <Card className="mt-5">
      <div className="mb-1 flex items-center justify-between">
        <h2 className="font-semibold text-slate-100">Cash forecast — next 30 days</h2>
        <span className="text-xs text-slate-500">liquid accounts only</span>
      </div>
      <div className="mb-2 flex flex-wrap gap-x-6 gap-y-1 text-sm">
        <span className="text-slate-400">
          Today <span className="font-mono font-semibold tnum text-slate-100">{formatMoney(f.start_balance_minor)}</span>
        </span>
        <span className="text-slate-400">
          Projected{" "}
          <span className={`font-mono font-semibold tnum ${falling ? "text-amber-400" : "text-emerald-400"}`}>
            {formatMoney(f.end_balance_minor)}
          </span>
        </span>
        <span className="text-slate-400">
          Bills due <span className="font-mono tnum text-slate-300">{formatMoney(f.expected_bills_minor)}</span>
        </span>
        <span className="text-slate-400">
          Income expected <span className="font-mono tnum text-slate-300">{formatMoney(f.expected_income_minor)}</span>
        </span>
        <span className="text-slate-400">
          Day-to-day <span className="font-mono tnum text-slate-300">~{formatMoney(f.discretionary_daily_minor)}/day</span>
        </span>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={series}>
          <defs>
            <linearGradient id="fc" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.3} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis dataKey="label" tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={AXIS_LINE} minTickGap={40} />
          <YAxis tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={AXIS_LINE} domain={["auto", "auto"]} />
          <Tooltip
            formatter={(v) => `$${Number(v).toFixed(2)}`}
            contentStyle={TOOLTIP_STYLE}
            itemStyle={TOOLTIP_ITEM_STYLE}
            labelStyle={TOOLTIP_LABEL_STYLE}
          />
          <Area type="monotone" dataKey="Projected" stroke={color} strokeWidth={2} fill="url(#fc)" />
        </AreaChart>
      </ResponsiveContainer>
      <p className="mt-1 text-xs text-slate-500">
        Projection = scheduled recurring bills and income on your cash accounts, plus your
        average day-to-day spending. An estimate, not a promise.
      </p>
    </Card>
  );
}

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
              formatter={(v) => `$${Number(v).toFixed(2)}`}
              contentStyle={TOOLTIP_STYLE}
              itemStyle={TOOLTIP_ITEM_STYLE}
              labelStyle={TOOLTIP_LABEL_STYLE}
            />
            <Area type="monotone" dataKey="value" stroke={SERIES.accent} strokeWidth={2} fill="url(#nw)" />
          </AreaChart>
        </ResponsiveContainer>
      </Card>

      <ForecastCard />
    </div>
  );
}
