// Lightweight fetch wrapper. fe-shell (agent 4) will likely replace this with
// a generated OpenAPI client; the surface here is intentionally minimal.

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, message: string, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export interface RequestOptions extends RequestInit {
  query?: Record<string, string | number | boolean | undefined | null>;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const base = path.startsWith("/api") ? path : `/api${path}`;
  if (!query) return base;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null) continue;
    params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${base}?${qs}` : base;
}

export async function apiFetch<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { query, headers, ...rest } = options;
  const res = await fetch(buildUrl(path, query), {
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(headers ?? {}),
    },
    ...rest,
  });
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      try {
        body = await res.text();
      } catch {
        body = null;
      }
    }
    const message =
      (body && typeof body === "object" && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : null) ?? `${res.status} ${res.statusText}`;
    throw new ApiError(res.status, message, body);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function apiFetchText(
  path: string,
  options: RequestOptions = {},
): Promise<string> {
  const { query, headers, ...rest } = options;
  const res = await fetch(buildUrl(path, query), {
    headers: {
      Accept: "text/html, text/plain, */*",
      ...(headers ?? {}),
    },
    ...rest,
  });
  if (!res.ok) {
    throw new ApiError(res.status, `${res.status} ${res.statusText}`, null);
  }
  return res.text();
}
