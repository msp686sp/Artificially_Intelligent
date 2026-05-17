import { useState } from "react";
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
  type VisibilityState,
} from "@tanstack/react-table";
import { cn } from "@/lib/cn";

export interface DataTableProps<TData, TValue> {
  data: TData[];
  columns: ColumnDef<TData, TValue>[];
  className?: string;
  emptyMessage?: string;
  initialSorting?: SortingState;
  enableColumnVisibility?: boolean;
  caption?: string;
  onRowClick?: (row: TData) => void;
  rowKey?: (row: TData, index: number) => string;
}

export function DataTable<TData, TValue>({
  data,
  columns,
  className,
  emptyMessage = "No rows",
  initialSorting,
  enableColumnVisibility = true,
  caption,
  onRowClick,
  rowKey,
}: DataTableProps<TData, TValue>) {
  const [sorting, setSorting] = useState<SortingState>(initialSorting ?? []);
  const [visibility, setVisibility] = useState<VisibilityState>({});

  const table = useReactTable({
    data,
    columns,
    state: { sorting, columnVisibility: visibility },
    onSortingChange: setSorting,
    onColumnVisibilityChange: setVisibility,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {enableColumnVisibility && (
        <details className="text-xs">
          <summary className="cursor-pointer text-fg-muted">
            Columns ({table.getVisibleLeafColumns().length}/
            {table.getAllLeafColumns().length})
          </summary>
          <div className="mt-2 flex flex-wrap gap-2 rounded-md border border-bg-subtle bg-bg-subtle p-2">
            {table.getAllLeafColumns().map((col) => (
              <label
                key={col.id}
                className="flex cursor-pointer items-center gap-1"
              >
                <input
                  type="checkbox"
                  checked={col.getIsVisible()}
                  onChange={col.getToggleVisibilityHandler()}
                />
                <span>{col.id}</span>
              </label>
            ))}
          </div>
        </details>
      )}

      <div className="overflow-auto rounded-lg border border-bg-subtle">
        <table className="min-w-full text-sm">
          {caption && (
            <caption className="px-3 py-2 text-left text-xs text-fg-muted">
              {caption}
            </caption>
          )}
          <thead className="bg-bg-subtle">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((header) => {
                  const canSort = header.column.getCanSort();
                  const dir = header.column.getIsSorted();
                  return (
                    <th
                      key={header.id}
                      className={cn(
                        "px-3 py-2 text-left font-medium",
                        canSort && "cursor-pointer select-none",
                      )}
                      onClick={
                        canSort
                          ? header.column.getToggleSortingHandler()
                          : undefined
                      }
                    >
                      <div className="flex items-center gap-1">
                        {flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                        {dir === "asc" && <span aria-hidden>↑</span>}
                        {dir === "desc" && <span aria-hidden>↓</span>}
                      </div>
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.length === 0 ? (
              <tr>
                <td
                  colSpan={table.getVisibleLeafColumns().length}
                  className="px-3 py-6 text-center text-fg-muted"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row, idx) => (
                <tr
                  key={rowKey ? rowKey(row.original, idx) : row.id}
                  className={cn(
                    "border-t border-bg-subtle",
                    onRowClick && "cursor-pointer hover:bg-bg-subtle/60",
                  )}
                  onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-3 py-2">
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
