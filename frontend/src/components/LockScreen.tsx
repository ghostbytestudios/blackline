import { useState } from "react";
import { ShieldCheck } from "lucide-react";
import { useStatus, useUnlock } from "../hooks/useApi";
import { ApiError } from "../lib/api";

export default function LockScreen() {
  const { data: status } = useStatus();
  const unlock = useUnlock();
  const [passphrase, setPassphrase] = useState("");
  const firstTime = status && !status.initialized;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    unlock.mutate(passphrase);
  };

  const errorMsg =
    unlock.error instanceof ApiError ? unlock.error.message : unlock.error ? "Failed" : null;

  return (
    <div className="flex min-h-screen items-center justify-center bg-ink-900 px-4">
      <div className="w-full max-w-sm rounded-2xl bg-white p-8 shadow-xl">
        <div className="mb-6 flex flex-col items-center text-center">
          <ShieldCheck className="h-10 w-10 text-accent" />
          <h1 className="mt-3 text-xl font-bold text-slate-900">Blackline</h1>
          <p className="mt-1 text-sm text-slate-500">
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
            className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          />
          {firstTime && (
            <p className="text-xs text-amber-600">
              There is no recovery. If you lose this passphrase, your stored connection must be
              re-linked. Choose something strong and memorable.
            </p>
          )}
          {errorMsg && <p className="text-sm text-red-600">{errorMsg}</p>}
          <button
            type="submit"
            disabled={unlock.isPending || passphrase.length < 8}
            className="w-full rounded-lg bg-accent py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {unlock.isPending ? "Unlocking…" : firstTime ? "Create Vault" : "Unlock"}
          </button>
        </form>
      </div>
    </div>
  );
}
