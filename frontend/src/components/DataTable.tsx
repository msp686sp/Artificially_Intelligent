import { useMemo, useState } from "react";
import type { ReactNode } from "react";

export interface DataTableColumn<T> {
  key: string;
  header: ReactNode;
  /** Read the displayed value for a row. */
  accessor: (row: T) => ReactNode;
  /** Optional numeric/string used for sorting; defaults to the accessor. */
  sortValue?: (row: T) => number | string | null | undefined;
  sortable?: boolean;
}

interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  rows: T[];
  rowKey: (row: T, index: number) => string;
  emptyMessage?: ReactNode;
}

type SortDir = "asc" | "desc";

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  emptyMessage,
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const sorted = useMemo(() => {
    if (!sortKey) return rows;
    const col = columns.find((c) => c.key === sortKey);
    if (!col) return rows;
    const valueFor = (row: T) => {
      if (col.sortValue) return col.sortValue(row);
      const v = col.accessor(row);
      // Fallback: stringify React nodes
      if (typeof v === "number" || typeof v === "string") return v;
      if (v === null || v === undefined) return null;
      return String(v);
    };
    const sortedRows = [...rows].sort((a, b) => {
      const va = valueFor(a);
      const vb = valueFor(b);
      if (va === null || va === undefined) return 1;
      if (vb === null || vb === undefined) return -1;
      if (typeof va === "number" && typeof vb === "number") return va - vb;
      return String(va).localeCompare(String(vb));
    });
    return sortDir === "asc" ? sortedRows : sortedRows.reverse();
  }, [columns, rows, sortKey, sortDir]);

  function toggleSort(key: string, sortable: boolean | undefined) {
    if (!sortable) return;
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  if (rows.length === 0) {
    return (
      <div className="empty-state">{emptyMessage ?? "No rows to display."}</div>
    );
  }

  return (
    <table className="data-table">
      <thead>
        <tr>
          {columns.map((c) => (
            <th
              key={c.key}
              onClick={() => toggleSort(c.key, c.sortable)}
              style={{ cursor: c.sortable ? "pointer" : "default" }}
              scope="col"
            >
              {c.header}
              {c.sortable && sortKey === c.key
                ? sortDir === "asc"
                  ? " ▲"
                  : " ▼"
                : ""}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {sorted.map((row, idx) => (
          <tr key={rowKey(row, idx)}>
            {columns.map((c) => (
              <td
                key={c.key}
                data-label={typeof c.header === "string" ? c.header : c.key}
              >
                {c.accessor(row)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
