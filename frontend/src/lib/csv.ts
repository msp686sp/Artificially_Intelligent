// CSV export helper. Used by DataTable's toolbar "Export" button.
// Keeps the logic pure (string-in, string-out) so it's trivially unit-testable
// and works the same in tests as in the browser.

export type CsvValue = string | number | boolean | null | undefined;
// Permissive row shape — accept unknown values so callers don't have
// to narrow first; escapeCsvCell coerces to a string at write time.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type CsvRow = Record<string, any>;

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

/** Back-compat helper used by agent 7's SQL workbench, which calls
 *  ``rowsToCsv(columns, rows)`` where rows are array-of-arrays. */
export function rowsToCsv(
  columnsOrRows: string[] | CsvRow[],
  rows?: Array<Array<CsvValue>> | CsvRow[],
): string {
  // Two-arg shape: (columns: string[], rows: any[][]).
  if (rows !== undefined) {
    const cols = columnsOrRows as string[];
    const header = cols.map(escapeCsvCell).join(",");
    if ((rows as unknown[]).length === 0) return header;
    const body = (rows as unknown[]).map((row) => {
      if (Array.isArray(row)) {
        return (row as CsvValue[]).map(escapeCsvCell).join(",");
      }
      return cols
        .map((c) => escapeCsvCell((row as CsvRow)[c]))
        .join(",");
    }).join("\n");
    return `${header}\n${body}`;
  }
  // One-arg shape — delegate to toCsv.
  return toCsv(columnsOrRows as CsvRow[]);
}
