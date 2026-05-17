import { flexRender, type Table } from "@tanstack/react-table";
import { useEffect, useState } from "react";
import { cx } from "../lib/cx";

export interface DataTableProps<T> {
  table: Table<T>;
  /** When true, renders stacked cards (mobile fallback). */
  forceCardMode?: boolean;
  density?: "comfortable" | "compact";
  /** Optional row key click handler. */
  onRowClick?: (row: T) => void;
  /** Optional empty-state message. */
  emptyMessage?: string;
}

export function DataTable<T>({
  table,
  forceCardMode,
  density = "comfortable",
  onRowClick,
  emptyMessage = "No rows.",
}: DataTableProps<T>) {
  const isMobile = useIsMobile();
  const useCards = forceCardMode ?? isMobile;
  const rows = table.getRowModel().rows;
  if (rows.length === 0) {
    return <div className="rounded-lg border border-bg-panel bg-bg-subtle p-4 text-sm text-fg-muted">{emptyMessage}</div>;
  }
  if (useCards) {
    return <CardList table={table} rows={rows} onRowClick={onRowClick} />;
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-bg-panel">
      <table className="min-w-full divide-y divide-bg-panel text-sm">
        <thead className="bg-bg-subtle">
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((h) => {
                const canSort = h.column.getCanSort();
                const sorted = h.column.getIsSorted();
                return (
                  <th
                    key={h.id}
                    scope="col"
                    className={cx(
                      "px-3 py-2 text-left font-semibold text-fg-muted",
                      canSort && "cursor-pointer select-none",
                    )}
                    onClick={canSort ? h.column.getToggleSortingHandler() : undefined}
                  >
                    <span className="inline-flex items-center gap-1">
                      {h.isPlaceholder ? null : flexRender(h.column.columnDef.header, h.getContext())}
                      {sorted === "asc" && <span aria-hidden>▲</span>}
                      {sorted === "desc" && <span aria-hidden>▼</span>}
                    </span>
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>
        <tbody className="divide-y divide-bg-panel">
          {rows.map((r) => (
            <tr
              key={r.id}
              onClick={onRowClick ? () => onRowClick(r.original) : undefined}
              className={cx(
                "hover:bg-bg-subtle",
                onRowClick && "cursor-pointer",
                density === "compact" ? "[&>td]:py-1" : "[&>td]:py-2",
              )}
            >
              {r.getVisibleCells().map((c) => (
                <td key={c.id} className="whitespace-nowrap px-3 align-middle">
                  {flexRender(c.column.columnDef.cell, c.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CardList<T>({
  table,
  rows,
  onRowClick,
}: {
  table: Table<T>;
  rows: ReturnType<Table<T>["getRowModel"]>["rows"];
  onRowClick?: (row: T) => void;
}) {
  const cols = table.getAllLeafColumns();
  return (
    <div className="flex flex-col gap-2" data-testid="datatable-cards">
      {rows.map((r) => (
        <button
          key={r.id}
          type="button"
          onClick={onRowClick ? () => onRowClick(r.original) : undefined}
          className={cx(
            "touch-target w-full rounded-lg border border-bg-panel bg-bg-subtle p-3 text-left",
            onRowClick && "hover:bg-bg-panel",
          )}
        >
          <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 text-sm">
            {cols
              .filter((c) => c.getIsVisible())
              .map((c) => {
                const cell = r.getAllCells().find((cc) => cc.column.id === c.id);
                if (!cell) return null;
                return (
                  <div key={c.id} className="contents">
                    <dt className="text-xs uppercase tracking-wide text-fg-subtle">
                      {typeof c.columnDef.header === "string" ? c.columnDef.header : c.id}
                    </dt>
                    <dd className="text-fg">
                      {flexRender(c.columnDef.cell, cell.getContext())}
                    </dd>
                  </div>
                );
              })}
          </dl>
        </button>
      ))}
    </div>
  );
}

function useIsMobile() {
  const [m, setM] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia("(max-width: 639px)");
    const update = () => setM(mq.matches);
    update();
    mq.addEventListener?.("change", update);
    return () => mq.removeEventListener?.("change", update);
  }, []);
  return m;
}

export default DataTable;
