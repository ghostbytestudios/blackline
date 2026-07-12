import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, FileUp, Plus } from "lucide-react";
import {
  useAccounts,
  useCreateManualAccount,
  useImportCommit,
  useImportPreview,
} from "../hooks/useApi";
import { Card, PageHeader } from "../components/ui";
import type { ColumnMapping, ImportPreview } from "../lib/types";

export type Role =
  | "ignore" | "date" | "amount" | "debit" | "credit" | "payee" | "description" | "memo";

const ROLE_OPTIONS: { value: Role; label: string }[] = [
  { value: "ignore", label: "— ignore —" },
  { value: "date", label: "Date" },
  { value: "amount", label: "Amount (signed)" },
  { value: "debit", label: "Debit (money out)" },
  { value: "credit", label: "Credit (money in)" },
  { value: "payee", label: "Payee" },
  { value: "description", label: "Description" },
  { value: "memo", label: "Memo" },
];

const ACCOUNT_TYPES = ["checking", "savings", "credit", "cash", "loan", "investment", "other"];

export function rolesFromSuggestion(m: ColumnMapping | null | undefined, width: number): Role[] {
  const roles: Role[] = Array(width).fill("ignore");
  if (!m) return roles;
  const assign = (idx: number | null | undefined, role: Role) => {
    if (idx != null && idx < width) roles[idx] = role;
  };
  assign(m.date, "date");
  assign(m.amount, "amount");
  assign(m.debit, "debit");
  assign(m.credit, "credit");
  assign(m.payee, "payee");
  assign(m.description, "description");
  assign(m.memo, "memo");
  return roles;
}

export function buildMapping(roles: Role[], dateFormat: string | null, flip: boolean): ColumnMapping | null {
  const idx = (r: Role) => {
    const i = roles.indexOf(r);
    return i === -1 ? null : i;
  };
  const date = idx("date");
  if (date === null) return null;
  const mapping: ColumnMapping = {
    date,
    amount: idx("amount"),
    debit: idx("debit"),
    credit: idx("credit"),
    payee: idx("payee"),
    description: idx("description"),
    memo: idx("memo"),
    date_format: dateFormat,
    flip_amounts: flip,
  };
  if (mapping.amount === null && mapping.debit === null && mapping.credit === null) return null;
  return mapping;
}

function NewAccountForm({ onCreated }: { onCreated: (id: number) => void }) {
  const create = useCreateManualAccount();
  const [name, setName] = useState("");
  const [type, setType] = useState("checking");

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-dashed border-ink-700 p-3">
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Account name (e.g. Old Bank Checking)"
        className="min-w-[16rem] flex-1 rounded-lg border border-ink-700 px-3 py-1.5 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
      />
      <select
        value={type}
        onChange={(e) => setType(e.target.value)}
        className="rounded-lg border border-ink-700 px-3 py-1.5 text-sm"
      >
        {ACCOUNT_TYPES.map((t) => (
          <option key={t} value={t}>
            {t[0].toUpperCase() + t.slice(1)}
          </option>
        ))}
      </select>
      <button
        onClick={() =>
          create.mutate(
            { name: name.trim(), account_type: type },
            { onSuccess: (a) => onCreated(a.id) },
          )
        }
        disabled={!name.trim() || create.isPending}
        className="rounded-lg bg-accent px-3 py-1.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
      >
        Create
      </button>
      {create.isError && (
        <span className="text-xs text-red-400">{(create.error as Error).message}</span>
      )}
    </div>
  );
}

