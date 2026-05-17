// Small fetch wrapper + React Query key registry. All API access in
// the app should go through this module so retries, error shape,
// and base-URL handling stay consistent.

export const API_BASE = "/api";

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

type Query = Record<string, string | number | boolean | null | undefined>;

function buildUrl(path: string, query?: Query): string {
  const base = path.startsWith("/") ? path : `/${path}`;
  const full = base.startsWith(API_BASE) ? base : `${API_BASE}${base}`;
  if (!query) return full;
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v === null || v === undefined) continue;
    params.append(k, String(v));
  }
  const qs = params.toString();
  return qs ? `${full}?${qs}` : full;
}

async function request<T>(
  method: string,
  path: string,
  options: { query?: Query; body?: unknown; signal?: AbortSignal } = {},
): Promise<T> {
  const url = buildUrl(path, options.query);
  const init: RequestInit = {
    method,
    signal: options.signal,
    headers: { Accept: "application/json" },
  };
  if (options.body !== undefined) {
    init.body = JSON.stringify(options.body);
    (init.headers as Record<string, string>)["Content-Type"] = "application/json";
  }
  const res = await fetch(url, init);
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      try {
        body = await res.text();
      } catch {
        /* ignore */
      }
    }
    const detail =
      (body && typeof body === "object" && "detail" in body && String((body as { detail: unknown }).detail)) ||
      res.statusText;
    throw new ApiError(`${method} ${url} failed (${res.status}): ${detail}`, res.status, body);
  }
  // 204 / empty body
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

export const api = {
  get: <T>(path: string, query?: Query, signal?: AbortSignal) =>
    request<T>("GET", path, { query, signal }),
  post: <T>(path: string, body?: unknown, query?: Query, signal?: AbortSignal) =>
    request<T>("POST", path, { body, query, signal }),
  put: <T>(path: string, body?: unknown, query?: Query, signal?: AbortSignal) =>
    request<T>("PUT", path, { body, query, signal }),
  del: <T>(path: string, query?: Query, signal?: AbortSignal) =>
    request<T>("DELETE", path, { query, signal }),
};

// Back-compat named exports — older route code expects them. The
// 2nd arg may be either a query object or an AbortSignal; we detect
// which at call time so consumers that wrote ``apiGet(path, signal)``
// keep working alongside the canonical ``api.get(path, query, signal)``.
function _isSignal(value: unknown): value is AbortSignal {
  return typeof AbortSignal !== "undefined" && value instanceof AbortSignal;
}

export function apiGet<T>(path: string, queryOrSignal?: Query | AbortSignal, signal?: AbortSignal): Promise<T> {
  if (_isSignal(queryOrSignal)) return api.get<T>(path, undefined, queryOrSignal);
  return api.get<T>(path, queryOrSignal as Query | undefined, signal);
}
export function apiPost<T>(path: string, body?: unknown, queryOrSignal?: Query | AbortSignal, signal?: AbortSignal): Promise<T> {
  if (_isSignal(queryOrSignal)) return api.post<T>(path, body, undefined, queryOrSignal);
  return api.post<T>(path, body, queryOrSignal as Query | undefined, signal);
}
export function apiPut<T>(path: string, body?: unknown, queryOrSignal?: Query | AbortSignal, signal?: AbortSignal): Promise<T> {
  if (_isSignal(queryOrSignal)) return api.put<T>(path, body, undefined, queryOrSignal);
  return api.put<T>(path, body, queryOrSignal as Query | undefined, signal);
}
export function apiDel<T>(path: string, queryOrSignal?: Query | AbortSignal, signal?: AbortSignal): Promise<T> {
  if (_isSignal(queryOrSignal)) return api.del<T>(path, undefined, queryOrSignal);
  return api.del<T>(path, queryOrSignal as Query | undefined, signal);
}

/** Build the WebSocket URL for the /api/events stream. Relative protocol
 * so it picks up ws://localhost:5173 in dev (Vite proxy) and wss://...
 * if the app is served over HTTPS. */
export function wsUrl(path: string, query?: Record<string, string | undefined>): string {
  const proto = typeof window !== "undefined" && window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = typeof window !== "undefined" ? window.location.host : "localhost";
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(query ?? {})) if (v) qs.set(k, v);
  const search = qs.toString();
  return `${proto}//${host}${path}${search ? `?${search}` : ""}`;
}

/**
 * Centralized React Query key registry. Using a registry (rather than
 * inline literals) keeps invalidation predictable across the app — when
 * an agent invalidates `queryKeys.sources.all()` from a mutation,
 * every list/detail consumer rerenders.
 */
export const queryKeys = {
  health: () => ["health"] as const,
  version: () => ["version"] as const,
  sources: {
    all: () => ["sources"] as const,
    detail: (name: string) => ["sources", name] as const,
    preview: (name: string, limit: number, offset: number) =>
      ["sources", name, "preview", { limit, offset }] as const,
    schema: (name: string) => ["sources", name, "schema"] as const,
  },
  rankings: (query: unknown) => ["rankings", query] as const,
  zips: {
    detail: (zcta5: string) => ["zips", zcta5] as const,
    compare: (zips: string[]) => ["zips", "compare", zips.slice().sort()] as const,
  },
  charts: {
    zhvi: (zcta5: string, since?: string) => ["charts", "zhvi", zcta5, since] as const,
    zori: (zcta5: string) => ["charts", "zori", zcta5] as const,
    redfin: (zcta5: string) => ["charts", "redfin", zcta5] as const,
    distribution: (dim: string) => ["charts", "distribution", dim] as const,
    scatter: (feature: string, score: string) => ["charts", "scatter", feature, score] as const,
  },
  schema: () => ["schema"] as const,
  manifest: {
    all: () => ["manifest"] as const,
    one: (source: string) => ["manifest", source] as const,
  },
  config: {
    list: () => ["config", "list"] as const,
    file: (name: string) => ["config", name] as const,
  },
  backtest: {
    runs: () => ["backtest", "runs"] as const,
    run: (id: number) => ["backtest", "runs", id] as const,
  },
  logs: () => ["refresh-log"] as const,
} as const;
