import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/api/client";
import type { HealthInfo, VersionInfo } from "@/api/types";

export function useVersion() {
  return useQuery<VersionInfo>({
    queryKey: ["version"],
    queryFn: ({ signal }) => apiGet<VersionInfo>("/api/version", signal),
    staleTime: 60_000,
  });
}

export function useHealth() {
  return useQuery<HealthInfo>({
    queryKey: ["health"],
    queryFn: ({ signal }) => apiGet<HealthInfo>("/api/health", signal),
    refetchInterval: 30_000,
    staleTime: 10_000,
  });
}

export function useRankings(limit = 5) {
  return useQuery({
    queryKey: ["rankings-top", limit],
    queryFn: async ({ signal }) =>
      apiGet<{ rows: Array<Record<string, unknown>> }>(
        `/api/rankings?limit=${limit}&sort=market_score&order=desc`,
        signal,
      ),
    staleTime: 60_000,
    retry: 0,
  });
}
