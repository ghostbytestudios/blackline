import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type {
  Account,
  InsightCard,
  InsightsSummary,
  Status,
  SyncResult,
  Transaction,
} from "../lib/types";

export function useStatus() {
  return useQuery({ queryKey: ["status"], queryFn: () => api.get<Status>("/status") });
}

export function useUnlock() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (passphrase: string) => api.post<Status>("/unlock", { passphrase }),
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useLock() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<Status>("/lock"),
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useChangePassphrase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: { current: string; next: string }) =>
      api.post<Status>("/change-passphrase", {
        current_passphrase: b.current,
        new_passphrase: b.next,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["status"] }),
  });
}

export function useConnect() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (setup_token: string) => api.post<Status>("/connect", { setup_token }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["status"] }),
  });
}

export function useSync() {
  const qc = useQueryClient();
  return useMutation<SyncResult, Error, number>({
    mutationFn: (lookbackDays) =>
      api.post<SyncResult>(`/sync?lookback_days=${lookbackDays}`),
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useAccounts(enabled = true) {
  return useQuery({
    queryKey: ["accounts"],
    queryFn: () => api.get<Account[]>("/accounts"),
    enabled,
  });
}

export function useTransactions(params: { accountId?: number; category?: string } = {}) {
  const search = new URLSearchParams();
  if (params.accountId) search.set("account_id", String(params.accountId));
  if (params.category) search.set("category", params.category);
  const qs = search.toString();
  return useQuery({
    queryKey: ["transactions", params],
    queryFn: () => api.get<Transaction[]>(`/transactions${qs ? `?${qs}` : ""}`),
  });
}

export function useInsights(days = 90) {
  return useQuery({
    queryKey: ["insights", days],
    queryFn: () => api.get<InsightsSummary>(`/insights/summary?days=${days}`),
  });
}

export function useInsightCards(days = 180) {
  return useQuery({
    queryKey: ["insight-cards", days],
    queryFn: () => api.get<InsightCard[]>(`/insights/cards?days=${days}`),
  });
}

export function useSetCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, category }: { id: number; category: string }) =>
      api.patch<Transaction>(`/transactions/${id}/category`, { category }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["transactions"] });
      qc.invalidateQueries({ queryKey: ["insights"] });
    },
  });
}
