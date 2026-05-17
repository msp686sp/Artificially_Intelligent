import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Card } from "@/components/Card";
import { Badge } from "@/components/Badge";
import { DataTable } from "@/components/DataTable";
import { useManifest } from "@/hooks/useManifest";
import { formatAge, formatTimestamp, formatCount } from "@/lib/source-meta";
import type { ManifestEntry, SourceStatus } from "@/api/types";

const STATUS_OPTIONS: Array<{ value: "" | SourceStatus; label: string }> = [
  { value: "", label: "All statuses" },
  { value: "ok", label: "ok" },
  { value: "stale", label: "stale" },
  { value: "error", label: "error" },
  { value: "never", label: "never" },
];

export default function ManifestPage() {
  const manifest = useManifest();
  const [statusFilter, setStatusFilter] = useState<"" | SourceStatus>("");
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    const rows = manifest.data ?? [];
    return rows.filter((r) => {
      if (statusFilter && r.status !== statusFilter) return false;
      if (search && !r.source.toLowerCase().includes(search.toLowerCase()))
        return false;
      return true;
    });
  }, [manifest.data, statusFilter, search]);

  return (
    <div className="stack" style={{ gap: "1.5rem" }}>
      <header className="row">
        <h1 style={{ margin: 0 }}>Manifest</h1>
        <div className="spacer" />
        <button onClick={() => manifest.refetch()}>Reload</button>
      </header>

      <Card>
        <div className="toolbar">
          <label>
            <span className="muted">Search&nbsp;</span>
            <input
              type="text"
              placeholder="source name"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search source name"
            />
          </label>
          <label>
            <span className="muted">Status&nbsp;</span>
            <select
              value={statusFilter}
              onChange={(e) =>
                setStatusFilter(e.target.value as "" | SourceStatus)
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
          <div className="spacer" />
          <span className="muted">
            {filtered.length} / {(manifest.data ?? []).length} entries
          </span>
        </div>

        {manifest.isLoading ? (
          <div className="muted">Loading manifest…</div>
        ) : manifest.isError ? (
          <div className="empty-state">Could not load manifest.</div>
        ) : (
          <DataTable<ManifestEntry>
            columns={[
              {
                key: "source",
                header: "Source",
                accessor: (r) => <Link to={`/sources/${r.source}`}>{r.source}</Link>,
                sortValue: (r) => r.source,
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
                key: "last_refresh",
                header: "Last refresh",
                accessor: (r) => formatTimestamp(r.last_refresh),
                sortValue: (r) => r.last_refresh ?? "",
                sortable: true,
              },
              {
                key: "age",
                header: "Age",
                accessor: (r) => formatAge(r.age_seconds),
                sortValue: (r) =>
                  r.age_seconds === null || r.age_seconds === undefined
                    ? Number.POSITIVE_INFINITY
                    : r.age_seconds,
                sortable: true,
              },
              {
                key: "rows_loaded",
                header: "Rows",
                accessor: (r) => formatCount(r.rows_loaded),
                sortValue: (r) => r.rows_loaded,
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
            rowKey={(r) => r.source}
            emptyMessage="No manifest entries match the current filter."
          />
        )}
      </Card>
    </div>
  );
}
