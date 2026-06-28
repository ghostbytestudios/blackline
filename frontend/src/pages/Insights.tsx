import { Link } from "react-router-dom";
import {
  Lightbulb,
  TrendingUp,
  TrendingDown,
  Activity,
  PiggyBank,
  ShoppingCart,
  AlertCircle,
  Info,
  type LucideIcon,
} from "lucide-react";
import { useInsightCards } from "../hooks/useApi";
import { EmptyState, Loading, PageHeader } from "../components/ui";
import type { InsightCard } from "../lib/types";

const ICONS: Record<string, LucideIcon> = {
  "trending-up": TrendingUp,
  "trending-down": TrendingDown,
  activity: Activity,
  piggy: PiggyBank,
  shopping: ShoppingCart,
};

const SEVERITY = {
  critical: {
    border: "border-l-red-500",
    badge: "border-red-200 bg-red-50 text-red-600",
    label: "critical",
    Badge: AlertCircle,
  },
  warning: {
    border: "border-l-amber-400",
    badge: "border-amber-200 bg-amber-50 text-amber-600",
    label: "warning",
    Badge: AlertCircle,
  },
  info: {
    border: "border-l-blue-400",
    badge: "border-blue-200 bg-blue-50 text-blue-600",
    label: "info",
    Badge: Info,
  },
} as const;

const GROUPS: { key: keyof typeof SEVERITY; heading: string }[] = [
  { key: "critical", heading: "Requires Attention" },
  { key: "warning", heading: "Heads Up" },
  { key: "info", heading: "Opportunities" },
];

function Card({ card }: { card: InsightCard }) {
  const sev = SEVERITY[card.severity];
  const Icon = ICONS[card.icon] ?? Lightbulb;
  const Badge = sev.Badge;
  return (
    <div className={`rounded-xl border border-slate-200 border-l-4 bg-white p-5 shadow-sm ${sev.border}`}>
      <div className="flex gap-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-slate-50 text-slate-500">
          <Icon className="h-5 w-5" />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-slate-900">{card.title}</h3>
            <span
              className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs font-medium ${sev.badge}`}
            >
              <Badge className="h-3 w-3" />
              {sev.label}
            </span>
          </div>
          <p className="mt-1.5 text-sm leading-relaxed text-slate-500">{card.detail}</p>
          {card.action_label && card.action_route && (
            <Link
              to={card.action_route}
              className="mt-3 inline-block rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              {card.action_label}
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Insights() {
  const { data, isLoading } = useInsightCards();
  if (isLoading) return <Loading />;
  const cards = data ?? [];

  return (
    <div>
      <PageHeader title="Insights" />

      <div className="mb-5 flex items-center justify-between border-b border-slate-200 pb-3">
        <div className="flex items-center gap-2 text-lg font-semibold text-slate-900">
          <Lightbulb className="h-5 w-5 text-accent" />
          Financial Insights
        </div>
        <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-500">
          {cards.length} insight{cards.length === 1 ? "" : "s"}
        </span>
      </div>

      {cards.length === 0 ? (
        <EmptyState
          title="No insights yet"
          hint="Sync more history and categorize transactions to unlock insights."
        />
      ) : (
        <div className="space-y-7">
          {GROUPS.map(({ key, heading }) => {
            const group = cards.filter((c) => c.severity === key);
            if (group.length === 0) return null;
            return (
              <section key={key}>
                <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                  {heading}
                </div>
                <div className="space-y-4">
                  {group.map((c) => (
                    <Card key={c.id} card={c} />
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
