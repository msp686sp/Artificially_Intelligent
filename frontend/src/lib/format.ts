// Centralized formatters so columns/cards/charts render numbers the
// same way everywhere. All functions are pure and locale-aware via
// Intl.* — they fall back to "—" for nullish input so the UI never
// shows "null" or "NaN".

const EMPTY = "—";

export function isNullish(value: unknown): value is null | undefined {
  return value === null || value === undefined;
}

/**
 * Format an integer or float with thousands separators.
 * Returns "—" for null/undefined/NaN.
 */
export function formatNumber(
  value: number | string | null | undefined | unknown,
  options: { decimals?: number; compact?: boolean; suffix?: string } = {},
): string {
  if (isNullish(value)) return EMPTY;
  const n = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(n)) return EMPTY;
  const { decimals, compact, suffix } = options;
  const formatter = new Intl.NumberFormat("en-US", {
    notation: compact ? "compact" : "standard",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals ?? (compact ? 1 : 2),
  });
  return suffix ? `${formatter.format(n)}${suffix}` : formatter.format(n);
}

/**
 * Format USD currency (no fractional cents by default).
 * Returns "—" for null/undefined/NaN.
 */
export function formatCurrency(
  value: number | null | undefined,
  options: { decimals?: number; compact?: boolean } = {},
): string {
  if (isNullish(value) || Number.isNaN(value)) return EMPTY;
  const { decimals = 0, compact } = options;
  const formatter = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: compact ? "compact" : "standard",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  return formatter.format(value as number);
}

/**
 * Format a percentage. Input is treated as a percentage already
 * (e.g. 5.2 → "5.2%"). For 0–1 ratios, pass `{ asRatio: true }`.
 */
export function formatPercent(
  value: number | null | undefined,
  options: { decimals?: number; asRatio?: boolean } = {},
): string {
  if (isNullish(value) || Number.isNaN(value)) return EMPTY;
  const { decimals = 1, asRatio = false } = options;
  const pct = asRatio ? (value as number) * 100 : (value as number);
  return `${pct.toFixed(decimals)}%`;
}

/**
 * Format an ISO date (or Date) as a human-friendly short form.
 * Returns "—" for null/undefined/invalid input.
 */
export function formatDate(
  value: string | Date | null | undefined,
  options: { style?: "short" | "medium" | "long" | "iso" } = {},
): string {
  if (isNullish(value)) return EMPTY;
  const date = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return EMPTY;
  const { style = "medium" } = options;
  if (style === "iso") return date.toISOString().slice(0, 10);
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: style,
  }).format(date);
}

/**
 * Human "time ago" (e.g. "5 minutes ago", "3 days ago"). Useful for
 * status cards showing last-refresh age.
 */
export function formatRelativeTime(
  value: string | Date | null | undefined,
  now: Date = new Date(),
): string {
  if (isNullish(value)) return EMPTY;
  const date = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return EMPTY;
  const diffSeconds = Math.round((date.getTime() - now.getTime()) / 1000);
  const absSeconds = Math.abs(diffSeconds);
  const rtf = new Intl.RelativeTimeFormat("en-US", { numeric: "auto" });
  const ranges: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ["year", 60 * 60 * 24 * 365],
    ["month", 60 * 60 * 24 * 30],
    ["week", 60 * 60 * 24 * 7],
    ["day", 60 * 60 * 24],
    ["hour", 60 * 60],
    ["minute", 60],
    ["second", 1],
  ];
  for (const [unit, secs] of ranges) {
    if (absSeconds >= secs || unit === "second") {
      return rtf.format(Math.round(diffSeconds / secs), unit);
    }
  }
  return EMPTY;
}

/**
 * Convert seconds to a compact duration string ("3m 12s", "1h 4m").
 */
export function formatDuration(seconds: number | null | undefined): string {
  if (isNullish(seconds) || Number.isNaN(seconds) || seconds < 0) return EMPTY;
  const s = Math.floor(seconds as number);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rs = s % 60;
  if (m < 60) return rs ? `${m}m ${rs}s` : `${m}m`;
  const h = Math.floor(m / 60);
  const rm = m % 60;
  return rm ? `${h}h ${rm}m` : `${h}h`;
}

export const EMPTY_VALUE = EMPTY;

/** Tailwind class for a score band (high/mid/low). Used by rankings cells. */
export function scoreColorClass(score: number | null | undefined): string {
  if (score == null || Number.isNaN(score)) return "text-fg-muted";
  if (score >= 1) return "text-success";
  if (score >= -1) return "text-fg";
  return "text-danger";
}

/** Tailwind background class for a score band, mirrors scoreColorClass. */
export function scoreBgClass(score: number | null | undefined): string {
  if (score == null || Number.isNaN(score)) return "bg-bg-subtle";
  if (score >= 1) return "bg-success/20";
  if (score >= -1) return "bg-bg-panel";
  return "bg-danger/20";
}
