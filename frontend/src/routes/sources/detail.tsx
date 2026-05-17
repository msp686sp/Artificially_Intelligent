import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Card } from "@/components/Card";
import { Badge } from "@/components/Badge";
import { DataTable } from "@/components/DataTable";
import { Progress } from "@/components/Progress";
import { useToast } from "@/components/Toast";
import {
  useSource,
  useSourcePreview,
  useSourceSchema,
} from "@/hooks/useSources";
import { useManifestEntry } from "@/hooks/useManifest";
import { useRefreshJob } from "@/hooks/useRefreshJob";
import {
  formatCount,
  formatTimestamp,
  mergeSourceMeta,
} from "@/lib/source-meta";
import type { SchemaColumn } from "@/api/types";

const PAGE_SIZE = 50;

export default function SourceDetailPage() {
  const { name = "" } = useParams<{ name: string }>();
  const source = useSource(name);
  const schema = useSourceSchema(name);
  const [offset, setOffset] = useState(0);
  const preview = useSourcePreview(name, PAGE_SIZE, offset);
  const manifest = useManifestEntry(name);
  const refreshJob = useRefreshJob();
  const toast = useToast();
  const qc = useQueryClient();
  const [copied, setCopied] = useState(false);

  const meta = mergeSourceMeta(name, {
    license: source.data?.license ?? undefined,
    cadence: source.data?.cadence ?? undefined,
    source_url: source.data?.source_url ?? undefined,
  });

  const cli = `python -m rental.cli refresh ${name}`;
  const copyCli = async () => {
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard) {
        await navigator.clipboard.writeText(cli);
        setCopied(true);
        toast.success("CLI command copied.");
        setTimeout(() => setCopied(false), 1500);
      } else {
        toast.error("Clipboard not available.");
      }
    } catch {
      toast.error("Copy failed.");
    }
  };

  const runRefresh = (fromFixture: boolean) => {
    refreshJob.start(name, {
      fromFixture,
      onComplete: (rows) => {
        toast.success(
          `${name} refreshed${rows ? ` (${rows.toLocaleString()} rows)` : ""}.`,
        );
        qc.invalidateQueries({ queryKey: ["source", name] });
        qc.invalidateQueries({ queryKey: ["source-preview", name] });
        qc.invalidateQueries({ queryKey: ["manifest", name] });
        qc.invalidateQueries({ queryKey: ["manifest"] });
      },
      onError: (msg) => toast.error(`${name} failed: ${msg}`),
    });
  };

  const everRefreshed = Boolean(source.data?.last_refresh);

  return (
    <div className="stack" data-testid="source-detail-root" style={{ gap: "1.5rem" }}>
      <header className="row">
        <Link to="/sources">← Sources</Link>
        <h1 style={{ margin: 0 }}>{meta.display_name}</h1>
        {source.data && (
          <Badge status={source.data.status}>{source.data.status}</Badge>
        )}
        <div className="spacer" />
        <button onClick={() => runRefresh(false)} className="primary">
          Refresh
        </button>
        <button onClick={() => runRefresh(true)}>Refresh from fixture</button>
        <button onClick={copyCli} data-testid="source-detail-cli-copy">
          {copied ? "Copied!" : "Copy CLI command"}
        </button>
      </header>

      {refreshJob.state === "running" && (
        <Card title={`Refreshing ${refreshJob.step ?? "…"}`}>
          <Progress
            value={refreshJob.progress}
            label={
              refreshJob.etaSeconds ? `ETA ${refreshJob.etaSeconds}s` : "in progress"
            }
          />
        </Card>
      )}

      <Card title="Source metadata">
        <dl className="kv-list">
          <dt>ID</dt>
          <dd className="mono">{name}</dd>
          <dt>Description</dt>
          <dd>{meta.description}</dd>
          <dt>Cadence</dt>
          <dd>{meta.cadence}</dd>
          <dt>License</dt>
          <dd>{meta.license}</dd>
          <dt>Source URL</dt>
          <dd>
            {meta.source_url ? (
              <a href={meta.source_url} target="_blank" rel="noreferrer noopener">
                {meta.source_url}
              </a>
            ) : (
              <span className="muted">—</span>
            )}
          </dd>
          <dt>Last refresh</dt>
          <dd>{formatTimestamp(source.data?.last_refresh ?? null)}</dd>
          <dt>Manifest rows</dt>
          <dd>{formatCount(source.data?.rows_loaded ?? null)}</dd>
          <dt>Warehouse rows</dt>
          <dd>{formatCount(source.data?.warehouse_rows ?? null)}</dd>
        </dl>
        {meta.fixture_only_in_ci && (
          <div className="muted" style={{ marginTop: "0.75rem" }}>
            Note: outbound network to this source is blocked in CI; use
            "Refresh from fixture" for offline testing.
          </div>
        )}
      </Card>

      <Card title="Schema">
        {schema.isLoading ? (
          <div className="muted">Loading schema…</div>
        ) : schema.isError ? (
          <div className="empty-state">Could not load schema.</div>
        ) : (schema.data?.columns ?? []).length === 0 ? (
          <div className="empty-state">No columns reported.</div>
        ) : (
          <DataTable<SchemaColumn>
            data-testid="source-detail-schema-table"
            columns={[
              { key: "name", header: "Column", accessor: (r) => r.name, sortable: true },
              { key: "type", header: "Type", accessor: (r) => r.type, sortable: true },
              {
                key: "nullable",
                header: "Nullable",
                accessor: (r) => (r.nullable ? "yes" : "no"),
                sortable: true,
              },
            ]}
            rows={schema.data?.columns ?? []}
            rowKey={(r) => r.name}
          />
        )}
        {schema.data?.row_count !== undefined && schema.data?.row_count !== null && (
          <div className="muted" style={{ marginTop: "0.5rem" }}>
            Row count: {schema.data.row_count.toLocaleString()}
          </div>
        )}
      </Card>

      <Card title="Sample rows">
        {!everRefreshed ? (
          <div className="empty-state">
            No data yet — run a refresh to populate this source.
          </div>
        ) : preview.isLoading ? (
          <div className="muted">Loading rows…</div>
        ) : preview.isError ? (
          <div className="empty-state">Could not load preview rows.</div>
        ) : (preview.data?.rows ?? []).length === 0 ? (
          <div className="empty-state">No rows to display.</div>
        ) : (
          <div>
            <DataTable
              data-testid="source-detail-sample-table"
              columns={(preview.data?.columns ?? []).map((c) => ({
                key: c,
                header: c,
                accessor: (row: Record<string, unknown>) =>
                  row[c] === null || row[c] === undefined ? (
                    <span className="muted">null</span>
                  ) : (
                    String(row[c])
                  ),
              }))}
              rows={preview.data?.rows ?? []}
              rowKey={(_r, idx) => String(offset + idx)}
            />
            <div className="row" style={{ marginTop: "0.75rem" }}>
              <button
                onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
                disabled={offset === 0}
              >
                ← Prev
              </button>
              <span className="muted">
                rows {offset + 1}–
                {offset + (preview.data?.rows.length ?? 0)} of{" "}
                {formatCount(preview.data?.total ?? null)}
              </span>
              <button
                onClick={() => setOffset((o) => o + PAGE_SIZE)}
                disabled={
                  preview.data
                    ? offset + preview.data.rows.length >= preview.data.total
                    : true
                }
              >
                Next →
              </button>
            </div>
          </div>
        )}
      </Card>

      <Card title="Refresh history" data-testid="source-detail-history">
        {manifest.isLoading ? (
          <div className="muted">Loading…</div>
        ) : manifest.isError ? (
          <div className="empty-state">No manifest entry yet.</div>
        ) : manifest.data ? (
          <dl className="kv-list">
            <dt>Status</dt>
            <dd>
              <Badge status={manifest.data.status}>{manifest.data.status}</Badge>
            </dd>
            <dt>Last refresh</dt>
            <dd>{formatTimestamp(manifest.data.last_refresh)}</dd>
            <dt>Rows loaded</dt>
            <dd>{formatCount(manifest.data.rows_loaded)}</dd>
            {manifest.data.age_seconds !== undefined &&
              manifest.data.age_seconds !== null && (
                <>
                  <dt>Age</dt>
                  <dd>{Math.floor(manifest.data.age_seconds / 60)} minutes</dd>
                </>
              )}
            {manifest.data.error && (
              <>
                <dt>Error</dt>
                <dd style={{ color: "var(--danger)" }}>{manifest.data.error}</dd>
              </>
            )}
          </dl>
        ) : (
          <div className="empty-state">No manifest entry yet.</div>
        )}
        <div className="row" style={{ marginTop: "0.75rem" }}>
          <Link to="/logs">View full refresh log →</Link>
        </div>
      </Card>
    </div>
  );
}
