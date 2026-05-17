import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import type { SchemaTree } from "@/api/types";

export const schemaQueryKey = ["schema"] as const;

export function useSchema() {
  return useQuery<SchemaTree>({
    queryKey: schemaQueryKey,
    queryFn: () => apiFetch<SchemaTree>("/schema"),
    staleTime: 5 * 60_000,
  });
}
