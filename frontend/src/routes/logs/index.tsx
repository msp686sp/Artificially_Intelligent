import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Card } from "@/components/Card";
import { Badge } from "@/components/Badge";
import { DataTable } from "@/components/DataTable";
import { useLogs } from "@/hooks/useLogs";
import type { LogsFilter } from "@/hooks/useLogs";
import { useSources } from "@/hooks/useSources";
import { formatTimestamp, formatCount } from "@/lib/source-meta";
import type { RefreshLogRow, SourceStatus } from "@/api/types";

const STATUS_OPTIONS: Array<{ value: "" | SourceStatus; label: string }> = [
  { value: "", label: "Any status" },
  { value: "ok", label: "ok" },
  { value: "stale", label: "stale" },
  { value: "error", label: "error" },
  { value: "never", label: "never" },
];

export default function LogsPage() {
  const [filter, setFilter] = useState<LogsFilter>({});
  const sources = useSources();
  const logs = useLogs(filter);

  // Client-side filter fallback when API ignores some query params.
  const filtered = useMemo(() => {
    const rows = logs.data ?? [];
    return rows.filter((r) => {
      if (filter.source && r.source !== filter.source) return false;
      if (filter.status && r.status !== filter.status) return false;
      if (filter.start) {
        const t = new Date(r.started_at).getTime();
        const start = new Date(filter.start).getTime();
        if (Number.isFinite(start) && t < start) return false;
      }
      if (filter.end) {
        const t = new Date(r.started_at).getTime();
        const end = new Date(filter.end).getTime();
        if (Number.isFinite(end) && t > end) return false;
      }
      return true;
    });
  }, [logs.data, filter]);

  const update = <K extends keyof LogsFilter>(k: K, v: LogsFilter[K] | "") => {
    setFilter((cur) => ({ ...cur, [k]: v === "" ? undefined : v }));
  };

  return (
    <div className="stack" style={{ gap: "1.5rem" }} data-testid="logs-root">
      <header className="row">
        <h1 style={{ margin: 0 }}>Refresh log</h1>
        <div className="spacer" />
        <button onClick={() => logs.refetch()}>Reload</button>
      </header>

      <Card>
        <div className="toolbar">
          <label>
            <span className="muted">Source&nbsp;</span>
            <select
              value={filter.source ?? ""}
              onChange={(e) => update("source", e.target.value)}
              aria-label="Filter by source"
            >
              <option value="">All sources</option>
              {(sources.data ?? []).map((s) => (
                <option key={s.name} value={s.name}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="muted">Status&nbsp;</span>
            <select
              value={filter.status ?? ""}
              onChange={(e) =>
                update("status", e.target.value as "" | SourceStatus)
              }
              aria-label="Filter by status"
            >
              {STATUS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="muted">From&nbsp;</span>
            <input
              type="date"
              value={filter.start ?? ""}
              onChange={(e) => update("start", e.target.value)}
              aria-label="Start date"
            />
          </label>
          <label>
            <span className="muted">To&nbsp;</span>
            <input
              type="date"
              value={filter.end ?? ""}
              onChange={(e) => update("end", e.target.value)}
              aria-label="End date"
            />
          </label>
          <button onClick={() => setFilter({})}>Clear</button>
          <div className="spacer" />
          <span className="muted">
            {filtered.length} / {(logs.data ?? []).length} entries
          </span>
        </div>

        {logs.isLoading ? (
          <div className="muted">Loading refresh log…</div>
        ) : logs.isError ? (
          <div className="empty-state">Could not load refresh log.</div>
        ) : (
          <DataTable<RefreshLogRow>
            data-testid="logs-table"
            columns={[
              {
                key: "id",
                header: "ID",
                accessor: (r) => r.id,
                sortValue: (r) => r.id,
                sortable: true,
              },
              {
                key: "source",
                header: "Source",
                accessor: (r) => <Link to={`/sources/${r.source}`}>{r.source}</Link>,
                sortValue: (r) => r.source,
                sortable: true,
              },
              {
                key: "started_at",
                header: "Started",
                accessor: (r) => formatTimestamp(r.started_at),
                sortValue: (r) => r.started_at,
                sortable: true,
              },
              {
                key: "finished_at",
                header: "Finished",
                accessor: (r) => formatTimestamp(r.finished_at),
                sortValue: (r) => r.finished_at ?? "",
                sortable: true,
              },
              {
                key: "status",
                header: "Status",
                accessor: (r) => <Badge status={r.status}>{r.status}</Badge>,
                sortValue: (r) => r.status,
                sortable: true,
              },
              {
                key: "rows_loaded",
                header: "Rows",
                accessor: (r) => formatCount(r.rows_loaded),
                sortValue: (r) => r.rows_loaded ?? 0,
                sortable: true,
              },
              {
                key: "error",
                header: "Error",
                accessor: (r) =>
                  r.error ? (
                    <span style={{ color: "var(--danger)" }}>{r.error}</span>
                  ) : (
                    <span className="muted">—</span>
                  ),
              },
            ]}
            rows={filtered}
            rowKey={(r) => String(r.id)}
            emptyMessage="No refresh log entries match the current filter."
          />
        )}
      </Card>
    </div>
  );
}
