import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type {
  Account,
  BudgetStatus,
  DashboardSummary,
  InsightCard,
  InsightsSummary,
  NetWorthPoint,
  PortfolioSummary,
  Profile,
  RecurringCharge,
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

export function useResetVault() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (confirm: string) => api.post<Status>("/reset-vault", { confirm }),
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useSeedDemo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      api.post<{ accounts: number; transactions: number }>("/demo/seed"),
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useRemoveDemo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.del<{ accounts_removed: number }>("/demo"),
    onSuccess: () => qc.invalidateQueries(),
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

export function useUpdateAccountSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      ...body
    }: {
      id: number;
      type_override?: string | null;
      goal_name?: string | null;
      goal_target_minor?: number | null;
    }) => api.patch<Account>(`/accounts/${id}/settings`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["accounts"] });
      qc.invalidateQueries({ queryKey: ["insight-cards"] });
      qc.invalidateQueries({ queryKey: ["insights"] });
    },
  });
}

export function useTransactions(
  params: { accountId?: number; category?: string; limit?: number } = {},
) {
  const search = new URLSearchParams();
  if (params.accountId) search.set("account_id", String(params.accountId));
  if (params.category) search.set("category", params.category);
  if (params.limit) search.set("limit", String(params.limit));
  const qs = search.toString();
  return useQuery({
    queryKey: ["transactions", params],
    queryFn: () => api.get<Transaction[]>(`/transactions${qs ? `?${qs}` : ""}`),
  });
}

export function useDashboard() {
  return useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api.get<DashboardSummary>("/dashboard/summary"),
  });
}

export function useInsights(days = 90) {
  return useQuery({
    queryKey: ["insights", days],
    queryFn: () => api.get<InsightsSummary>(`/insights/summary?days=${days}`),
  });
}

export function usePortfolio() {
  return useQuery({
    queryKey: ["portfolio"],
    queryFn: () => api.get<PortfolioSummary>("/portfolio"),
  });
}

export function useRecurring() {
  return useQuery({
    queryKey: ["recurring"],
    queryFn: () => api.get<RecurringCharge[]>("/recurring"),
  });
}

export function useNetWorthHistory() {
  return useQuery({
    queryKey: ["networth-history"],
    queryFn: () => api.get<NetWorthPoint[]>("/networth/history"),
  });
}

export function useInsightCards(days = 180) {
  return useQuery({
    queryKey: ["insight-cards", days],
    queryFn: () => api.get<InsightCard[]>(`/insights/cards?days=${days}`),
  });
}

export function useBudgets() {
  return useQuery({ queryKey: ["budgets"], queryFn: () => api.get<BudgetStatus[]>("/budgets") });
}

export function useSetBudget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: { category: string; limit_minor: number }) =>
      api.put<BudgetStatus>("/budgets", b),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["budgets"] });
      qc.invalidateQueries({ queryKey: ["insight-cards"] });
    },
  });
}

export function useDeleteBudget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (category: string) => api.del<void>(`/budgets/${encodeURIComponent(category)}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["budgets"] });
      qc.invalidateQueries({ queryKey: ["insight-cards"] });
    },
  });
}

export function useSuggestBudgets() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<BudgetStatus[]>("/budgets/suggest"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["budgets"] });
      qc.invalidateQueries({ queryKey: ["insight-cards"] });
    },
  });
}

export function useProfile() {
  return useQuery({ queryKey: ["profile"], queryFn: () => api.get<Profile>("/profile") });
}

export function useSetProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (gross_annual_income_minor: number) =>
      api.put<Profile>("/profile", { gross_annual_income_minor }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["profile"] });
      qc.invalidateQueries({ queryKey: ["insight-cards"] });
    },
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
