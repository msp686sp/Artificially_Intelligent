import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { apiPost } from "@/api/client";
import { Card } from "@/components/Card";
import { Stat } from "@/components/Stat";
import { Badge } from "@/components/Badge";
import { Progress } from "@/components/Progress";
import { useToast } from "@/components/Toast";
import { useSources } from "@/hooks/useSources";
import { useManifest } from "@/hooks/useManifest";
import { useHealth, useRankings, useVersion } from "@/hooks/useVersion";
import { useRefreshJob } from "@/hooks/useRefreshJob";
import { formatTimestamp } from "@/lib/source-meta";

export default function DashboardPage() {
  const sources = useSources();
  const manifest = useManifest();
  const rankings = useRankings(5);
  const version = useVersion();
  const health = useHealth();
  const refreshJob = useRefreshJob();
  const toast = useToast();
  const qc = useQueryClient();
  const [refreshing, setRefreshing] = useState(false);
  const [computing, setComputing] = useState(false);

  const warehouseInitialized = health.data?.warehouse?.initialized !== false;
  const zipCount = health.data?.warehouse?.zips ?? 0;

  const stats = useMemo(() => {
    const list = sources.data ?? [];
    return {
      total: list.length,
      ok: list.filter((s) => s.status === "ok").length,
      stale: list.filter((s) => s.status === "stale").length,
      errored: list.filter((s) => s.status === "error").length,
      never: list.filter((s) => s.status === "never").length,
      warehouseRows: list.reduce(
        (acc, s) => acc + (s.warehouse_rows ?? 0),
        0,
      ),
    };
  }, [sources.data]);

  const refreshAll = async () => {
    const list = sources.data ?? [];
    if (list.length === 0) {
      toast.error("No sources to refresh.");
      return;
    }
    setRefreshing(true);
    toast.push(`Kicking off refresh for ${list.length} source(s)…`);
    let okCount = 0;
    let failCount = 0;
    for (const s of list) {
      try {
        await new Promise<void>((resolve) => {
          refreshJob.start(s.name, {
            onComplete: () => {
              okCount += 1;
              resolve();
            },
            onError: () => {
              failCount += 1;
              resolve();
            },
          });
          // Safety: if the WebSocket isn't running yet, the start promise
          // resolves immediately; we rely on the onComplete/onError to
          // terminate the per-source loop. Cap each at 60s.
          setTimeout(resolve, 60_000);
        });
      } catch {
        failCount += 1;
      }
    }
    setRefreshing(false);
    qc.invalidateQueries({ queryKey: ["sources"] });
    qc.invalidateQueries({ queryKey: ["manifest"] });
    if (failCount === 0) toast.success(`Refreshed ${okCount} source(s).`);
    else toast.error(`${okCount} ok, ${failCount} failed.`);
  };

  const computeMarketScore = async () => {
    setComputing(true);
    try {
      await apiPost<unknown>("/api/rankings/populate", {});
      toast.success("MarketScore computed.");
      qc.invalidateQueries({ queryKey: ["rankings-top"] });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(`Failed: ${msg}`);
    } finally {
      setComputing(false);
    }
  };

  const lastBacktest = "—"; // backtest endpoint owned by agent 3; show placeholder.

  const topRows = (rankings.data?.rows ?? []) as Array<{
    zcta5: string;
    market_score?: number;
    state?: string;
  }>;

  if (!warehouseInitialized) {
    return (
      <div data-testid="dashboard-root" className="stack" style={{ gap: "1.5rem" }}>
        <Card title="Warehouse not initialized">
          <div data-testid="dashboard-empty-state" className="stack" style={{ gap: "0.75rem" }}>
            <p className="muted">
              The DuckDB warehouse hasn&apos;t been built yet. Run the
              bootstrap command from a terminal in the repo root to fetch
              source fixtures and populate the warehouse.
            </p>
            <code
              data-testid="dashboard-empty-cta-init"
              style={{
                display: "inline-block",
                padding: "0.5rem 0.75rem",
                borderRadius: "0.375rem",
                background: "var(--bg-subtle, #1a1a1a)",
                fontFamily: "monospace",
              }}
            >
              make init
            </code>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div data-testid="dashboard-root" className="stack" style={{ gap: "1.5rem" }}>
      <header className="row">
        <h1 style={{ margin: 0 }}>Dashboard</h1>
        <div className="spacer" />
        <button onClick={() => sources.refetch()} aria-label="Refetch data">
          Reload
        </button>
        <button
          data-testid="dashboard-quick-refresh-all"
          className="primary"
          onClick={refreshAll}
          disabled={refreshing}
          aria-label="Refresh all sources"
        >
          {refreshing ? "Refreshing…" : "Refresh all"}
        </button>
        <button
          data-testid="dashboard-quick-compute-rank"
          onClick={computeMarketScore}
          disabled={computing}
          aria-label="Compute MarketScore"
        >
          {computing ? "Computing…" : "Compute MarketScore"}
        </button>
      </header>

      {refreshJob.state === "running" && (
        <Card title={`Refreshing ${refreshJob.step ?? "…"}`}>
          <Progress
            value={refreshJob.progress}
            label={
              refreshJob.etaSeconds
                ? `ETA ${refreshJob.etaSeconds}s`
                : "in progress"
            }
          />
        </Card>
      )}

      <section className="grid cards" aria-label="Top-line metrics">
        <div data-testid="dashboard-stat-sources-ok">
          <Stat label="Sources OK" value={stats.ok} hint={`${stats.total} total`} />
        </div>
        <div data-testid="dashboard-stat-sources-stale">
          <Stat label="Sources stale" value={stats.stale} />
        </div>
        <div data-testid="dashboard-stat-sources-error">
          <Stat label="Sources errored" value={stats.errored} />
        </div>
        <div data-testid="dashboard-stat-zip-count">
          <Stat label="ZIPs in warehouse" value={zipCount.toLocaleString()} />
        </div>
      </section>

      <Card
        title="Top 5 by market_score"
        actions={<Link to="/rankings">View all →</Link>}
      >
        {rankings.isLoading ? (
          <div className="muted">Loading…</div>
        ) : rankings.isError ? (
          <div className="muted">
            No rankings yet — click <strong>Compute MarketScore</strong> to
            populate.
          </div>
        ) : topRows.length === 0 ? (
          <table data-testid="dashboard-top5-table">
            <tbody>
              <tr>
                <td className="muted">No rankings yet.</td>
              </tr>
            </tbody>
          </table>
        ) : (
          <table data-testid="dashboard-top5-table">
            <thead>
              <tr>
                <th>ZIP</th>
                <th>State</th>
                <th>Score</th>
              </tr>
            </thead>
            <tbody>
              {topRows.map((r) => (
                <tr key={r.zcta5}>
                  <td>
                    <Link to={`/rankings/${r.zcta5}`}>{r.zcta5}</Link>
                  </td>
                  <td>{r.state ?? ""}</td>
                  <td>
                    {typeof r.market_score === "number"
                      ? r.market_score.toFixed(2)
                      : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <section className="grid" style={{ gridTemplateColumns: "1fr" }}>
        <Card title="Manifest summary">
          {manifest.isLoading ? (
            <div className="muted">Loading manifest…</div>
          ) : manifest.isError ? (
            <div className="muted">Could not load manifest.</div>
          ) : (manifest.data ?? []).length === 0 ? (
            <div className="muted">Manifest is empty.</div>
          ) : (
            <ul style={{ paddingLeft: "1rem", margin: 0 }}>
              {(manifest.data ?? []).slice(0, 5).map((m) => (
                <li key={m.source}>
                  <Link to={`/sources/${m.source}`}>{m.source}</Link>{" "}
                  <Badge status={m.status}>{m.status}</Badge>{" "}
                  <span className="muted">
                    {formatTimestamp(m.last_refresh)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Last backtest">
          <div data-testid="dashboard-recent-backtest" className="muted">
            {lastBacktest}
          </div>
        </Card>

        <Card title="Version">
          {version.data ? (
            <dl className="kv-list">
              <dt>API</dt>
              <dd>{version.data.api}</dd>
              <dt>App</dt>
              <dd>{version.data.app}</dd>
              <dt>Python</dt>
              <dd>{version.data.python}</dd>
            </dl>
          ) : (
            <div className="muted">Loading…</div>
          )}
        </Card>
      </section>
    </div>
  );
}
