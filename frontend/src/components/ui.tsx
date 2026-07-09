import type { ReactNode } from "react";

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`rounded-xl border border-ink-700 bg-ink-800 p-5 shadow-sm ${className}`}>
      {children}
    </div>
  );
}

export function PageHeader({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div className="mb-6 flex items-center justify-between">
      <h1 className="text-2xl font-bold text-slate-100">{title}</h1>
      {action}
    </div>
  );
}

export function CategoryChip({ category }: { category: string }) {
  return (
    <span className="rounded border border-ink-700 bg-ink-900/60 px-2 py-0.5 text-xs font-medium text-slate-400">
      {category.replace(/\b\w/g, (c) => c.toUpperCase())}
    </span>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return <div className="py-10 text-center text-sm text-slate-500">{label}</div>;
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-dashed border-ink-700 bg-ink-800 py-12 text-center">
      <div className="text-sm font-medium text-slate-300">{title}</div>
      {hint && <div className="mt-1 text-sm text-slate-500">{hint}</div>}
    </div>
  );
}
