import { useMutation } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import type { SqlRequest, SqlResponse } from "@/api/types";

/**
 * Mutation hook for `/api/sql`. The SQL workbench triggers it manually on Run.
 * Returns the data, error, and `mutate(req)` you call to execute.
 */
export function useSql() {
  return useMutation<SqlResponse, Error, SqlRequest>({
    mutationFn: (req) =>
      apiFetch<SqlResponse>("/sql", {
        method: "POST",
        body: JSON.stringify(req),
      }),
  });
}
