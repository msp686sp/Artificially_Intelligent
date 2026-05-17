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
import { useRankings, useVersion } from "@/hooks/useVersion";
import { useRefreshJob } from "@/hooks/useRefreshJob";
import { formatTimestamp } from "@/lib/source-meta";

export default function DashboardPage() {
  const sources = useSources();
  const manifest = useManifest();
  const rankings = useRankings(5);
  const version = useVersion();
  const refreshJob = useRefreshJob();
  const toast = useToast();
  const qc = useQueryClient();
  const [refreshing, setRefreshing] = useState(false);
  const [computing, setComputing] = useState(false);

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

  return (
    <div className="stack" style={{ gap: "1.5rem" }}>
      <header className="row">
        <h1 style={{ margin: 0 }}>Dashboard</h1>
        <div className="spacer" />
        <button onClick={() => sources.refetch()} aria-label="Refetch data">
          Reload
        </button>
        <button
          className="primary"
          onClick={refreshAll}
          disabled={refreshing}
          aria-label="Refresh all sources"
        >
          {refreshing ? "Refreshing…" : "Refresh all"}
        </button>
        <button
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
        <Stat label="Sources OK" value={stats.ok} hint={`${stats.total} total`} />
        <Stat label="Sources stale" value={stats.stale} />
        <Stat label="Sources errored" value={stats.errored} />
        <Stat label="Warehouse rows" value={stats.warehouseRows.toLocaleString()} />
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
          <div className="muted">No rankings yet.</div>
        ) : (
          <ol style={{ paddingLeft: "1.25rem", margin: 0 }}>
            {topRows.map((r) => (
              <li key={r.zcta5}>
                <Link to={`/rankings/${r.zcta5}`}>
                  {r.zcta5}
                  {r.state ? ` (${r.state})` : ""}
                </Link>
                {typeof r.market_score === "number" && (
                  <span className="muted"> — {r.market_score.toFixed(2)}</span>
                )}
              </li>
            ))}
          </ol>
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
          <div className="muted">{lastBacktest}</div>
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
