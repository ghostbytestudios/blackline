import {
  Bar,
  BarChart,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useInsights } from "../hooks/useApi";
import { Card, EmptyState, Loading, PageHeader } from "../components/ui";
import { formatMoney, fromMinor, titleCase } from "../lib/format";

const COLORS = [
  "#2563eb", "#7c3aed", "#db2777", "#ea580c", "#16a34a",
  "#0891b2", "#ca8a04", "#dc2626", "#4f46e5", "#0d9488",
];

export default function Spending() {
  const { data, isLoading } = useInsights(120);
  if (isLoading) return <Loading />;
  const s = data;
  const cats = s?.top_categories ?? [];

  const pieData = cats.map((c) => ({ name: titleCase(c.category), value: fromMinor(c.total_minor) }));
  const barData = (s?.monthly_trends ?? []).map((m) => ({
    month: m.month,
    Spending: fromMinor(m.outflow_minor),
    Income: fromMinor(m.inflow_minor),
  }));

  return (
    <div>
      <PageHeader title="Spending Analysis" />
      {cats.length === 0 ? (
        <EmptyState title="No spending data yet" hint="Sync transactions to see category breakdowns." />
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <Card>
            <h2 className="mb-2 font-semibold text-slate-900">By Category</h2>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={60} outerRadius={100}>
                  {pieData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v: number) => `$${v.toFixed(2)}`} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </Card>

          <Card>
            <h2 className="mb-2 font-semibold text-slate-900">Income vs Spending</h2>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={barData}>
                <XAxis dataKey="month" fontSize={12} />
                <YAxis fontSize={12} />
                <Tooltip formatter={(v: number) => `$${v.toFixed(2)}`} />
                <Legend />
                <Bar dataKey="Income" fill="#16a34a" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Spending" fill="#dc2626" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          <Card className="lg:col-span-2">
            <h2 className="mb-3 font-semibold text-slate-900">Top Categories</h2>
            <div className="divide-y divide-slate-100">
              {cats.map((c, i) => (
                <div key={c.category} className="flex items-center justify-between py-2.5">
                  <div className="flex items-center gap-2">
                    <span
                      className="h-3 w-3 rounded-full"
                      style={{ background: COLORS[i % COLORS.length] }}
                    />
                    <span className="font-medium text-slate-800">{titleCase(c.category)}</span>
                    <span className="text-xs text-slate-400">({c.txn_count} txns)</span>
                  </div>
                  <span className="font-mono font-semibold tnum text-slate-900">
                    {formatMoney(c.total_minor)}
                  </span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
