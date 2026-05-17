import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type { ColumnDef } from "@tanstack/react-table";
import SqlEditor from "@/components/SqlEditor";
import { DataTable } from "@/components/DataTable";
import { Button, Card, Dialog, Pill, Spinner } from "@/components/ui";
import { useSql } from "@/hooks/useSql";
import { useSchema } from "@/hooks/useSchema";
import { useSavedQueries, useSqlHistory } from "@/hooks/useSqlHistory";
import { downloadCsv, rowsToCsv } from "@/lib/csv";
import { cn } from "@/lib/cn";

const DEFAULT_QUERY = "SELECT 1 AS hello;";

const TEMPLATES: Array<{ name: string; query: string }> = [
  {
    name: "Top 20 zips by market score",
    query:
      "SELECT zcta5, state, metro, market_score\nFROM zip_scores\nORDER BY market_score DESC\nLIMIT 20;",
  },
  {
    name: "Latest ZHVI per zip",
    query:
      "SELECT zcta5, MAX(period) AS latest_period, MAX_BY(zhvi, period) AS latest_zhvi\nFROM raw_zillow_zhvi\nGROUP BY zcta5\nORDER BY latest_zhvi DESC NULLS LAST\nLIMIT 50;",
  },
  {
    name: "ZORI year-over-year change",
    query:
      "WITH ranked AS (\n  SELECT zcta5, period, zori,\n    ROW_NUMBER() OVER (PARTITION BY zcta5 ORDER BY period DESC) AS rn\n  FROM raw_zillow_zori\n)\nSELECT cur.zcta5,\n       cur.zori AS zori_now,\n       prev.zori AS zori_year_ago,\n       (cur.zori - prev.zori) / NULLIF(prev.zori, 0) AS yoy_change\nFROM ranked cur\nJOIN ranked prev USING (zcta5)\nWHERE cur.rn = 1 AND prev.rn = 13\nORDER BY yoy_change DESC NULLS LAST\nLIMIT 50;",
  },
  {
    name: "Manifest health (stale sources)",
    query:
      "SELECT source, status, last_refresh, rows_loaded\nFROM manifest\nWHERE status IN ('stale', 'error')\nORDER BY last_refresh;",
  },
];

function ExplainTree({ rows }: { rows: Array<Record<string, unknown>> }) {
  const text = useMemo(
    () =>
      rows
        .map((r) => {
          if (typeof r === "string") return r;
          // DuckDB returns EXPLAIN as a one-column "explain_value" or similar.
          const first = Object.values(r)[0];
          return typeof first === "string" ? first : JSON.stringify(r);
        })
        .join("\n"),
    [rows],
  );
  return (
    <pre className="max-h-96 overflow-auto rounded-lg border border-bg-subtle bg-bg-subtle p-3 font-mono text-xs">
      {text}
    </pre>
  );
}

