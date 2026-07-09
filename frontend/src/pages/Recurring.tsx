import { CalendarClock, Repeat } from "lucide-react";
import { useRecurring } from "../hooks/useApi";
import { Card, CategoryChip, EmptyState, Loading, PageHeader } from "../components/ui";
import { formatMoney, formatDate, titleCase } from "../lib/format";

function dueLabel(days: number): { text: string; cls: string } {
  if (days < 0) return { text: `${-days}d overdue?`, cls: "text-amber-400" };
  if (days === 0) return { text: "today", cls: "text-amber-400 font-semibold" };
  if (days === 1) return { text: "tomorrow", cls: "text-slate-200 font-semibold" };
  return { text: `in ${days} days`, cls: "text-slate-400" };
}

export default function Recurring() {
  const { data, isLoading } = useRecurring();
  if (isLoading) return <Loading />;
  const items = data ?? [];
  const monthlyTotal = items.reduce((s, r) => s + r.monthly_estimate_minor, 0);
  const yearlyTotal = monthlyTotal * 12;

  const upcoming = items
    .filter((r) => r.days_until >= 0 && r.days_until <= 14)
    .sort((a, b) => a.days_until - b.days_until);
  const upcomingTotal = upcoming.reduce((s, r) => s + r.typical_amount_minor, 0);

  return (
    <div>
      <PageHeader title="Recurring" />
      {items.length === 0 ? (
        <EmptyState
          title="No recurring charges detected yet"
          hint="Detection needs at least 2 consistent charges from a merchant. Sync more history to improve it."
        />
      ) : (
        <>
          <div className="mb-5 grid grid-cols-1 gap-5 sm:grid-cols-3">
            <Card>
              <div className="text-sm font-medium text-slate-400">Recurring / month</div>
              <div className="mt-1 font-mono text-3xl font-bold tnum text-slate-100">
                {formatMoney(monthlyTotal)}
              </div>
            </Card>
            <Card>
              <div className="text-sm font-medium text-slate-400">Recurring / year</div>
              <div className="mt-1 font-mono text-3xl font-bold tnum text-slate-100">
                {formatMoney(yearlyTotal)}
              </div>
            </Card>
            <Card>
              <div className="text-sm font-medium text-slate-400">Due in next 14 days</div>
              <div className="mt-1 font-mono text-3xl font-bold tnum text-slate-100">
                {formatMoney(upcomingTotal)}
              </div>
              <div className="mt-0.5 text-xs text-slate-500">
                {upcoming.length} bill{upcoming.length === 1 ? "" : "s"}
              </div>
            </Card>
          </div>

          {upcoming.length > 0 && (
            <Card className="mb-5">
              <div className="mb-3 flex items-center gap-2 font-semibold text-slate-100">
                <CalendarClock className="h-5 w-5 text-accent-soft" />
                Upcoming bills
              </div>
              <div className="divide-y divide-ink-700">
                {upcoming.map((r, i) => {
                  const due = dueLabel(r.days_until);
                  return (
                    <div key={i} className="flex items-center justify-between py-2.5">
                      <div className="min-w-0 flex-1">
                        <div className="truncate font-medium text-slate-200">{r.name}</div>
                        <div className="text-xs text-slate-500">
                          {formatDate(r.next_date)} · {titleCase(r.cadence)}
                        </div>
                      </div>
                      <span className={`mx-4 text-sm ${due.cls}`}>{due.text}</span>
                      <span className="font-mono text-sm font-semibold tnum text-slate-100">
                        {formatMoney(r.typical_amount_minor)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </Card>
          )}

          <Card className="overflow-hidden p-0">
            <table className="w-full text-sm">
              <thead className="border-b border-ink-700 bg-ink-900/60 text-left text-xs uppercase tracking-wider text-slate-400">
                <tr>
                  <th className="px-5 py-3 font-semibold">Merchant</th>
                  <th className="px-5 py-3 font-semibold">Cadence</th>
                  <th className="px-5 py-3 font-semibold">Category</th>
                  <th className="px-5 py-3 font-semibold">Last charge</th>
                  <th className="px-5 py-3 font-semibold">Next due</th>
                  <th className="px-5 py-3 text-right font-semibold">Amount</th>
                  <th className="px-5 py-3 text-right font-semibold">~ / month</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-700">
                {items.map((r, i) => {
                  const due = dueLabel(r.days_until);
                  return (
                    <tr key={i} className="hover:bg-ink-700/60">
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-2 font-medium text-slate-200">
                          <Repeat className="h-4 w-4 text-accent" />
                          {r.name}
                        </div>
                      </td>
                      <td className="px-5 py-3 text-slate-400">{titleCase(r.cadence)}</td>
                      <td className="px-5 py-3">
                        <CategoryChip category={r.category} />
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 text-slate-400">
                        {formatDate(r.last_date)}
                      </td>
                      <td className="whitespace-nowrap px-5 py-3">
                        <span className={due.cls}>
                          {formatDate(r.next_date)} <span className="text-xs">({due.text})</span>
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 text-right font-mono tnum text-slate-300">
                        {formatMoney(r.typical_amount_minor)}
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 text-right font-mono font-semibold tnum text-slate-100">
                        {formatMoney(r.monthly_estimate_minor)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </div>
  );
}
