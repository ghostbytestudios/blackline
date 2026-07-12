import { useEffect, useState } from "react";
import {
  ArrowLeftRight,
  CheckCircle2,
  RefreshCw,
  Link2,
  AlertCircle,
  KeyRound,
  DollarSign,
  Download,
  ExternalLink,
  FlaskConical,
  ListChecks,
  Trash2,
} from "lucide-react";
import {
  useAddRule,
  useChangePassphrase,
  useConnect,
  useDeleteRule,
  useMatchTransfers,
  useProfile,
  useRemoveDemo,
  useRules,
  useSeedDemo,
  useSetProfile,
  useStatus,
  useSync,
} from "../hooks/useApi";
import { api, ApiError } from "../lib/api";
import { Card, PageHeader } from "../components/ui";
import { formatDate, formatMoney } from "../lib/format";
import { useQueryClient } from "@tanstack/react-query";

/** A setup token is base64 of the SimpleFIN claim URL — sniff it so we can auto-fill. */
function looksLikeSetupToken(text: string): boolean {
  const t = text.trim();
  if (t.length < 40 || /\s/.test(t)) return false;
  try {
    return /simplefin.*\/claim\//i.test(atob(t));
  } catch {
    return false;
  }
}

export default function Settings() {
  const { data: status } = useStatus();
  const connect = useConnect();
  const sync = useSync();
  const qc = useQueryClient();
  const [token, setToken] = useState("");
  const [autoFilled, setAutoFilled] = useState(false);

  const connectErr = connect.error instanceof ApiError ? connect.error.message : null;
  const syncErr = sync.error instanceof ApiError ? sync.error.message : null;

  const openBridge = () => {
    window.open(
      "https://bridge.simplefin.org/",
      "simplefin-bridge",
      "width=540,height=760,menubar=no,toolbar=no,location=yes,resizable=yes",
    );
  };

  // When the user comes back from the Bridge popup, try to grab the token they
  // copied straight from the clipboard so they don't have to paste it manually.
  useEffect(() => {
    if (status?.connected) return;
    const grab = async () => {
      if (token.trim().length > 0) return; // don't clobber manual input
      try {
        const text = await navigator.clipboard.readText();
        if (looksLikeSetupToken(text)) {
          setToken(text.trim());
          setAutoFilled(true);
        }
      } catch {
        // clipboard unavailable or denied — manual paste still works fine
      }
    };
    window.addEventListener("focus", grab);
    return () => window.removeEventListener("focus", grab);
  }, [status?.connected, token]);

  const disconnect = async () => {
    await api.del("/connect");
    qc.invalidateQueries();
  };

  return (
    <div className="max-w-2xl">
      <PageHeader title="Settings" />

      <IncomeCard />

      <Card className="mt-5">
        <div className="flex items-center gap-2 font-semibold text-slate-100">
          <Link2 className="h-5 w-5 text-accent" />
          Bank Connection (SimpleFIN)
        </div>

        {status?.connected ? (
          <div className="mt-4">
            <div className="flex items-center gap-2 text-sm text-emerald-400">
              <CheckCircle2 className="h-4 w-4" />
              Connected · {status.account_count} account(s)
            </div>
            <div className="mt-1 text-xs text-slate-500">
              Last sync: {status.last_sync ? formatDate(status.last_sync) : "never"}
            </div>

            <div className="mt-4 flex gap-3">
              <button
                onClick={() => sync.mutate(90)}
                disabled={sync.isPending}
                className="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
              >
                <RefreshCw className={`h-4 w-4 ${sync.isPending ? "animate-spin" : ""}`} />
                {sync.isPending ? "Syncing…" : "Sync now"}
              </button>
              <button
                onClick={disconnect}
                className="rounded-lg border border-ink-700 px-4 py-2 text-sm font-medium text-slate-400 hover:bg-ink-700/60"
              >
                Disconnect
              </button>
            </div>

            {sync.isSuccess && (
              <p className="mt-3 text-sm text-emerald-400">
                Synced: +{sync.data.transactions_inserted} transactions,{" "}
                {sync.data.accounts_upserted} accounts.
              </p>
            )}
            {syncErr && (
              <p className="mt-3 flex items-center gap-1 text-sm text-red-400">
                <AlertCircle className="h-4 w-4" /> {syncErr}
              </p>
            )}
          </div>
        ) : (
          <div className="mt-4">
            <ol className="mb-3 space-y-3 text-sm text-slate-400">
              <li className="flex items-start gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold text-white">
                  1
                </span>
                <div>
                  <div>
                    Open the SimpleFIN Bridge, sign in to your bank(s), and copy the Setup Token.
                    A Bridge account is ~$1.50/month (free trial) — that&apos;s paid to SimpleFIN,
                    not us.
                  </div>
                  <button
                    onClick={openBridge}
                    className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-sm font-semibold text-white hover:bg-blue-700"
                  >
                    <ExternalLink className="h-4 w-4" />
                    Open SimpleFIN Bridge
                  </button>
                </div>
              </li>
              <li className="flex items-start gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold text-white">
                  2
                </span>
                <div className="flex-1">
                  <div className="mb-2">
                    Come back here — we&apos;ll grab the token from your clipboard automatically.
                    Otherwise paste it below, then connect.
                  </div>
                  <textarea
                    value={token}
                    onChange={(e) => {
                      setToken(e.target.value);
                      setAutoFilled(false);
                    }}
                    rows={3}
                    placeholder="Paste SimpleFIN setup token…"
                    className="w-full rounded-lg border border-ink-700 px-3 py-2 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                  />
                  {autoFilled && (
                    <p className="mt-2 flex items-center gap-1 text-sm text-emerald-400">
                      <CheckCircle2 className="h-4 w-4" /> Token detected from clipboard.
                    </p>
                  )}
                  {connectErr && (
                    <p className="mt-2 flex items-center gap-1 text-sm text-red-400">
                      <AlertCircle className="h-4 w-4" /> {connectErr}
                    </p>
                  )}
                  <button
                    onClick={() =>
                      connect.mutate(token.trim(), { onSuccess: () => sync.mutate(90) })
                    }
                    disabled={connect.isPending || sync.isPending || token.trim().length === 0}
                    className="mt-3 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                  >
                    {connect.isPending
                      ? "Connecting…"
                      : sync.isPending
                        ? "Syncing…"
                        : "Connect & Sync"}
                  </button>
                </div>
              </li>
            </ol>
            <p className="text-xs text-slate-500">
              The token is exchanged once for a read-only access token, encrypted at rest. To add
              more banks later, connect them at the Bridge and just hit Sync — no new token needed.
            </p>
          </div>
        )}
      </Card>

      <RulesCard />

      <DemoCard />

      <ExportCard />

      <ChangePassphraseCard />

      <Card className="mt-5">
        <div className="font-semibold text-slate-100">Security</div>
        <p className="mt-2 text-sm text-slate-400">
          Your SimpleFIN access token is encrypted at rest with AES-256-GCM using a key derived
          from your passphrase. The app runs only on localhost and reaches the internet solely
          during a sync. Lock the vault from the sidebar when you step away.
        </p>
      </Card>
    </div>
  );
}

