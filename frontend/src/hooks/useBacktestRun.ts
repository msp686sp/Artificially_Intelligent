import { useQueries, useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import type { BacktestRunDetail } from "@/api/types";

export function backtestRunQueryKey(id: string) {
  return ["backtest", "run", id] as const;
}

export function useBacktestRun(id: string | undefined) {
  return useQuery<BacktestRunDetail>({
    queryKey: backtestRunQueryKey(id ?? ""),
    queryFn: () => apiFetch<BacktestRunDetail>(`/backtest/runs/${id}`),
    enabled: Boolean(id),
  });
}

export function useBacktestRunsByIds(ids: string[]) {
  return useQueries({
    queries: ids.map((id) => ({
      queryKey: backtestRunQueryKey(id),
      queryFn: () => apiFetch<BacktestRunDetail>(`/backtest/runs/${id}`),
      enabled: Boolean(id),
    })),
  });
}
