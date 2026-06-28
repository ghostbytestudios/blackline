import { useAccounts } from "../hooks/useApi";
import { Card, EmptyState, Loading, PageHeader } from "../components/ui";
import { formatMoney, formatDate, titleCase } from "../lib/format";

const TYPE_LABELS: Record<string, string> = {
  depository: "Cash / Bank",
  credit: "Credit",
  investment: "Investment",
  loan: "Loan",
};

export default function Accounts() {
  const { data, isLoading } = useAccounts();
  if (isLoading) return <Loading />;
  const accounts = data ?? [];

  return (
    <div>
      <PageHeader title="Accounts" />
      {accounts.length === 0 ? (
        <EmptyState title="No accounts linked yet" hint="Connect a bank in Settings, then Sync." />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {accounts.map((a) => (
            <Card key={a.id}>
              <div className="flex items-start justify-between">
                <div>
                  <div className="font-semibold text-slate-900">{a.name}</div>
                  <div className="text-xs text-slate-400">{a.org_name ?? "—"}</div>
                </div>
                <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                  {TYPE_LABELS[a.account_type] ?? titleCase(a.account_type)}
                </span>
              </div>
              <div
                className={`mt-4 font-mono text-2xl font-bold tnum ${
                  a.balance_minor < 0 ? "text-red-500" : "text-slate-900"
                }`}
              >
                {formatMoney(a.balance_minor, a.currency)}
              </div>
              <div className="mt-1 text-xs text-slate-400">
                As of {formatDate(a.balance_date)}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