const RULE_CATEGORIES = [
  "groceries", "dining", "transport", "travel", "shopping", "subscriptions",
  "entertainment", "utilities", "housing", "health", "insurance", "loans",
  "interest", "income", "transfer", "atm", "fees", "uncategorized",
];

function RulesCard() {
  const { data: rules } = useRules();
  const addRule = useAddRule();
  const deleteRule = useDeleteRule();
  const matchTransfers = useMatchTransfers();
  const [pattern, setPattern] = useState("");
  const [category, setCategory] = useState("groceries");

  const add = () =>
    addRule.mutate(
      { pattern: pattern.trim().toLowerCase(), category },
      { onSuccess: () => setPattern("") },
    );

  return (
    <Card className="mt-5">
      <div className="flex items-center gap-2 font-semibold text-slate-100">
        <ListChecks className="h-5 w-5 text-accent-soft" />
        Category Rules
      </div>
      <p className="mt-2 text-sm text-slate-400">
        Rules assign a category to any transaction whose payee or description contains the
        pattern. One is learned automatically each time you correct a category; manage them all
        here. Deleting a rule re-categorizes the transactions it was deciding.
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <input
          value={pattern}
          onChange={(e) => setPattern(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && pattern.trim() && add()}
          placeholder='Pattern, e.g. "trader joe"'
          className="min-w-[14rem] flex-1 rounded-lg border border-ink-700 px-3 py-1.5 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
        />
        <span className="text-xs text-slate-500">→</span>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="rounded-lg border border-ink-700 px-3 py-1.5 text-sm"
        >
          {RULE_CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c[0].toUpperCase() + c.slice(1)}
            </option>
          ))}
        </select>
        <button
          onClick={add}
          disabled={!pattern.trim() || addRule.isPending}
          className="rounded-lg bg-accent px-3 py-1.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
        >
          Add rule
        </button>
      </div>

      {(rules ?? []).length > 0 ? (
        <table className="mt-3 w-full text-sm">
          <thead className="border-b border-ink-700 text-left text-xs uppercase tracking-wider text-slate-500">
            <tr>
              <th className="py-2 pr-3 font-semibold">Pattern</th>
              <th className="py-2 pr-3 font-semibold">Category</th>
              <th className="py-2 pr-3 text-right font-semibold">Matches</th>
              <th className="w-10 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-700">
            {(rules ?? []).map((r) => (
              <tr key={r.id}>
                <td className="py-2 pr-3 font-mono text-xs text-slate-300">{r.pattern}</td>
                <td className="py-2 pr-3 text-slate-400">
                  {r.category[0].toUpperCase() + r.category.slice(1)}
                </td>
                <td className="py-2 pr-3 text-right font-mono text-xs tnum text-slate-400">
                  {r.match_count}
                </td>
                <td className="py-2 text-center">
                  <button
                    onClick={() => deleteRule.mutate(r.id)}
                    disabled={deleteRule.isPending}
                    title="Delete rule (re-categorizes its transactions)"
                    className="text-slate-600 hover:text-red-400"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="mt-3 text-sm text-slate-500">
          No rules yet — correct a category on the Transactions page and one appears here.
        </p>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-ink-700 pt-3">
        <button
          onClick={() => matchTransfers.mutate()}
          disabled={matchTransfers.isPending}
          className="flex items-center gap-2 rounded-lg border border-ink-700 px-3 py-1.5 text-sm text-slate-300 hover:bg-ink-700/60 disabled:opacity-50"
        >
          <ArrowLeftRight className="h-4 w-4" />
          {matchTransfers.isPending ? "Scanning…" : "Match internal transfers"}
        </button>
        <span className="text-xs text-slate-500">
          {matchTransfers.data
            ? `Linked ${matchTransfers.data.pairs_matched} pair${matchTransfers.data.pairs_matched === 1 ? "" : "s"}.`
            : "Runs automatically after every sync and import — this scans the last year for anything older."}
        </span>
      </div>
    </Card>
  );
}

function IncomeCard() {
  const { data: profile } = useProfile();
  const setProfile = useSetProfile();
  const [val, setVal] = useState("");
  const [netVal, setNetVal] = useState("");
  // Seed the inputs whenever a fresh profile arrives (state adjustment during
  // render — the React-recommended replacement for a setState-in-effect sync).
  const [seededFrom, setSeededFrom] = useState<typeof profile>(undefined);
  if (profile && profile !== seededFrom) {
    setSeededFrom(profile);
    if (profile.gross_annual_income_minor > 0) {
      setVal(String(profile.gross_annual_income_minor / 100));
    }
    if (profile.net_monthly_income_minor) {
      setNetVal(String(profile.net_monthly_income_minor / 100));
    }
  }

  const save = () => {
    const gross = parseFloat(val.replace(/,/g, ""));
    const net = parseFloat(netVal.replace(/,/g, ""));
    setProfile.mutate({
      ...(isNaN(gross) || gross < 0 ? {} : { gross_annual_income_minor: Math.round(gross * 100) }),
      // Empty field clears the override (falls back to observed/estimated).
      net_monthly_income_minor:
        netVal.trim() === "" ? null : isNaN(net) || net <= 0 ? undefined : Math.round(net * 100),
    });
  };

  const takeHomeHint =
    profile && profile.take_home_monthly_minor > 0
      ? {
          manual: "using your manual take-home",
          observed: "auto-detected from your recurring deposits",
          estimated: "estimated as 75% of gross — set take-home or sync payroll for accuracy",
          none: "",
        }[profile.take_home_source]
      : null;

  return (
    <Card>
      <div className="flex items-center gap-2 font-semibold text-slate-100">
        <DollarSign className="h-5 w-5 text-accent" />
        Income
      </div>
      <p className="mt-2 text-sm text-slate-400">
        Gross income drives the lender-style guidance (housing, debt-to-income) and "Suggest
        budgets". Take-home drives the 50/30/20 and car-cost checks — leave it blank and it's
        detected automatically from your recurring payroll deposits.
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-x-2 gap-y-3">
        <div className="relative">
          <span className="absolute left-2 top-1/2 -translate-y-1/2 text-sm text-slate-500">$</span>
          <input
            value={val}
            onChange={(e) => setVal(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && save()}
            inputMode="decimal"
            placeholder="75000"
            className="w-36 rounded-lg border border-ink-700 py-2 pl-5 pr-2 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </div>
        <span className="mr-3 text-sm text-slate-500">/ year (gross)</span>
        <div className="relative">
          <span className="absolute left-2 top-1/2 -translate-y-1/2 text-sm text-slate-500">$</span>
          <input
            value={netVal}
            onChange={(e) => setNetVal(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && save()}
            inputMode="decimal"
            placeholder="auto"
            className="w-28 rounded-lg border border-ink-700 py-2 pl-5 pr-2 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </div>
        <span className="text-sm text-slate-500">/ month (take-home, optional)</span>
        <button
          onClick={save}
          disabled={setProfile.isPending}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
        >
          Save
        </button>
        {setProfile.isSuccess && <span className="text-sm text-emerald-400">Saved.</span>}
      </div>
      {takeHomeHint && (
        <p className="mt-2 text-xs text-slate-500">
          Take-home in use:{" "}
          <span className="font-mono tnum text-slate-400">
            {formatMoney(profile!.take_home_monthly_minor)}/mo
          </span>{" "}
          — {takeHomeHint}.
        </p>
      )}
    </Card>
  );
}

function DemoCard() {
  const { data: status } = useStatus();
  const seed = useSeedDemo();
  const remove = useRemoveDemo();

  if (!status) return null;

  const seedErr = seed.error instanceof ApiError ? seed.error.message : null;

  // A real bank connection (and no lingering demo data): demo mode is off the table,
  // but say so rather than vanish — a hidden card reads as a missing feature.
  if (status.connected && !status.demo_data) {
    return (
      <Card className="mt-5">
        <div className="flex items-center gap-2 font-semibold text-slate-100">
          <FlaskConical className="h-5 w-5 text-slate-600" />
          Demo Mode
        </div>
        <p className="mt-2 text-sm text-slate-500">
          Unavailable while a bank is connected — demo data never mixes with your real
          financial data. You&apos;re running on the real thing.
        </p>
      </Card>
    );
  }

  return (
    <Card className="mt-5">
      <div className="flex items-center gap-2 font-semibold text-slate-100">
        <FlaskConical className="h-5 w-5 text-accent" />
        Demo Mode
      </div>
      {status.demo_data ? (
        <div className="mt-2">
          <p className="text-sm text-slate-400">
            Demo data is loaded — a fictional six-month household. It's removed
            automatically the moment you connect your real accounts, or remove it
            now.
          </p>
          <button
            onClick={() => remove.mutate()}
            disabled={remove.isPending}
            className="mt-3 rounded-lg border border-ink-700 px-4 py-2 text-sm font-medium text-slate-400 hover:bg-ink-700/60 disabled:opacity-50"
          >
            {remove.isPending ? "Removing…" : "Remove demo data"}
          </button>
        </div>
      ) : (
        <div className="mt-2">
          <p className="text-sm text-slate-400">
            No bank yet? Load a fictional household — five accounts, six months of
            realistic activity — to explore every feature. One click removes it later.
          </p>
          <button
            onClick={() => seed.mutate()}
            disabled={seed.isPending || status.account_count > 0}
            className="mt-3 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {seed.isPending ? "Loading…" : "Load demo data"}
          </button>
          {status.account_count > 0 && (
            <p className="mt-2 text-xs text-slate-500">
              Demo data only loads into an empty vault.
            </p>
          )}
          {seedErr && (
            <p className="mt-2 flex items-center gap-1 text-sm text-red-400">
              <AlertCircle className="h-4 w-4" /> {seedErr}
            </p>
          )}
        </div>
      )}
    </Card>
  );
}

function ExportCard() {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  const href = (() => {
    const params = new URLSearchParams();
    if (start) params.set("start", start);
    if (end) params.set("end", end);
    const qs = params.toString();
    return `/api/transactions/export.csv${qs ? `?${qs}` : ""}`;
  })();

  return (
    <Card className="mt-5">
      <div className="flex items-center gap-2 font-semibold text-slate-100">
        <Download className="h-5 w-5 text-accent" />
        Export Data
      </div>
      <p className="mt-2 text-sm text-slate-400">
        Download your transactions as CSV — for spreadsheets, taxes, or your own backups.
        Leave the dates empty to export everything.
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <input
          type="date"
          value={start}
          onChange={(e) => setStart(e.target.value)}
          className="rounded-lg border border-ink-700 px-3 py-2 text-sm text-slate-400 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
        />
        <span className="text-sm text-slate-500">to</span>
        <input
          type="date"
          value={end}
          onChange={(e) => setEnd(e.target.value)}
          className="rounded-lg border border-ink-700 px-3 py-2 text-sm text-slate-400 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
        />
        <a
          href={href}
          download
          className="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
        >
          <Download className="h-4 w-4" />
          Download CSV
        </a>
      </div>
    </Card>
  );
}

function ChangePassphraseCard() {
  const change = useChangePassphrase();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");

  const mismatch = next.length > 0 && confirm.length > 0 && next !== confirm;
  const canSubmit = current.length >= 1 && next.length >= 8 && next === confirm && !change.isPending;
  const err = change.error instanceof ApiError ? change.error.message : null;

  const submit = () => {
    change.mutate(
      { current, next },
      {
        onSuccess: () => {
          setCurrent("");
          setNext("");
          setConfirm("");
        },
      },
    );
  };

  return (
    <Card className="mt-5">
      <div className="flex items-center gap-2 font-semibold text-slate-100">
        <KeyRound className="h-5 w-5 text-accent" />
        Change Passphrase
      </div>
      <p className="mt-2 text-sm text-slate-400">
        Re-encrypts your vault under a new passphrase. There is no recovery — if you forget it,
        the data cannot be decrypted.
      </p>
      <div className="mt-4 max-w-sm space-y-3">
        <input
          type="password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          placeholder="Current passphrase"
          className="w-full rounded-lg border border-ink-700 px-3 py-2 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
        />
        <input
          type="password"
          value={next}
          onChange={(e) => setNext(e.target.value)}
          placeholder="New passphrase (min 8 chars)"
          className="w-full rounded-lg border border-ink-700 px-3 py-2 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
        />
        <input
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          placeholder="Confirm new passphrase"
          className="w-full rounded-lg border border-ink-700 px-3 py-2 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
        />
        {mismatch && <p className="text-sm text-red-400">New passphrases do not match.</p>}
        {err && (
          <p className="flex items-center gap-1 text-sm text-red-400">
            <AlertCircle className="h-4 w-4" /> {err}
          </p>
        )}
        {change.isSuccess && <p className="text-sm text-emerald-400">Passphrase updated.</p>}
        <button
          onClick={submit}
          disabled={!canSubmit}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {change.isPending ? "Updating…" : "Update passphrase"}
        </button>
      </div>
    </Card>
  );
}
