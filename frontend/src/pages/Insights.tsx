import { Lightbulb } from "lucide-react";
import { useInsights } from "../hooks/useApi";
import { Card, Loading, PageHeader } from "../components/ui";
import { formatMoney } from "../lib/format";

export default function Insights() {
  const { data, isLoading } = useInsights(120);
  if (isLoading) return <Loading />;
  const s = data;

  return (
    <div>
      <PageHeader title="Insights" />
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <Card>
          <div className="text-sm font-medium text-slate-500">Inflow (period)</div>
          <div className="mt-1 font-mono text-2xl font-bold tnum text-emerald-600">
            {formatMoney(s?.total_inflow_minor ?? 0)}
          </div>
        </Card>
        <Card>
          <div className="text-sm font-medium text-slate-500">Outflow (period)</div>
          <div className="mt-1 font-mono text-2xl font-bold tnum text-red-500">
            {formatMoney(s?.total_outflow_minor ?? 0)}
          </div>
        </Card>
        <Card>
          <div className="text-sm font-medium text-slate-500">Net (period)</div>
          <div className="mt-1 font-mono text-2xl font-bold tnum text-slate-900">
            {formatMoney(s?.net_minor ?? 0)}
          </div>
        </Card>
      </div>

      <Card className="mt-5">
        <div className="mb-3 flex items-center gap-2 font-semibold text-slate-900">
          <Lightbulb className="h-5 w-5 text-accent" />
          Observations
        </div>
        <ul className="space-y-2">
          {(s?.observations ?? []).map((o, i) => (
            <li key={i} className="flex gap-2 text-sm text-slate-700">
              <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
              {o}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
