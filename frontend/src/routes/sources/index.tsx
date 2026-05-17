import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { apiPost } from "@/api/client";
import { Card } from "@/components/Card";
import { Badge } from "@/components/Badge";
import { Dialog } from "@/components/Dialog";
import { Progress } from "@/components/Progress";
import { useToast } from "@/components/Toast";
import { useSources } from "@/hooks/useSources";
import { useRefreshJob } from "@/hooks/useRefreshJob";
import {
  formatCount,
  formatTimestamp,
  mergeSourceMeta,
} from "@/lib/source-meta";
import type { SourceSummary } from "@/api/types";

interface ConfirmReset {
  source: string;
}

function selectQuery(sourceName: string): string {
  // Heuristic: warehouse tables are typically named raw_{source} or
  // {source}. We default to raw_{source}.
  const table = sourceName.startsWith("raw_") ? sourceName : `raw_${sourceName}`;
  return `SELECT * FROM ${table} LIMIT 50`;
}

export default function SourcesPage() {
  const sources = useSources();
  const refreshJob = useRefreshJob();
  const toast = useToast();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [activeRefresh, setActiveRefresh] = useState<string | null>(null);
  const [confirmReset, setConfirmReset] = useState<ConfirmReset | null>(null);

  const startRefresh = (source: SourceSummary, fromFixture: boolean) => {
    setActiveRefresh(source.name);
    refreshJob.start(source.name, {
      fromFixture,
      onComplete: (rows) => {
        toast.success(
          `${source.name} refreshed${rows ? ` (${rows.toLocaleString()} rows)` : ""}.`,
        );
        qc.invalidateQueries({ queryKey: ["sources"] });
        qc.invalidateQueries({ queryKey: ["manifest"] });
        qc.invalidateQueries({ queryKey: ["source", source.name] });
        setActiveRefresh(null);
      },
      onError: (msg) => {
        toast.error(`${source.name} failed: ${msg}`);
        setActiveRefresh(null);
      },
    });
  };

  const resetManifest = async (sourceName: string) => {
    try {
      await apiPost<unknown>(
        `/api/sources/${encodeURIComponent(sourceName)}/manifest/reset`,
        {},
      );
      toast.success(`Reset manifest for ${sourceName}.`);
      qc.invalidateQueries({ queryKey: ["sources"] });
      qc.invalidateQueries({ queryKey: ["manifest"] });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(`Reset failed: ${msg}`);
    } finally {
      setConfirmReset(null);
    }
  };

  return (
    <div className="stack" style={{ gap: "1.5rem" }}>
      <header className="row">
        <h1 style={{ margin: 0 }}>Sources</h1>
        <div className="spacer" />
        <button onClick={() => sources.refetch()} aria-label="Refetch sources">
          Reload
        </button>
      </header>

      {sources.isLoading && <div className="muted">Loading sources…</div>}
      {sources.isError && (
        <div className="empty-state">
          Could not load sources: {String((sources.error as Error)?.message)}
        </div>
      )}
      {sources.data && sources.data.length === 0 && (
        <div className="empty-state">No sources registered.</div>
      )}

      <div className="grid source-cards">
        {(sources.data ?? []).map((s) => {
          const meta = mergeSourceMeta(s.name, {
            license: s.license ?? undefined,
            cadence: s.cadence ?? undefined,
            source_url: s.source_url ?? undefined,
          });
          const isActive = activeRefresh === s.name;
          return (
            <Card
              key={s.name}
              title={
                <span>
                  <Link to={`/sources/${s.name}`}>{meta.display_name}</Link>{" "}
                  <span className="muted mono">({s.name})</span>
                </span>
              }
              actions={<Badge status={s.status}>{s.status}</Badge>}
            >
              <div className="stack">
                <div className="muted">{meta.description}</div>
                <dl className="kv-list">
                  <dt>Last refresh</dt>
                  <dd>{formatTimestamp(s.last_refresh)}</dd>
                  <dt>Manifest rows</dt>
                  <dd>{formatCount(s.rows_loaded)}</dd>
                  <dt>Warehouse rows</dt>
                  <dd>{formatCount(s.warehouse_rows)}</dd>
                  <dt>Cadence</dt>
                  <dd>{meta.cadence}</dd>
                  <dt>License</dt>
                  <dd>{meta.license}</dd>
                  <dt>URL</dt>
                  <dd>
                    {meta.source_url ? (
                      <a
                        href={meta.source_url}
                        target="_blank"
                        rel="noreferrer noopener"
                      >
                        {meta.source_url}
                      </a>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </dd>
                </dl>
                {s.error && (
                  <div className="muted" style={{ color: "var(--danger)" }}>
                    Error: {s.error}
                  </div>
                )}
                {isActive && refreshJob.state === "running" && (
                  <Progress
                    value={refreshJob.progress}
                    label={refreshJob.step ?? "Refreshing"}
                  />
                )}
                <div className="row">
                  <button
                    onClick={() => startRefresh(s, false)}
                    disabled={isActive}
                    aria-label={`Refresh ${s.name}`}
                  >
                    Refresh
                  </button>
                  <button
                    onClick={() => startRefresh(s, true)}
                    disabled={isActive}
                    aria-label={`Refresh ${s.name} from fixture`}
                  >
                    Refresh from fixture
                  </button>
                  <button
                    onClick={() => navigate(`/sources/${s.name}`)}
                    aria-label={`Preview ${s.name} rows`}
                  >
                    Preview rows
                  </button>
                  <button
                    onClick={() =>
                      navigate(
                        `/sql?q=${encodeURIComponent(selectQuery(s.name))}`,
                      )
                    }
                    aria-label={`Open ${s.name} in SQL`}
                  >
                    Open in SQL
                  </button>
                  <button
                    onClick={() => setConfirmReset({ source: s.name })}
                    aria-label={`Reset manifest for ${s.name}`}
                  >
                    Reset manifest
                  </button>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      <Dialog
        open={Boolean(confirmReset)}
        onClose={() => setConfirmReset(null)}
        title="Reset manifest?"
        actions={
          <>
            <button onClick={() => setConfirmReset(null)}>Cancel</button>
            <button
              className="danger"
              onClick={() => confirmReset && resetManifest(confirmReset.source)}
            >
              Reset
            </button>
          </>
        }
      >
        <p>
          This clears the manifest entry for{" "}
          <strong>{confirmReset?.source}</strong>. Warehouse rows are not
          touched, but the next refresh will reload from scratch.
        </p>
      </Dialog>
    </div>
  );
}
