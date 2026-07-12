// All money is stored as integer minor units (cents) on the backend.
export function fromMinor(minor: number): number {
  return minor / 100;
}

const LIABILITY_TYPES = new Set(["credit", "loan"]);

/**
 * Convert a raw transaction amount into a *cash-flow* amount from the user's
 * perspective. Liability accounts (loans, credit cards) sign transactions as
 * balance changes — a loan payment is positive (debt down) even though it is cash
 * leaving you. From your wallet's view, money moving on a liability is an outflow,
 * so we render it negative (red). Asset accounts keep their natural sign.
 */
export function cashFlowMinor(amountMinor: number, accountType: string | undefined): number {
  if (accountType && LIABILITY_TYPES.has(accountType)) {
    return -Math.abs(amountMinor);
  }
  return amountMinor;
}

export function formatMoney(minor: number | null | undefined, currency = "USD"): string {
  if (minor === null || minor === undefined) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(fromMinor(minor));
}

export function formatPercent(value: number, digits = 1): string {
  return `${value.toFixed(digits)}%`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  // Backend timestamps are UTC; SQLite round-trips them without an offset marker,
  // which new Date() would misread as local time. Pin offset-less strings to UTC.
  const d = new Date(/[Zz]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function titleCase(s: string): string {
  return s.replace(/\b\w/g, (c) => c.toUpperCase());
}
