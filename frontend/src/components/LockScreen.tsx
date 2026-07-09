import { useState } from "react";
import { AlertTriangle, ShieldCheck } from "lucide-react";
import { useResetVault, useStatus, useUnlock } from "../hooks/useApi";
import { ApiError } from "../lib/api";

const RESET_CONFIRM_PHRASE = "DELETE MY DATA";

export default function LockScreen() {
  const { data: status } = useStatus();
  const unlock = useUnlock();
  const [passphrase, setPassphrase] = useState("");
  const [showReset, setShowReset] = useState(false);
  const firstTime = status && !status.initialized;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    unlock.mutate(passphrase);
  };

  const errorMsg =
    unlock.error instanceof ApiError ? unlock.error.message : unlock.error ? "Failed" : null;

  return (
    <div className="flex min-h-screen items-center justify-center bg-ink-900 px-4">
      <div className="w-full max-w-sm">
        <div className="rounded-2xl bg-ink-800 p-8 shadow-xl">
          <div className="mb-6 flex flex-col items-center text-center">
            <ShieldCheck className="h-10 w-10 text-accent" />
            <h1 className="mt-3 text-xl font-bold text-slate-100">Blackline</h1>
            <p className="mt-1 text-sm text-slate-400">
              {firstTime ? "Create a passphrase to secure your vault" : "Unlock your local vault"}
            </p>
          </div>

          <form onSubmit={submit} className="space-y-4">
            <input
              type="password"
              autoFocus
              value={passphrase}
              onChange={(e) => setPassphrase(e.target.value)}
              placeholder={firstTime ? "New passphrase (min 8 chars)" : "Passphrase"}
              className="w-full rounded-lg border border-ink-700 px-3 py-2.5 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            />
            {firstTime && (
              <p className="text-xs text-amber-400">
                There is no recovery. If you lose this passphrase, your stored connection must be
                re-linked. Choose something strong and memorable.
              </p>
            )}
            {errorMsg && <p className="text-sm text-red-400">{errorMsg}</p>}
            <button
              type="submit"
              disabled={unlock.isPending || passphrase.length < 8}
              className="w-full rounded-lg bg-accent py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {unlock.isPending ? "Unlocking…" : firstTime ? "Create Vault" : "Unlock"}
            </button>
          </form>

          {!firstTime && (
            <div className="mt-5 border-t border-ink-700 pt-4 text-center">
              <button
                onClick={() => setShowReset((v) => !v)}
                className="text-xs text-slate-500 hover:text-slate-300 hover:underline"
              >
                Forgot your passphrase?
              </button>
            </div>
          )}
        </div>

        {showReset && !firstTime && <ResetVaultPanel onDone={() => setShowReset(false)} />}
      </div>
    </div>
  );
}

function ResetVaultPanel({ onDone }: { onDone: () => void }) {
  const reset = useResetVault();
  const [confirm, setConfirm] = useState("");
  const err = reset.error instanceof ApiError ? reset.error.message : null;

  return (
    <div className="mt-4 rounded-2xl border border-red-500/40 bg-red-950/40 p-6">
      <div className="flex items-center gap-2 font-semibold text-red-400">
        <AlertTriangle className="h-5 w-5" />
        Reset vault — destroys all data
      </div>
      <p className="mt-2 text-sm text-red-200/80">
        There is no passphrase recovery: the passphrase <em>is</em> the encryption key. The only
        way forward is to <strong>permanently destroy</strong> the vault — all accounts,
        transactions, net-worth history, budgets, rules, and your bank connection. This cannot
        be undone. Afterward you start fresh: new passphrase, new SimpleFIN setup token, and
        accounts re-sync from scratch.
      </p>
      <p className="mt-3 text-sm text-red-200/80">
        Type <span className="font-mono font-semibold text-red-300">{RESET_CONFIRM_PHRASE}</span>{" "}
        to confirm:
      </p>
      <input
        value={confirm}
        onChange={(e) => setConfirm(e.target.value)}
        placeholder={RESET_CONFIRM_PHRASE}
        className="mt-2 w-full rounded-lg border border-red-500/40 bg-transparent px-3 py-2 font-mono text-sm text-red-100 placeholder-red-200/30 focus:border-red-400 focus:outline-none focus:ring-1 focus:ring-red-400"
      />
      {err && <p className="mt-2 text-sm text-red-400">{err}</p>}
      <div className="mt-3 flex gap-2">
        <button
          onClick={() => reset.mutate(confirm)}
          disabled={confirm !== RESET_CONFIRM_PHRASE || reset.isPending}
          className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-40"
        >
          {reset.isPending ? "Destroying…" : "Destroy vault & start over"}
        </button>
        <button
          onClick={onDone}
          className="rounded-lg border border-red-500/30 px-4 py-2 text-sm text-red-200/80 hover:bg-red-900/40"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
