// Minimal fetch wrapper. Returns JSON or throws on non-2xx.
//
// The OpenAPI-generated client (agent 1) will replace this; until then
// pages use these helpers via the typed hooks in ../hooks/.

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly statusText: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(path, { signal });
  if (!res.ok) {
    let body = "";
    try {
      body = await res.text();
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, res.statusText, body || res.statusText);
  }
  return (await res.json()) as T;
}

export async function apiPost<T, B = unknown>(
  path: string,
  body?: B,
  signal?: AbortSignal,
): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  if (!res.ok) {
    let text = "";
    try {
      text = await res.text();
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, res.statusText, text || res.statusText);
  }
  // Empty body is fine for fire-and-forget; cast to T.
  const ct = res.headers.get("content-type") || "";
  if (!ct.includes("application/json")) {
    return undefined as unknown as T;
  }
  return (await res.json()) as T;
}

// Compute the WebSocket URL for the events stream. In dev the page is
// served by Vite on a different port from the API, so we point at the
// API host directly (the Vite proxy doesn't relay WS by default).
export function wsUrl(path: string): string {
  if (typeof window === "undefined") return path;
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.hostname;
  // In dev (Vite on 5173), the API lives on 8000; in prod the page is
  // served by FastAPI itself so reuse the same port.
  const port =
    window.location.port === "5173" ? "8000" : window.location.port;
  const portSuffix = port ? `:${port}` : "";
  return `${proto}//${host}${portSuffix}${path}`;
}
