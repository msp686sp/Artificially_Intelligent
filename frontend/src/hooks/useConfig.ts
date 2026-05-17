import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../api/client";
import type { ConfigFile } from "../api/types";

export function useConfigFile(file: string | undefined) {
  return useQuery<ConfigFile>({
    queryKey: ["config", file],
    queryFn: ({ signal }) =>
      apiFetch<ConfigFile>(`/api/config/${file}`, { signal }),
    enabled: !!file,
  });
}

export function useSaveConfig(file: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: ["config", "save", file],
    mutationFn: async (content: string) => {
      await apiFetch<void>(`/api/config/${file}`, {
        method: "PUT",
        body: { content },
      });
      return content;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["config", file] });
      qc.invalidateQueries({ queryKey: ["rankings"] });
    },
  });
}