export default function SqlWorkbench() {
  const navigate = useNavigate();
  const location = useLocation();
  const schemaQuery = useSchema();
  const sqlMutation = useSql();

  const [query, setQuery] = useState<string>(() => {
    const params = new URLSearchParams(location.search);
    return params.get("q") || DEFAULT_QUERY;
  });
  const [readOnly, setReadOnly] = useState(true);
  const [readOnlyWarn, setReadOnlyWarn] = useState(false);
  const [explainRows, setExplainRows] = useState<Array<Record<string, unknown>> | null>(
    null,
  );
  const [templatesOpen, setTemplatesOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState("");

  const { history, push: pushHistory, clear: clearHistory } = useSqlHistory();
  const { saved, save: saveQuery, remove: removeSaved } = useSavedQueries();

  // Sync ?q= so deep-link "Open in SQL" from the schema browser works.
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const q = params.get("q");
    if (q && q !== query) setQuery(q);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.search]);

  const runQuery = useCallback(
    async (overrideQuery?: string) => {
      const q = (overrideQuery ?? query).trim();
      if (!q) return;
      setExplainRows(null);
      try {
        const result = await sqlMutation.mutateAsync({
          query: q,
          read_only: readOnly,
        });
        pushHistory({
          query: q,
          ranAt: new Date().toISOString(),
          rowCount: result.row_count,
          elapsedMs: result.elapsed_ms,
          ok: true,
        });
      } catch (e) {
        pushHistory({
          query: q,
          ranAt: new Date().toISOString(),
          ok: false,
        });
        // mutation.error surfaces in render
        void e;
      }
    },
    [query, readOnly, sqlMutation, pushHistory],
  );

  const runExplain = useCallback(async () => {
    const q = query.trim();
    if (!q) return;
    try {
      const result = await sqlMutation.mutateAsync({
        query: `EXPLAIN ${q.replace(/;\s*$/, "")}`,
        read_only: true,
      });
      setExplainRows(result.rows);
    } catch {
      // surfaced via mutation.error
    }
  }, [query, sqlMutation]);

  const onExport = useCallback(() => {
    if (!sqlMutation.data) return;
    const csv = rowsToCsv(sqlMutation.data.columns, sqlMutation.data.rows);
    downloadCsv(`query-${Date.now()}.csv`, csv);
  }, [sqlMutation.data]);

  const onToggleReadOnly = useCallback(() => {
    if (readOnly) {
      // Turning protection OFF — warn first.
      setReadOnlyWarn(true);
    } else {
      setReadOnly(true);
    }
  }, [readOnly]);

  const columns = useMemo<ColumnDef<Record<string, unknown>>[]>(() => {
    if (!sqlMutation.data) return [];
    return sqlMutation.data.columns.map((col) => ({
      id: col,
      accessorFn: (row: Record<string, unknown>) => row[col],
      header: col,
      cell: ({ getValue }) => {
        const v = getValue();
        if (v === null || v === undefined)
          return <span className="text-fg-subtle">NULL</span>;
        if (typeof v === "object") return <code>{JSON.stringify(v)}</code>;
        return String(v);
      },
    }));
  }, [sqlMutation.data]);

  const errorMessage =
    sqlMutation.error instanceof Error
      ? sqlMutation.error.message
      : sqlMutation.error
        ? String(sqlMutation.error)
        : null;

  return (
    <div className="flex flex-col gap-4 p-4 lg:p-6" data-testid="sql-root">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold">SQL workbench</h1>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={onToggleReadOnly}
            data-testid="sql-readonly-toggle"
            className={cn(
              "inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium",
              readOnly
                ? "bg-success/20 text-success"
                : "bg-danger/20 text-danger",
            )}
            aria-pressed={!readOnly}
            title="Toggle read-only protection"
          >
            <span
              className={cn(
                "h-2 w-2 rounded-full",
                readOnly ? "bg-success" : "bg-danger",
              )}
            />
            {readOnly ? "Read-only ON" : "Read-only OFF"}
          </button>
          <Button
            variant="ghost"
            compact
            onClick={() => setTemplatesOpen(true)}
            aria-label="Templates"
          >
            <span className="lg:hidden" aria-hidden>
              T
            </span>
            <span className="hidden lg:inline">Templates</span>
          </Button>
          <Button
            variant="ghost"
            compact
            onClick={() => setHistoryOpen(true)}
            aria-label="History"
          >
            <span className="lg:hidden" aria-hidden>
              H
            </span>
            <span className="hidden lg:inline">History</span>
          </Button>
          <Button
            variant="ghost"
            compact
            onClick={() => setSaveOpen(true)}
            aria-label="Save"
          >
            <span className="lg:hidden" aria-hidden>
              S
            </span>
            <span className="hidden lg:inline">Save</span>
          </Button>
          <Button
            variant="primary"
            onClick={() => runQuery()}
            disabled={sqlMutation.isPending}
            aria-label="Run (Cmd/Ctrl+Enter)"
            data-testid="sql-run-btn"
          >
            {sqlMutation.isPending ? <Spinner /> : null}
            <span>Run</span>
          </Button>
        </div>
      </header>

      <SqlEditor
        value={query}
        onChange={setQuery}
        schema={schemaQuery.data}
        onRun={() => runQuery()}
        placeholder="Cmd/Ctrl+Enter to run"
      />

      <div className="flex flex-wrap items-center gap-3 text-xs text-fg-muted">
        {sqlMutation.data && (
          <>
            <span data-testid="sql-row-count">
              <Pill tone="accent">{sqlMutation.data.row_count} rows</Pill>
            </span>
            <span data-testid="sql-elapsed">
              {sqlMutation.data.elapsed_ms.toFixed(1)} ms
            </span>
            <button
              onClick={runExplain}
              className="underline-offset-2 hover:underline"
            >
              EXPLAIN
            </button>
            <button
              onClick={onExport}
              data-testid="sql-export-csv-btn"
              className="underline-offset-2 hover:underline"
            >
              Export CSV
            </button>
          </>
        )}
        {schemaQuery.isLoading && <Spinner />}
      </div>

      {errorMessage && (
        <Card className="border-danger bg-danger/10 text-danger">
          <strong>Error:</strong> {errorMessage}
        </Card>
      )}

      {explainRows && (
        <Card>
          <header className="mb-2 flex items-center justify-between">
            <h2 className="font-semibold">EXPLAIN</h2>
            <Button variant="ghost" compact onClick={() => setExplainRows(null)}>
              Close
            </Button>
          </header>
          <ExplainTree rows={explainRows} />
        </Card>
      )}

      {sqlMutation.data && !explainRows && (
        <div data-testid="sql-results-table">
          <Card className="overflow-hidden">
            <DataTable
              data={sqlMutation.data.rows}
              columns={columns}
              emptyMessage="Query returned no rows"
            />
          </Card>
        </div>
      )}

      {/* Read-only OFF warning */}
      <Dialog
        open={readOnlyWarn}
        onClose={() => setReadOnlyWarn(false)}
        title="Disable read-only protection?"
        footer={
          <>
            <Button variant="ghost" onClick={() => setReadOnlyWarn(false)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                setReadOnly(false);
                setReadOnlyWarn(false);
              }}
            >
              Disable
            </Button>
          </>
        }
      >
        <p>
          With read-only OFF, statements like <code>INSERT</code>,{" "}
          <code>UPDATE</code>, <code>DELETE</code>, <code>CREATE</code>, and{" "}
          <code>DROP</code> will be sent to DuckDB and may mutate the warehouse.
        </p>
      </Dialog>

      {/* Templates */}
      <Dialog
        open={templatesOpen}
        onClose={() => setTemplatesOpen(false)}
        title="Query templates"
        className="max-w-2xl"
      >
        <ul className="flex flex-col gap-3">
          {TEMPLATES.map((t) => (
            <li key={t.name} className="rounded-md border border-bg-subtle p-3">
              <div className="flex items-center justify-between gap-2">
                <strong>{t.name}</strong>
                <div className="flex gap-2">
                  <Button
                    compact
                    variant="ghost"
                    onClick={() => {
                      void navigator.clipboard?.writeText(t.query);
                    }}
                  >
                    Copy
                  </Button>
                  <Button
                    compact
                    variant="primary"
                    onClick={() => {
                      setQuery(t.query);
                      setTemplatesOpen(false);
                    }}
                  >
                    Use
                  </Button>
                </div>
              </div>
              <pre className="mt-2 max-h-32 overflow-auto rounded bg-bg-subtle p-2 text-xs">
                {t.query}
              </pre>
            </li>
          ))}
        </ul>
      </Dialog>

      {/* History */}
      <Dialog
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        title="Recent queries"
        className="max-w-2xl"
        footer={
          <>
            <Button variant="ghost" onClick={clearHistory}>
              Clear
            </Button>
            <Button variant="secondary" onClick={() => setHistoryOpen(false)}>
              Close
            </Button>
          </>
        }
      >
        <div data-testid="sql-history">
        {history.length === 0 ? (
          <p className="text-fg-muted">No history yet.</p>
        ) : (
          <ul className="flex max-h-96 flex-col gap-2 overflow-auto">
            {history.map((h, i) => (
              <li
                key={`${h.ranAt}-${i}`}
                className="rounded-md border border-bg-subtle p-2"
              >
                <div className="flex items-center justify-between text-xs text-fg-muted">
                  <span>{new Date(h.ranAt).toLocaleString()}</span>
                  <span>
                    {h.ok ? (
                      <Pill tone="success">
                        {h.rowCount ?? 0} rows · {h.elapsedMs?.toFixed(0) ?? "?"}{" "}
                        ms
                      </Pill>
                    ) : (
                      <Pill tone="danger">failed</Pill>
                    )}
                  </span>
                </div>
                <pre className="mt-1 max-h-24 overflow-auto whitespace-pre-wrap break-words font-mono text-xs">
                  {h.query}
                </pre>
                <div className="mt-1 flex justify-end gap-2">
                  <Button
                    compact
                    variant="ghost"
                    onClick={() => {
                      setQuery(h.query);
                      setHistoryOpen(false);
                    }}
                  >
                    Load
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
        </div>
      </Dialog>

      {/* Save */}
      <Dialog
        open={saveOpen}
        onClose={() => setSaveOpen(false)}
        title="Save query"
        footer={
          <>
            <Button variant="ghost" onClick={() => setSaveOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={() => {
                saveQuery(saveName, query);
                setSaveName("");
                setSaveOpen(false);
              }}
              disabled={!saveName.trim()}
            >
              Save
            </Button>
          </>
        }
      >
        <label className="flex flex-col gap-1">
          <span className="text-xs text-fg-muted">Name</span>
          <input
            type="text"
            value={saveName}
            onChange={(e) => setSaveName(e.target.value)}
            className="rounded-md border border-bg-subtle bg-bg-subtle px-3 py-2 text-sm focus:border-accent focus:outline-none"
            placeholder="e.g. top-zips-by-score"
          />
        </label>
        {saved.length > 0 && (
          <div className="mt-4 flex flex-col gap-2">
            <div className="text-xs text-fg-muted">Saved</div>
            <ul className="flex max-h-64 flex-col gap-1 overflow-auto">
              {saved.map((s) => (
                <li
                  key={s.name}
                  className="flex items-center justify-between rounded-md border border-bg-subtle p-2 text-sm"
                >
                  <button
                    className="truncate text-left"
                    onClick={() => {
                      setQuery(s.query);
                      setSaveOpen(false);
                    }}
                  >
                    {s.name}
                  </button>
                  <Button
                    compact
                    variant="ghost"
                    onClick={() => removeSaved(s.name)}
                  >
                    Delete
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Dialog>

      <div className="text-xs text-fg-subtle">
        <button
          onClick={() => navigate("/schema")}
          className="underline-offset-2 hover:underline"
        >
          Schema browser
        </button>
      </div>
    </div>
  );
}
