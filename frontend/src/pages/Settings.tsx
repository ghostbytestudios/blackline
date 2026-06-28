import { useEffect, useState } from "react";
import { CheckCircle2, RefreshCw, Link2, AlertCircle, KeyRound, DollarSign } from "lucide-react";
import {
  useChangePassphrase,
  useConnect,
  useProfile,
  useSetProfile,
  useStatus,
  useSync,
} from "../hooks/useApi";
import { api, ApiError } from "../lib/api";
import { Card, PageHeader } from "../components/ui";
import { formatDate } from "../lib/format";
import { useQueryClient } from "@tanstack/react-query";

export default function Settings() {
  const { data: status } = useStatus();
  const connect = useConnect();
  const sync = useSync();
  const qc = useQueryClient();
  const [token, setToken] = useState("");

  const connectErr = connect.error instanceof ApiError ? connect.error.message : null;
  const syncErr = sync.error instanceof ApiError ? sync.error.message : null;

  const disconnect = async () => {
    await api.del("/connect");
    qc.invalidateQueries();
  };

  return (
    <div className="max-w-2xl">
      <PageHeader title="Settings" />

      <IncomeCard />

      <Card className="mt-5">
        <div className="flex items-center gap-2 font-semibold text-slate-900">
          <Link2 className="h-5 w-5 text-accent" />
          Bank Connection (SimpleFIN)
        </div>

        {status?.connected ? (
          <div className="mt-4">
            <div className="flex items-center gap-2 text-sm text-emerald-600">
              <CheckCircle2 className="h-4 w-4" />
              Connected · {status.account_count} account(s)
            </div>
            <div className="mt-1 text-xs text-slate-400">
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
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
              >
                Disconnect
              </button>
            </div>

            {sync.isSuccess && (
              <p className="mt-3 text-sm text-emerald-600">
                Synced: +{sync.data.transactions_inserted} transactions,{" "}
                {sync.data.accounts_upserted} accounts.
              </p>
            )}
            {syncErr && (
              <p className="mt-3 flex items-center gap-1 text-sm text-red-600">
                <AlertCircle className="h-4 w-4" /> {syncErr}
              </p>
            )}
          </div>
        ) : (
          <div className="mt-4">
            <ol className="mb-3 list-decimal space-y-1 pl-5 text-sm text-slate-600">
              <li>
                Go to{" "}
                <a
                  href="https://bridge.simplefin.org/"
                  target="_blank"
                  rel="noreferrer"
                  className="text-accent hover:underline"
                >
                  bridge.simplefin.org
                </a>
                , connect your bank, and create a <strong>Setup Token</strong>.
              </li>
              <li>Paste the token below. It is exchanged once for a read-only access token.</li>
            </ol>
            <textarea
              value={token}
              onChange={(e) => setToken(e.target.value)}
              rows={3}
              placeholder="Paste SimpleFIN setup token…"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            />
            {connectErr && (
              <p className="mt-2 flex items-center gap-1 text-sm text-red-600">
                <AlertCircle className="h-4 w-4" /> {connectErr}
              </p>
            )}
            <button
              onClick={() => connect.mutate(token.trim())}
              disabled={connect.isPending || token.trim().length === 0}
              className="mt-3 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {connect.isPending ? "Connecting…" : "Connect"}
            </button>
          </div>
        )}
      </Card>

      <ChangePassphraseCard />

      <Card className="mt-5">
        <div className="font-semibold text-slate-900">Security</div>
        <p className="mt-2 text-sm text-slate-600">
          Your SimpleFIN access token is encrypted at rest with AES-256-GCM using a key derived
          from your passphrase. The app runs only on localhost and reaches the internet solely
          during a sync. Lock the vault from the sidebar when you step away.
        </p>
      </Card>
    </div>
  );
}

function IncomeCard() {
  const { data: profile } = useProfile();
  const setProfile = useSetProfile();
  const [val, setVal] = useState("");

  useEffect(() => {
    if (profile && profile.gross_annual_income_minor > 0) {
      setVal(String(profile.gross_annual_income_minor / 100));
    }
  }, [profile]);

  const save = () => {
    const dollars = parseFloat(val);
    if (isNaN(dollars) || dollars < 0) return;
    setProfile.mutate(Math.round(dollars * 100));
  };

  return (
    <Card>
      <div className="flex items-center gap-2 font-semibold text-slate-900">
        <DollarSign className="h-5 w-5 text-accent" />
        Income
      </div>
      <p className="mt-2 text-sm text-slate-500">
        Your gross annual income powers budgeting guidance (50/30/20, plus housing, car, and
        debt-to-income ratios) and the "Suggest budgets" feature.
      </p>
      <div className="mt-4 flex items-center gap-2">
        <div className="relative">
          <span className="absolute left-2 top-1/2 -translate-y-1/2 text-sm text-slate-400">$</span>
          <input
            value={val}
            onChange={(e) => setVal(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && save()}
            inputMode="decimal"
            placeholder="75000"
            className="w-40 rounded-lg border border-slate-300 py-2 pl-5 pr-2 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </div>
        <span className="text-sm text-slate-400">/ year (gross)</span>
        <button
          onClick={save}
          disabled={setProfile.isPending}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
        >
          Save
        </button>
        {setProfile.isSuccess && <span className="text-sm text-emerald-600">Saved.</span>}
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
      <div className="flex items-center gap-2 font-semibold text-slate-900">
        <KeyRound className="h-5 w-5 text-accent" />
        Change Passphrase
      </div>
      <p className="mt-2 text-sm text-slate-500">
        Re-encrypts your vault under a new passphrase. There is no recovery — if you forget it,
        the data cannot be decrypted.
      </p>
      <div className="mt-4 max-w-sm space-y-3">
        <input
          type="password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          placeholder="Current passphrase"
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
        />
        <input
          type="password"
          value={next}
          onChange={(e) => setNext(e.target.value)}
          placeholder="New passphrase (min 8 chars)"
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
        />
        <input
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          placeholder="Confirm new passphrase"
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
        />
        {mismatch && <p className="text-sm text-red-600">New passphrases do not match.</p>}
        {err && (
          <p className="flex items-center gap-1 text-sm text-red-600">
            <AlertCircle className="h-4 w-4" /> {err}
          </p>
        )}
        {change.isSuccess && <p className="text-sm text-emerald-600">Passphrase updated.</p>}
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
