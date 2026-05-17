import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { apiFetch, buildQuery } from "../api/client";
import type { RankingsResponse, SortOrder } from "../api/types";

export interface UseRankingsArgs {
  state?: string;
  metro?: string;
  minScore?: number;
  maxScore?: number;
  sort?: string;
  order?: SortOrder;
  limit?: number;
  offset?: number;
  filtersYaml?: string;
  /** Disable the query (e.g. while editing). */
  enabled?: boolean;
}

export function useRankings(args: UseRankingsArgs = {}) {
  const params = {
    state: args.state,
    metro: args.metro,
    min_score: args.minScore,
    max_score: args.maxScore,
    sort: args.sort,
    order: args.order,
    limit: args.limit ?? 50,
    offset: args.offset ?? 0,
    filters_yaml: args.filtersYaml,
  };
  const qs = buildQuery(params);
  return useQuery<RankingsResponse>({
    queryKey: ["rankings", params],
    queryFn: ({ signal }) => apiFetch<RankingsResponse>(`/api/rankings${qs}`, { signal }),
    placeholderData: keepPreviousData,
    enabled: args.enabled ?? true,
  });
}
