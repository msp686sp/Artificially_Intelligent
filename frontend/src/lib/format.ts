/**
 * Display formatters. Cheap, pure, no I/O.
 */

export function formatNumber(
  value: number | null | undefined,
  opts: { decimals?: number; suffix?: string; placeholder?: string } = {},
): string {
  const { decimals = 2, suffix = "", placeholder = "—" } = opts;
  if (value === null || value === undefined || Number.isNaN(value)) return placeholder;
  return `${value.toFixed(decimals)}${suffix}`;
}

export function formatPct(
  value: number | null | undefined,
  opts: { decimals?: number; placeholder?: string } = {},
): string {
  const { decimals = 2, placeholder = "—" } = opts;
  if (value === null || value === undefined || Number.isNaN(value)) return placeholder;
  return `${value.toFixed(decimals)}%`;
}

export function formatCurrency(
  value: number | null | undefined,
  opts: { decimals?: number; placeholder?: string } = {},
): string {
  const { decimals = 0, placeholder = "—" } = opts;
  if (value === null || value === undefined || Number.isNaN(value)) return placeholder;
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function scoreColorClass(score: number | null | undefined): string {
  if (score === null || score === undefined || Number.isNaN(score)) return "text-fg-subtle";
  if (score >= 70) return "text-score-high";
  if (score >= 40) return "text-score-mid";
  return "text-score-low";
}

export function scoreBgClass(score: number | null | undefined): string {
  if (score === null || score === undefined || Number.isNaN(score)) return "bg-bg-subtle";
  if (score >= 70) return "bg-score-high/20";
  if (score >= 40) return "bg-score-mid/20";
  return "bg-score-low/20";
}
