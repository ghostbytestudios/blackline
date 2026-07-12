import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type {
  Account,
  AuditPage,
  BackupInfo,
  BudgetHistory,
  BudgetStatus,
  CategoryRule,
  DashboardSummary,
  ForecastSummary,
  Goal,
  InsightCard,
  InsightsSummary,
  ColumnMapping,
  ImportPreview,
  ImportResult,
  MerchantSummary,
  NetWorthPoint,
  PortfolioPoint,
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
  params: { accountId?: number; category?: string; q?: string; tag?: string; limit?: number } = {},
) {
  const search = new URLSearchParams();
  if (params.accountId) search.set("account_id", String(params.accountId));
  if (params.category) search.set("category", params.category);
  if (params.q) search.set("q", params.q);
  if (params.tag) search.set("tag", params.tag);
  if (params.limit) search.set("limit", String(params.limit));
  const qs = search.toString();
  return useQuery({
    queryKey: ["transactions", params],
    queryFn: () => api.get<Transaction[]>(`/transactions${qs ? `?${qs}` : ""}`),
  });
}

export function useAnnotateTransaction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: number; note?: string | null; tags?: string[] }) =>
      api.patch<Transaction>(`/transactions/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["transactions"] }),
  });
}

export function useMerchants(days = 365) {
  return useQuery({
    queryKey: ["merchants", days],
    queryFn: () => api.get<MerchantSummary[]>(`/merchants?days=${days}`),
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
    mutationFn: (b: { category: string; limit_minor: number; rollover?: boolean }) =>
      api.put<BudgetStatus>("/budgets", b),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["budgets"] });
      qc.invalidateQueries({ queryKey: ["budget-history"] });
      qc.invalidateQueries({ queryKey: ["insight-cards"] });
    },
  });
}

export function useBudgetHistory(months = 6) {
  return useQuery({
    queryKey: ["budget-history", months],
    queryFn: () => api.get<BudgetHistory[]>(`/budgets/history?months=${months}`),
  });
}

export function useGoals() {
  return useQuery({ queryKey: ["goals"], queryFn: () => api.get<Goal[]>("/goals") });
}

export function useCreateGoal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (g: {
      name: string;
      target_minor: number;
      target_date?: string | null;
      account_ids: number[];
    }) => api.post<Goal>("/goals", g),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["goals"] }),
  });
}

export function useDeleteGoal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.del<void>(`/goals/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["goals"] }),
  });
}

export function usePortfolioHistory() {
  return useQuery({
    queryKey: ["portfolio-history"],
    queryFn: () => api.get<PortfolioPoint[]>("/portfolio/history"),
  });
}

export function useForecast(days = 30) {
  return useQuery({
    queryKey: ["forecast", days],
    queryFn: () => api.get<ForecastSummary>(`/forecast?days=${days}`),
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
    // Partial update; net_monthly_income_minor: null clears the manual override.
    mutationFn: (b: {
      gross_annual_income_minor?: number;
      net_monthly_income_minor?: number | null;
    }) => api.put<Profile>("/profile", b),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["profile"] });
      qc.invalidateQueries({ queryKey: ["insight-cards"] });
    },
  });
}

export function useRules() {
  return useQuery({ queryKey: ["rules"], queryFn: () => api.get<CategoryRule[]>("/rules") });
}

export function useAddRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: { pattern: string; category: string; priority?: number }) =>
      api.post<{ rule_id: number }>("/rules", b),
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useDeleteRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.del<{ deleted: number }>(`/rules/${id}`),
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useMatchTransfers() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<{ pairs_matched: number }>("/transfers/match"),
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useSplitTransaction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      parts,
    }: {
      id: number;
      parts: { category: string; amount_minor: number; note?: string | null }[];
    }) => api.post<Transaction[]>(`/transactions/${id}/split`, { parts }),
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useUnsplitTransaction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.del<Transaction>(`/transactions/${id}/split`),
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useImportPreview() {
  return useMutation({
    mutationFn: (b: { filename: string; content: string }) =>
      api.post<ImportPreview>("/import/preview", b),
  });
}

export function useImportCommit() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: {
      filename: string;
      content: string;
      account_id: number;
      mapping?: ColumnMapping | null;
      skip_duplicates?: boolean;
    }) => api.post<ImportResult>("/import/commit", b),
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useCreateManualAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: { name: string; account_type?: string; balance_minor?: number }) =>
      api.post<Account>("/accounts/manual", b),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
  });
}

export function useAuditLog(limit = 20, offset = 0) {
  return useQuery({
    queryKey: ["audit", limit, offset],
    queryFn: () => api.get<AuditPage>(`/audit?limit=${limit}&offset=${offset}`),
  });
}

export function useBackups() {
  return useQuery({
    queryKey: ["backups"],
    queryFn: () => api.get<BackupInfo[]>("/backups"),
  });
}

export function useRestoreBackup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: { name: string; confirm: string }) =>
      api.post<Status>("/backups/restore", b),
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useImportVault() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: { bundle: string; confirm?: string }) =>
      api.post<Status>("/vault/import", b),
    onSuccess: () => qc.invalidateQueries(),
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
