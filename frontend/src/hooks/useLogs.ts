import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/api/client";
import type { RefreshLogRow } from "@/api/types";

export interface LogsFilter {
  source?: string;
  status?: string;
  start?: string; // ISO date
  end?: string; // ISO date
}

function buildQuery(filter: LogsFilter): string {
  const params = new URLSearchParams();
  if (filter.source) params.set("source", filter.source);
  if (filter.status) params.set("status", filter.status);
  if (filter.start) params.set("start", filter.start);
  if (filter.end) params.set("end", filter.end);
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function useLogs(filter: LogsFilter = {}) {
  const qs = buildQuery(filter);
  return useQuery<RefreshLogRow[]>({
    queryKey: ["refresh-log", filter],
    queryFn: ({ signal }) =>
      apiGet<RefreshLogRow[]>(`/api/refresh-log${qs}`, signal),
    staleTime: 10_000,
  });
}
