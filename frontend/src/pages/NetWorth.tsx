import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useInsights } from "../hooks/useApi";
import { Card, Loading, PageHeader } from "../components/ui";
import { formatMoney, fromMinor } from "../lib/format";

export default function NetWorth() {
  const { data, isLoading } = useInsights(365);
  if (isLoading) return <Loading />;
  const s = data;

  // We don't yet snapshot net worth over time, so we reconstruct an approximate
  // trajectory by walking monthly net flows backward from the current net worth.
  const trends = s?.monthly_trends ?? [];
  const current = s?.net_worth_minor ?? 0;
  let running = current;
  const series = [...trends]
    .reverse()
    .map((m) => {
      const point = { month: m.month, value: fromMinor(running) };
      running -= m.net_minor;
      return point;
    })
    .reverse();

  return (
    <div>
      <PageHeader title="Net Worth" />
      <Card>
        <div className="text-sm font-medium text-slate-500">Current Net Worth</div>
        <div className="mt-1 font-mono text-4xl font-bold tnum text-slate-900">
          {formatMoney(current)}
        </div>
        <p className="mt-2 text-xs text-amber-600">
          Trend is estimated from monthly cash flows. Precise history will appear once the app has
          recorded balance snapshots over time.
        </p>
        <div className="mt-4">
          <ResponsiveContainer width="100%" height={320}>
            <AreaChart data={series}>
              <defs>
                <linearGradient id="nw" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#2563eb" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#2563eb" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="month" fontSize={12} />
              <YAxis fontSize={12} />
              <Tooltip formatter={(v: number) => `$${v.toFixed(2)}`} />
              <Area type="monotone" dataKey="value" stroke="#2563eb" fill="url(#nw)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Card>
    </div>
  );
}
