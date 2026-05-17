import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
  type VisibilityState,
} from "@tanstack/react-table";
import { useMemo, useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { downloadCsv, toCsv } from "@/lib/csv";
import { useIsMobile } from "@/hooks/useMediaQuery";
import { useColumnVisibility } from "@/hooks/useColumnVisibility";
import { Button } from "./Button";

export type Density = "comfortable" | "compact";

export interface DataTableProps<TData> {
  /** Unique key for persisting column visibility. */
  tableKey: string;
  data: TData[];
  // ColumnDef's second generic is the cell value type; we accept any
  // value here so callers can type their own columns. Using `unknown`
  // collides with TanStack's inferred accessor signature.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  columns: ColumnDef<TData, any>[];
  /** Show toolbar with search/density/columns/export. Default true. */
  toolbar?: boolean;
  /** Optional title displayed at the left of the toolbar. */
  title?: ReactNode;
  /** Page size when client-side pagination is enabled. 0 = no pagination. */
  pageSize?: number;
  /** Initial sort state. */
  initialSort?: SortingState;
  /** CSV filename without extension. */
  exportName?: string;
  /** Allow callers to force the layout (e.g. tests). Defaults to auto. */
  layout?: "table" | "cards" | "auto";
  emptyMessage?: ReactNode;
  className?: string;
  "data-testid"?: string;
}

/**
 * DataTable — TanStack Table wrapper with our toolbar (search,
 * density, column visibility, CSV export). On mobile (< sm) the
 * default layout swaps to **stacked cards** so the data is still
 * readable on a phone (plan §6 responsive rules).
 */
export function DataTable<TData>({
  tableKey,
  data,
  columns,
  toolbar = true,
  title,
  pageSize = 50,
  initialSort,
  exportName,
  layout = "auto",
  emptyMessage = "No rows to display.",
  className,
  ...rest
}: DataTableProps<TData>) {
  const isMobile = useIsMobile();
  const resolvedLayout = layout === "auto" ? (isMobile ? "cards" : "table") : layout;

  const [sorting, setSorting] = useState<SortingState>(initialSort ?? []);
  const [globalFilter, setGlobalFilter] = useState("");
  const [density, setDensity] = useState<Density>("comfortable");
  const defaultVisibility = useMemo(() => {
    const out: Record<string, boolean> = {};
    for (const col of columns) {
      const id = (col as { id?: string; accessorKey?: string }).id ?? (col as { accessorKey?: string }).accessorKey;
      if (id) out[String(id)] = true;
    }
    return out;
  }, [columns]);
  const [columnVisibility, setColumnVisibility] = useColumnVisibility(tableKey, defaultVisibility);

  const table = useReactTable<TData>({
    data,
    columns,
    state: {
      sorting,
      globalFilter,
      columnVisibility: columnVisibility as VisibilityState,
    },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    onColumnVisibilityChange: (updater) => {
      const next =
        typeof updater === "function" ? updater(columnVisibility as VisibilityState) : updater;
      setColumnVisibility(next as Record<string, boolean>);
    },
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: pageSize > 0 ? getPaginationRowModel() : undefined,
    initialState: pageSize > 0 ? { pagination: { pageSize, pageIndex: 0 } } : undefined,
  });

  const rows = table.getRowModel().rows;

  const onExport = () => {
    const visibleCols = table.getVisibleLeafColumns().filter((c) => c.id !== "__select");
    const headers = visibleCols.map((c) => c.id);
    const exported = rows.map((row) => {
      const out: Record<string, string | number | boolean | null> = {};
      for (const col of visibleCols) {
        const cell = row.getValue(col.id);
        out[col.id] =
          cell === null || cell === undefined
            ? null
            : typeof cell === "number" || typeof cell === "boolean"
              ? cell
              : String(cell);
      }
      return out;
    });
    downloadCsv(exportName ?? tableKey, toCsv(exported, headers));
  };

  const padding = density === "compact" ? "px-2 py-1.5 text-xs" : "px-3 py-2.5 text-sm";

  return (
    <div
      className={cn("flex flex-col gap-3", className)}
      data-testid={rest["data-testid"] ?? "data-table"}
      data-layout={resolvedLayout}
    >
      {toolbar && (
        <DataTableToolbar
          title={title}
          globalFilter={globalFilter}
          setGlobalFilter={setGlobalFilter}
          density={density}
          setDensity={setDensity}
          onExport={onExport}
          rowCount={rows.length}
          totalRows={data.length}
          table={table}
        />
      )}

      {resolvedLayout === "cards" ? (
        <DataTableCards rows={rows} emptyMessage={emptyMessage} />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border-subtle bg-bg-panel">
          <table className="min-w-full text-left text-fg">
            <thead className="border-b border-border-subtle bg-bg-subtle text-xs uppercase tracking-wide text-fg-muted">
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id}>
                  {hg.headers.map((header) => {
                    const canSort = header.column.getCanSort();
                    const sortDir = header.column.getIsSorted();
                    return (
                      <th
                        key={header.id}
                        scope="col"
                        className={cn(padding, "whitespace-nowrap font-medium")}
                      >
                        {header.isPlaceholder ? null : (
                          <button
                            type="button"
                            onClick={canSort ? header.column.getToggleSortingHandler() : undefined}
                            className={cn(
                              "inline-flex items-center gap-1",
                              canSort && "hover:text-fg",
                              !canSort && "cursor-default",
                            )}
                          >
                            {flexRender(header.column.columnDef.header, header.getContext())}
                            {canSort && (
                              <span aria-hidden className="text-fg-subtle">
                                {sortDir === "asc" ? "▲" : sortDir === "desc" ? "▼" : "↕"}
                              </span>
                            )}
                          </button>
                        )}
                      </th>
                    );
                  })}
                </tr>
              ))}
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td
                    colSpan={table.getAllLeafColumns().length}
                    className="px-3 py-10 text-center text-sm text-fg-muted"
                  >
                    {emptyMessage}
                  </td>
                </tr>
              ) : (
                rows.map((row) => (
                  <tr
                    key={row.id}
                    className="border-b border-border-subtle last:border-b-0 hover:bg-bg-subtle/50"
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className={cn(padding, "tabular-nums")}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {pageSize > 0 && rows.length > 0 && resolvedLayout === "table" && (
        <DataTablePagination table={table} />
      )}
    </div>
  );
}

interface ToolbarProps<TData> {
  title?: ReactNode;
  globalFilter: string;
  setGlobalFilter: (v: string) => void;
  density: Density;
  setDensity: (v: Density) => void;
  onExport: () => void;
  rowCount: number;
  totalRows: number;
  table: ReturnType<typeof useReactTable<TData>>;
}

function DataTableToolbar<TData>({
  title,
  globalFilter,
  setGlobalFilter,
  density,
  setDensity,
  onExport,
  rowCount,
  totalRows,
  table,
}: ToolbarProps<TData>) {
  const [showCols, setShowCols] = useState(false);
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
      <div className="flex min-w-0 items-center gap-3">
        {title && <div className="text-sm font-medium text-fg">{title}</div>}
        <div className="text-xs text-fg-muted">
          {rowCount === totalRows ? `${totalRows} rows` : `${rowCount} of ${totalRows} rows`}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="search"
          value={globalFilter}
          onChange={(e) => setGlobalFilter(e.target.value)}
          placeholder="Filter…"
          aria-label="Filter rows"
          className="h-9 min-h-touch w-full rounded-md border border-border bg-bg-subtle px-3 text-sm text-fg placeholder:text-fg-subtle focus:outline-none focus:ring-2 focus:ring-accent sm:w-48"
        />
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setDensity(density === "comfortable" ? "compact" : "comfortable")}
          aria-pressed={density === "compact"}
        >
          {density === "comfortable" ? "Compact" : "Comfortable"}
        </Button>
        <div className="relative">
          <Button variant="secondary" size="sm" onClick={() => setShowCols((s) => !s)}>
            Columns
          </Button>
          {showCols && (
            <div className="absolute right-0 z-20 mt-1 w-56 rounded-md border border-border bg-bg-panel p-2 text-sm shadow-lg">
              {table.getAllLeafColumns().map((col) => (
                <label
                  key={col.id}
                  className="flex min-h-touch cursor-pointer items-center gap-2 rounded px-2 py-1 hover:bg-bg-subtle"
                >
                  <input
                    type="checkbox"
                    checked={col.getIsVisible()}
                    onChange={col.getToggleVisibilityHandler()}
                    className="h-4 w-4 accent-accent"
                  />
                  <span className="truncate text-fg">{col.id}</span>
                </label>
              ))}
            </div>
          )}
        </div>
        <Button variant="secondary" size="sm" onClick={onExport}>
          Export CSV
        </Button>
      </div>
    </div>
  );
}

