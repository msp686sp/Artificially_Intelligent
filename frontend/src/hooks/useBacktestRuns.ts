import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import type {
  BacktestRunSummary,
  JobResponse,
  RunRequest,
  TuneRequest,
} from "@/api/types";

export const backtestRunsQueryKey = ["backtest", "runs"] as const;

export function useBacktestRuns() {
  return useQuery<BacktestRunSummary[]>({
    queryKey: backtestRunsQueryKey,
    queryFn: () => apiFetch<BacktestRunSummary[]>("/backtest/runs"),
    refetchInterval: 5_000,
  });
}

export function useStartBacktestRun() {
  const qc = useQueryClient();
  return useMutation<JobResponse, Error, RunRequest>({
    mutationFn: (req) =>
      apiFetch<JobResponse>("/backtest/run", {
        method: "POST",
        body: JSON.stringify(req),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: backtestRunsQueryKey });
    },
  });
}

export function useStartBacktestTune() {
  const qc = useQueryClient();
  return useMutation<JobResponse, Error, TuneRequest>({
    mutationFn: (req) =>
      apiFetch<JobResponse>("/backtest/tune", {
        method: "POST",
        body: JSON.stringify(req),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: backtestRunsQueryKey });
    },
  });
}
