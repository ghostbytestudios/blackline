import { useState } from "react";
import { CheckCircle2, RefreshCw, Link2, AlertCircle } from "lucide-react";
import { useConnect, useStatus, useSync } from "../hooks/useApi";
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

      <Card>
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
