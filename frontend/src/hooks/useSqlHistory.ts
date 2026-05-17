import { useCallback, useEffect, useState } from "react";

export interface SqlHistoryEntry {
  query: string;
  ranAt: string; // ISO timestamp
  rowCount?: number;
  elapsedMs?: number;
  ok: boolean;
}

const HISTORY_KEY = "sql.history.v1";
const SAVED_KEY = "sql.saved.v1";
const MAX_HISTORY = 20;

function safeGetLocalStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function readJson<T>(key: string, fallback: T): T {
  const ls = safeGetLocalStorage();
  if (!ls) return fallback;
  try {
    const raw = ls.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function writeJson(key: string, value: unknown): void {
  const ls = safeGetLocalStorage();
  if (!ls) return;
  try {
    ls.setItem(key, JSON.stringify(value));
  } catch {
    /* ignore quota errors */
  }
}

/**
 * Returns the last N (default 20) sql queries with `push` and `clear`. The
 * most recent entry is first. Duplicates of the just-pushed query at the
 * head are coalesced so spamming Run doesn't fill the buffer.
 */
export function useSqlHistory(max: number = MAX_HISTORY) {
  const [history, setHistory] = useState<SqlHistoryEntry[]>(() =>
    readJson<SqlHistoryEntry[]>(HISTORY_KEY, []),
  );

  useEffect(() => {
    writeJson(HISTORY_KEY, history);
  }, [history]);

  const push = useCallback(
    (entry: SqlHistoryEntry) => {
      setHistory((prev) => {
        const trimmed = entry.query.trim();
        if (!trimmed) return prev;
        const head = prev[0];
        const next =
          head && head.query.trim() === trimmed ? prev.slice(1) : prev;
        return [{ ...entry, query: trimmed }, ...next].slice(0, max);
      });
    },
    [max],
  );

  const clear = useCallback(() => setHistory([]), []);

  const remove = useCallback((index: number) => {
    setHistory((prev) => prev.filter((_, i) => i !== index));
  }, []);

  return { history, push, clear, remove };
}

export interface SavedQuery {
  name: string;
  query: string;
  savedAt: string;
}

export function useSavedQueries() {
  const [saved, setSaved] = useState<SavedQuery[]>(() =>
    readJson<SavedQuery[]>(SAVED_KEY, []),
  );

  useEffect(() => {
    writeJson(SAVED_KEY, saved);
  }, [saved]);

  const save = useCallback((name: string, query: string) => {
    const trimmedName = name.trim();
    const trimmedQuery = query.trim();
    if (!trimmedName || !trimmedQuery) return;
    setSaved((prev) => {
      const next = prev.filter((q) => q.name !== trimmedName);
      return [
        { name: trimmedName, query: trimmedQuery, savedAt: new Date().toISOString() },
        ...next,
      ];
    });
  }, []);

  const remove = useCallback((name: string) => {
    setSaved((prev) => prev.filter((q) => q.name !== name));
  }, []);

  return { saved, save, remove };
}
