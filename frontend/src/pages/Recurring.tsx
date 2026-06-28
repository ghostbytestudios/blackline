import { Repeat } from "lucide-react";
import { useRecurring } from "../hooks/useApi";
import { Card, CategoryChip, EmptyState, Loading, PageHeader } from "../components/ui";
import { formatMoney, formatDate, titleCase } from "../lib/format";

export default function Recurring() {
  const { data, isLoading } = useRecurring();
  if (isLoading) return <Loading />;
  const items = data ?? [];
  const monthlyTotal = items.reduce((s, r) => s + r.monthly_estimate_minor, 0);
  const yearlyTotal = monthlyTotal * 12;

  return (
    <div>
      <PageHeader title="Recurring" />
      {items.length === 0 ? (
        <EmptyState
          title="No recurring charges detected yet"
          hint="Detection needs at least 3 consistent charges from a merchant. Sync more history to improve it."
        />
      ) : (
        <>
          <div className="mb-5 grid grid-cols-1 gap-5 sm:grid-cols-3">
            <Card>
              <div className="text-sm font-medium text-slate-500">Recurring / month</div>
              <div className="mt-1 font-mono text-3xl font-bold tnum text-slate-900">
                {formatMoney(monthlyTotal)}
              </div>
            </Card>
            <Card>
              <div className="text-sm font-medium text-slate-500">Recurring / year</div>
              <div className="mt-1 font-mono text-3xl font-bold tnum text-slate-900">
                {formatMoney(yearlyTotal)}
              </div>
            </Card>
            <Card>
              <div className="text-sm font-medium text-slate-500">Subscriptions</div>
              <div className="mt-1 font-mono text-3xl font-bold tnum text-slate-900">
                {items.length}
              </div>
            </Card>
          </div>

          <Card className="overflow-hidden p-0">
            <table className="w-full text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-5 py-3 font-semibold">Merchant</th>
                  <th className="px-5 py-3 font-semibold">Cadence</th>
                  <th className="px-5 py-3 font-semibold">Category</th>
                  <th className="px-5 py-3 font-semibold">Last charge</th>
                  <th className="px-5 py-3 text-right font-semibold">Amount</th>
                  <th className="px-5 py-3 text-right font-semibold">~ / month</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.map((r, i) => (
                  <tr key={i} className="hover:bg-slate-50">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2 font-medium text-slate-800">
                        <Repeat className="h-4 w-4 text-accent" />
                        {r.name}
                      </div>
                    </td>
                    <td className="px-5 py-3 text-slate-500">{titleCase(r.cadence)}</td>
                    <td className="px-5 py-3">
                      <CategoryChip category={r.category} />
                    </td>
                    <td className="whitespace-nowrap px-5 py-3 text-slate-500">
                      {formatDate(r.last_date)}
                    </td>
                    <td className="whitespace-nowrap px-5 py-3 text-right font-mono tnum text-slate-700">
                      {formatMoney(r.typical_amount_minor)}
                    </td>
                    <td className="whitespace-nowrap px-5 py-3 text-right font-mono font-semibold tnum text-slate-900">
                      {formatMoney(r.monthly_estimate_minor)}
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
