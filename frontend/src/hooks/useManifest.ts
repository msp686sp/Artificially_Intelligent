import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/api/client";
import type { ManifestEntry } from "@/api/types";

export function useManifest() {
  return useQuery<ManifestEntry[]>({
    queryKey: ["manifest"],
    queryFn: ({ signal }) => apiGet<ManifestEntry[]>("/api/manifest", signal),
    staleTime: 15_000,
  });
}

export function useManifestEntry(source: string) {
  return useQuery<ManifestEntry>({
    queryKey: ["manifest", source],
    queryFn: ({ signal }) =>
      apiGet<ManifestEntry>(
        `/api/manifest/${encodeURIComponent(source)}`,
        signal,
      ),
    enabled: Boolean(source),
    staleTime: 15_000,
  });
}
