import { useCallback, useEffect, useState } from "react";

/**
 * useColumnVisibility — persisted state for TanStack Table's column
 * visibility, keyed by a table-name string so each DataTable can have
 * its own user preferences.
 */
export function useColumnVisibility(
  tableKey: string,
  defaults: Record<string, boolean> = {},
): [Record<string, boolean>, (next: Record<string, boolean>) => void] {
  const storageKey = `rental.gooey.cols.${tableKey}`;
  const [state, setState] = useState<Record<string, boolean>>(() => {
    if (typeof window === "undefined") return defaults;
    try {
      const raw = window.localStorage.getItem(storageKey);
      if (!raw) return defaults;
      const parsed = JSON.parse(raw) as Record<string, boolean>;
      return { ...defaults, ...parsed };
    } catch {
      return defaults;
    }
  });

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(state));
    } catch {
      /* ignore quota / private-mode errors */
    }
  }, [storageKey, state]);

  const set = useCallback((next: Record<string, boolean>) => {
    setState(next);
  }, []);

  return [state, set];
}