function DataTablePagination<TData>({ table }: { table: ReturnType<typeof useReactTable<TData>> }) {
  const { pageIndex, pageSize } = table.getState().pagination;
  const total = table.getFilteredRowModel().rows.length;
  const start = total === 0 ? 0 : pageIndex * pageSize + 1;
  const end = Math.min(total, (pageIndex + 1) * pageSize);
  return (
    <div className="flex items-center justify-between text-xs text-fg-muted">
      <span>
        {start}–{end} of {total}
      </span>
      <div className="flex items-center gap-1">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => table.previousPage()}
          disabled={!table.getCanPreviousPage()}
        >
          Prev
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => table.nextPage()}
          disabled={!table.getCanNextPage()}
        >
          Next
        </Button>
      </div>
    </div>
  );
}

function DataTableCards<TData>({
  rows,
  emptyMessage,
}: {
  rows: ReturnType<ReturnType<typeof useReactTable<TData>>["getRowModel"]>["rows"];
  emptyMessage: ReactNode;
}) {
  if (rows.length === 0) {
    return (
      <div className="rounded-lg border border-border-subtle bg-bg-panel p-6 text-center text-sm text-fg-muted">
        {emptyMessage}
      </div>
    );
  }
  return (
    <div className="grid gap-2" data-testid="data-table-cards">
      {rows.map((row) => (
        <div
          key={row.id}
          className="rounded-lg border border-border-subtle bg-bg-panel p-3 text-sm"
        >
          <dl className="grid grid-cols-1 gap-1.5">
            {row.getVisibleCells().map((cell) => {
              const header = cell.column.columnDef.header;
              const label =
                typeof header === "string"
                  ? header
                  : (cell.column.id ?? "");
              return (
                <div
                  key={cell.id}
                  className="flex items-baseline justify-between gap-3 border-b border-border-subtle/50 last:border-b-0 pb-1.5 last:pb-0"
                >
                  <dt className="text-xs uppercase tracking-wide text-fg-muted">{label}</dt>
                  <dd className="text-right font-mono text-sm tabular-nums text-fg">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </dd>
                </div>
              );
            })}
          </dl>
        </div>
      ))}
    </div>
  );
}