export default function Import() {
  const accounts = useAccounts();
  const preview = useImportPreview();
  const commit = useImportCommit();
  const fileRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<{ name: string; content: string } | null>(null);
  const [accountId, setAccountId] = useState<number | "">("");
  const [roles, setRoles] = useState<Role[]>([]);
  const [flip, setFlip] = useState(false);
  const [skipDups, setSkipDups] = useState(true);
  const [showNewAccount, setShowNewAccount] = useState(false);

  const p: ImportPreview | undefined = preview.data;

  const onFile = async (f: File | undefined) => {
    if (!f) return;
    const content = await f.text();
    setFile({ name: f.name, content });
    commit.reset();
    setFlip(false);
    preview.mutate(
      { filename: f.name, content },
      {
        onSuccess: (pv) =>
          setRoles(rolesFromSuggestion(pv.suggested_mapping, pv.headers.length)),
      },
    );
  };

  // A role can only live on one column; assigning it elsewhere steals it.
  const setRole = (col: number, role: Role) =>
    setRoles((prev) =>
      prev.map((r, i) => (i === col ? role : role !== "ignore" && r === role ? "ignore" : r)),
    );

  const mapping =
    p?.kind === "csv"
      ? buildMapping(roles, p.suggested_mapping?.date_format ?? null, flip)
      : null;
  const ready = file !== null && accountId !== "" && (p?.kind === "ofx" || mapping !== null);
  const amountMapped = roles.includes("amount");

  const doImport = () => {
    if (!file || accountId === "") return;
    commit.mutate({
      filename: file.name,
      content: file.content,
      account_id: accountId,
      mapping,
      skip_duplicates: skipDups,
    });
  };

  return (
    <div>
      <PageHeader
        title="Import statements"
        action={
          <Link
            to="/transactions"
            className="flex items-center gap-2 rounded-lg border border-ink-700 px-3 py-2 text-sm text-slate-400 hover:bg-ink-700/60"
          >
            <ArrowLeft className="h-4 w-4" /> Back to transactions
          </Link>
        }
      />

      <Card>
        <h2 className="font-semibold text-slate-100">1. Choose a file and a destination account</h2>
        <p className="mt-1 text-sm text-slate-500">
          CSV, OFX, and QFX exports from your bank are supported. Everything is parsed locally —
          the file never leaves this machine.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <input
            ref={fileRef}
            type="file"
            accept=".csv,.ofx,.qfx,text/csv"
            className="hidden"
            onChange={(e) => onFile(e.target.files?.[0])}
          />
          <button
            onClick={() => fileRef.current?.click()}
            className="flex items-center gap-2 rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700"
          >
            <FileUp className="h-4 w-4" />
            {file ? file.name : "Choose file…"}
          </button>
          <select
            value={accountId}
            onChange={(e) => setAccountId(e.target.value ? Number(e.target.value) : "")}
            className="rounded-lg border border-ink-700 px-3 py-2 text-sm"
          >
            <option value="">Into account…</option>
            {(accounts.data ?? []).map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
          <button
            onClick={() => setShowNewAccount((s) => !s)}
            className="flex items-center gap-1.5 rounded-lg border border-ink-700 px-3 py-2 text-sm text-slate-400 hover:bg-ink-700/60"
          >
            <Plus className="h-4 w-4" /> New manual account
          </button>
        </div>
        {showNewAccount && (
          <NewAccountForm
            onCreated={(id) => {
              setAccountId(id);
              setShowNewAccount(false);
            }}
          />
        )}
        {preview.isError && (
          <p className="mt-3 text-sm text-red-400">{(preview.error as Error).message}</p>
        )}
      </Card>

      {p && (
        <Card className="mt-5">
          <div className="mb-1 flex items-center justify-between">
            <h2 className="font-semibold text-slate-100">
              2. {p.kind === "csv" ? "Map the columns" : "Review"}
            </h2>
            <span className="text-xs text-slate-500">
              {p.row_count} rows{p.currency ? ` · ${p.currency}` : ""}
              {p.kind === "ofx" ? " · OFX (no mapping needed)" : ""}
            </span>
          </div>
          {p.kind === "csv" && (
            <p className="mb-2 text-sm text-slate-500">
              Assign a role to each column. Date plus either a signed Amount or Debit/Credit
              columns are required.
            </p>
          )}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                {p.kind === "csv" && (
                  <tr>
                    {p.headers.map((_, i) => (
                      <th key={i} className="px-2 py-1.5">
                        <select
                          value={roles[i] ?? "ignore"}
                          onChange={(e) => setRole(i, e.target.value as Role)}
                          className={`w-full rounded-lg border px-2 py-1 text-xs ${
                            (roles[i] ?? "ignore") === "ignore"
                              ? "border-ink-700 text-slate-500"
                              : "border-accent text-slate-200"
                          }`}
                        >
                          {ROLE_OPTIONS.map((o) => (
                            <option key={o.value} value={o.value}>
                              {o.label}
                            </option>
                          ))}
                        </select>
                      </th>
                    ))}
                  </tr>
                )}
                <tr className="border-b border-ink-700 bg-ink-900/60 text-left text-xs uppercase tracking-wider text-slate-400">
                  {p.headers.map((h, i) => (
                    <th key={i} className="px-3 py-2 font-semibold">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-700">
                {p.sample_rows.map((row, ri) => (
                  <tr key={ri}>
                    {p.headers.map((_, ci) => (
                      <td key={ci} className="max-w-[220px] truncate px-3 py-2 text-slate-400">
                        {row[ci] ?? ""}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-slate-400">
            {p.kind === "csv" && amountMapped && (
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={flip} onChange={(e) => setFlip(e.target.checked)} />
                Amounts are positive for spending (flip signs)
              </label>
            )}
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={skipDups}
                onChange={(e) => setSkipDups(e.target.checked)}
              />
              Skip rows that look already synced (same amount within 3 days)
            </label>
          </div>
          {p.warnings.length > 0 && (
            <p className="mt-2 text-xs text-amber-400">{p.warnings.join(" · ")}</p>
          )}

          <div className="mt-4 flex items-center gap-3">
            <button
              onClick={doImport}
              disabled={!ready || commit.isPending}
              className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {commit.isPending ? "Importing…" : `Import ${p.row_count} rows`}
            </button>
            {!ready && (
              <span className="text-xs text-slate-500">
                {accountId === ""
                  ? "Pick a destination account first."
                  : "Map a Date column and an Amount (or Debit/Credit) column."}
              </span>
            )}
            {commit.isError && (
              <span className="text-sm text-red-400">{(commit.error as Error).message}</span>
            )}
          </div>
        </Card>
      )}

      {commit.data && (
        <Card className="mt-5">
          <h2 className="font-semibold text-slate-100">3. Done</h2>
          <p className="mt-2 text-sm text-slate-300">
            Imported <span className="font-semibold text-emerald-400">{commit.data.inserted}</span>{" "}
            transactions
            {commit.data.duplicates_skipped > 0 && (
              <> · {commit.data.duplicates_skipped} skipped as duplicates</>
            )}
            {commit.data.unparsed_skipped > 0 && (
              <> · {commit.data.unparsed_skipped} rows unreadable</>
            )}
            .
          </p>
          {commit.data.warnings.length > 0 && (
            <p className="mt-1 text-xs text-amber-400">{commit.data.warnings.join(" · ")}</p>
          )}
          <Link
            to="/transactions"
            className="mt-3 inline-block rounded-lg border border-ink-700 px-3 py-1.5 text-sm text-slate-300 hover:bg-ink-700/60"
          >
            View transactions
          </Link>
        </Card>
      )}
    </div>
  );
}
