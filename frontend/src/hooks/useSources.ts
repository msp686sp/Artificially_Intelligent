import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/api/client";
import type {
  PreviewPage,
  SourceSchema,
  SourceSummary,
} from "@/api/types";

export function useSources() {
  return useQuery<SourceSummary[]>({
    queryKey: ["sources"],
    queryFn: ({ signal }) => apiGet<SourceSummary[]>("/api/sources", signal),
    staleTime: 15_000,
  });
}

export function useSource(name: string) {
  return useQuery<SourceSummary>({
    queryKey: ["source", name],
    queryFn: ({ signal }) =>
      apiGet<SourceSummary>(`/api/sources/${encodeURIComponent(name)}`, signal),
    enabled: Boolean(name),
    staleTime: 15_000,
  });
}

export function useSourceSchema(name: string) {
  return useQuery<SourceSchema>({
    queryKey: ["source-schema", name],
    queryFn: ({ signal }) =>
      apiGet<SourceSchema>(
        `/api/sources/${encodeURIComponent(name)}/schema`,
        signal,
      ),
    enabled: Boolean(name),
    staleTime: 60_000,
    retry: 1,
  });
}

export function useSourcePreview(
  name: string,
  limit: number,
  offset: number,
) {
  return useQuery<PreviewPage>({
    queryKey: ["source-preview", name, limit, offset],
    queryFn: ({ signal }) =>
      apiGet<PreviewPage>(
        `/api/sources/${encodeURIComponent(name)}/preview?limit=${limit}&offset=${offset}`,
        signal,
      ),
    enabled: Boolean(name),
    retry: 1,
  });
}
