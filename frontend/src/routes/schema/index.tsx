import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { ColumnDef } from "@tanstack/react-table";
import { useMutation } from "@tanstack/react-query";
import { useSchema } from "@/hooks/useSchema";
import { DataTable } from "@/components/DataTable";
import { Button, Card, Pill, Spinner } from "@/components/ui";
import { apiFetch } from "@/api/client";
import type { SchemaColumn, SchemaTable, SqlResponse } from "@/api/types";
import { cn } from "@/lib/cn";

function tableSqlSkeleton(table: SchemaTable): string {
  const cols = (table.columns ?? []).map((c) => c.name).join(",\n  ");
  return `SELECT\n  ${cols || "*"}\nFROM ${table.name}\nLIMIT 50;`;
}

function tableSchemaSql(table: SchemaTable): string {
  const cols = (table.columns ?? [])
    .map(
      (c) =>
        `  ${c.name} ${c.type}${c.nullable ? "" : " NOT NULL"}`,
    )
    .join(",\n");
  return `-- ${table.kind} ${table.name}\nCREATE TABLE ${table.name} (\n${cols}\n);`;
}

export default function SchemaBrowser() {
  const navigate = useNavigate();
  const schemaQuery = useSchema();
  const [selectedName, setSelectedName] = useState<string | null>(null);

  const grouped = useMemo(() => {
    const tables: SchemaTable[] = [];
    const views: SchemaTable[] = [];
    for (const t of schemaQuery.data ?? []) {
      if (t.kind === "view") views.push(t);
      else tables.push(t);
    }
    const cmp = (a: SchemaTable, b: SchemaTable) =>
      a.name.localeCompare(b.name);
    tables.sort(cmp);
    views.sort(cmp);
    return { tables, views };
  }, [schemaQuery.data]);

  const selected = useMemo(
    () =>
      (schemaQuery.data ?? []).find((t) => t.name === selectedName) ?? null,
    [schemaQuery.data, selectedName],
  );

  const previewMutation = useMutation<SqlResponse, Error, string>({
    mutationFn: (table) =>
      apiFetch<SqlResponse>("/sql", {
        method: "POST",
        body: JSON.stringify({
          query: `SELECT * FROM ${table} LIMIT 50`,
          read_only: true,
        }),
      }),
  });

  const columnColumns = useMemo<ColumnDef<SchemaColumn>[]>(
    () => [
      { id: "name", accessorKey: "name", header: "Name" },
      { id: "type", accessorKey: "type", header: "Type" },
      {
        id: "nullable",
        accessorKey: "nullable",
        header: "Nullable",
        cell: ({ getValue }) => (getValue() ? "YES" : "NO"),
      },
    ],
    [],
  );

  const previewColumns = useMemo<ColumnDef<Record<string, unknown>>[]>(() => {
    if (!previewMutation.data) return [];
    return previewMutation.data.columns.map((col) => ({
      id: col,
      accessorFn: (row: Record<string, unknown>) => row[col],
      header: col,
      cell: ({ getValue }) => {
        const v = getValue();
        if (v === null || v === undefined)
          return <span className="text-fg-subtle">NULL</span>;
        return String(v);
      },
    }));
  }, [previewMutation.data]);

  return (
    <div className="flex flex-col gap-4 p-4 lg:p-6" data-testid="schema-root">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold">Schema browser</h1>
        {schemaQuery.isLoading && <Spinner />}
      </header>

      {/* Mobile dropdown */}
      <div className="lg:hidden">
        <label className="flex flex-col gap-1">
          <span className="text-xs text-fg-muted">Table / view</span>
          <select
            value={selectedName ?? ""}
            onChange={(e) => setSelectedName(e.target.value || null)}
            className="rounded-md border border-bg-subtle bg-bg-subtle px-3 py-2 text-sm"
          >
            <option value="">— pick one —</option>
            <optgroup label="Tables">
              {grouped.tables.map((t) => (
                <option key={t.name} value={t.name}>
                  {t.name}
                </option>
              ))}
            </optgroup>
            <optgroup label="Views">
              {grouped.views.map((t) => (
                <option key={t.name} value={t.name}>
                  {t.name}
                </option>
              ))}
            </optgroup>
          </select>
        </label>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[20rem_1fr]">
        {/* Desktop tree */}
        <aside className="hidden lg:block" data-testid="schema-tree">
          <Card className="max-h-[calc(100vh-10rem)] overflow-auto">
            <nav className="flex flex-col gap-3 text-sm">
              <section>
                <div className="mb-1 font-semibold text-fg-muted">
                  Tables ({grouped.tables.length})
                </div>
                <ul className="flex flex-col gap-0.5">
                  {grouped.tables.map((t) => (
                    <li key={t.name}>
                      <button
                        onClick={() => setSelectedName(t.name)}
                        data-testid={`schema-tree-item-${t.name}`}
                        className={cn(
                          "w-full rounded-md px-2 py-1 text-left",
                          selectedName === t.name
                            ? "bg-accent/30 text-fg"
                            : "hover:bg-bg-subtle",
                        )}
                      >
                        {t.name}
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
              <section>
                <div className="mb-1 font-semibold text-fg-muted">
                  Views ({grouped.views.length})
                </div>
                <ul className="flex flex-col gap-0.5">
                  {grouped.views.map((t) => (
                    <li key={t.name}>
                      <button
                        onClick={() => setSelectedName(t.name)}
                        data-testid={`schema-tree-item-${t.name}`}
                        className={cn(
                          "w-full rounded-md px-2 py-1 text-left",
                          selectedName === t.name
                            ? "bg-accent/30 text-fg"
                            : "hover:bg-bg-subtle",
                        )}
                      >
                        {t.name}
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            </nav>
          </Card>
        </aside>

        <section className="flex flex-col gap-4" data-testid="schema-preview">
          {!selected ? (
            <Card>
              <p className="text-fg-muted">
                Pick a table or view to see its columns and a 50-row preview.
              </p>
            </Card>
          ) : (
            <>
              <Card>
                <header className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h2 className="text-lg font-semibold">{selected.name}</h2>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-fg-muted">
                      <Pill tone="accent">{selected.kind}</Pill>
                      <span>
                        {selected.row_count !== null && selected.row_count !== undefined
                          ? `${selected.row_count.toLocaleString()} rows`
                          : "row count unknown"}
                      </span>
                      <span>{selected.columns.length} columns</span>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      compact
                      variant="ghost"
                      onClick={() => previewMutation.mutate(selected.name)}
                      disabled={previewMutation.isPending}
                    >
                      {previewMutation.isPending ? <Spinner /> : null}
                      Preview 50 rows
                    </Button>
                    <Button
                      compact
                      variant="ghost"
                      data-testid="schema-preview-open-sql-btn"
                      onClick={() =>
                        navigate(
                          `/sql?q=${encodeURIComponent(tableSqlSkeleton(selected))}`,
                        )
                      }
                    >
                      Open in SQL
                    </Button>
                    <Button
                      compact
                      variant="ghost"
                      onClick={() => {
                        void navigator.clipboard?.writeText(
                          tableSchemaSql(selected),
                        );
                      }}
                    >
                      Copy schema as SQL
                    </Button>
                  </div>
                </header>
                <div className="mt-3">
                  <DataTable
                    data={selected.columns}
                    columns={columnColumns}
                    enableColumnVisibility={false}
                  />
                </div>
              </Card>

              {previewMutation.error && (
                <Card className="border-danger bg-danger/10 text-danger">
                  <strong>Preview failed:</strong>{" "}
                  {previewMutation.error.message}
                </Card>
              )}

              {previewMutation.data && (
                <Card>
                  <h3 className="mb-2 font-semibold">
                    Preview ({previewMutation.data.row_count} rows in{" "}
                    {previewMutation.data.elapsed_ms.toFixed(1)} ms)
                  </h3>
                  <DataTable
                    data={previewMutation.data.rows}
                    columns={previewColumns}
                  />
                </Card>
              )}
            </>
          )}
        </section>
      </div>

      {schemaQuery.error && (
        <Card className="border-danger bg-danger/10 text-danger">
          <strong>Schema load failed:</strong>{" "}
          {(schemaQuery.error as Error).message}
        </Card>
      )}
    </div>
  );
}
