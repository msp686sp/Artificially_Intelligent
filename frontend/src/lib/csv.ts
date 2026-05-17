// CSV export helper. Used by DataTable's toolbar "Export" button.
// Keeps the logic pure (string-in, string-out) so it's trivially unit-testable
// and works the same in tests as in the browser.

export type CsvValue = string | number | boolean | null | undefined;
export type CsvRow = Record<string, CsvValue>;

/**
 * Escape a single CSV cell. RFC 4180: wrap in double quotes if the value
 * contains a comma, quote, or newline; double up embedded quotes.
 */
export function escapeCsvCell(value: CsvValue): string {
  if (value === null || value === undefined) return "";
  const str = String(value);
  if (/[",\n\r]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

/**
 * Convert an array of objects to a CSV string. Column order is taken
 * from the first row's keys; pass `columns` to control order or to
 * include keys absent from the first row.
 */
export function toCsv<T extends CsvRow>(rows: T[], columns?: string[]): string {
  if (rows.length === 0 && !columns) return "";
  const cols = columns ?? Object.keys(rows[0] ?? {});
  const header = cols.map(escapeCsvCell).join(",");
  const body = rows.map((row) => cols.map((c) => escapeCsvCell(row[c])).join(",")).join("\n");
  return body ? `${header}\n${body}` : header;
}

/**
 * Browser-only: trigger a file download for a CSV blob.
 * No-op in non-DOM environments (e.g. SSR/tests without jsdom).
 */
export function downloadCsv(filename: string, csv: string): void {
  if (typeof window === "undefined" || typeof document === "undefined") return;
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename.endsWith(".csv") ? filename : `${filename}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
