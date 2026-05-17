import { useQuery, type UseQueryOptions, type QueryKey } from "@tanstack/react-query";
import { api, ApiError } from "@/api/client";

/**
 * Thin wrapper around useQuery that defaults the fetcher to the
 * shared `api.get` helper. Use it when a hook just needs to GET a
 * URL and surface the typed payload. For mutations, use react-query's
 * `useMutation` directly with `api.post / api.put` from `@/api/client`.
 *
 * @example
 *   const sources = useApi<SourceSummary[]>(
 *     queryKeys.sources.all(),
 *     "/sources"
 *   );
 */
export function useApi<TData>(
  key: QueryKey,
  path: string,
  options?: Omit<UseQueryOptions<TData, ApiError, TData, QueryKey>, "queryKey" | "queryFn">,
) {
  return useQuery<TData, ApiError, TData, QueryKey>({
    queryKey: key,
    queryFn: ({ signal }) => api.get<TData>(path, undefined, signal),
    ...options,
  });
}
