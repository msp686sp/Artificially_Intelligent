import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { ColumnDef } from "@tanstack/react-table";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useBacktestRun } from "@/hooks/useBacktestRun";
import { Button, Card, Pill, Spinner } from "@/components/ui";
import { DataTable } from "@/components/DataTable";
import type {
  BacktestQuintileMean,
  BacktestSnapshotSpearman,
} from "@/api/types";
import { cn } from "@/lib/cn";

type Tab = "report" | "summary";

function isMobile(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(max-width: 767px)").matches;
}

export default function BacktestDetail() {
  const params = useParams<{ id: string }>();
  const id = params.id ?? "";
  const run = useBacktestRun(id);
  const [tab, setTab] = useState<Tab>("summary");
  const mobile = isMobile();

  const spearmanColumns = useMemo<ColumnDef<BacktestSnapshotSpearman>[]>(
    () => [
      { id: "snapshot", accessorKey: "snapshot", header: "Snapshot" },
      {
        id: "spearman",
        accessorKey: "spearman",
        header: "Spearman",
        cell: ({ getValue }) => {
          const v = getValue() as number | null;
          return v === null || v === undefined ? "—" : v.toFixed(3);
        },
      },
      {
        id: "n",
        accessorKey: "n",
        header: "n",
        cell: ({ getValue }) => (getValue() as number).toLocaleString(),
      },
      {
        id: "baseline",
        accessorKey: "baseline",
        header: "Baseline",
        cell: ({ getValue }) => {
          const v = getValue() as number | null;
          return v === null || v === undefined ? "—" : v.toFixed(3);
        },
      },
    ],
    [],
  );

  const quintileChartData = useMemo(() => {
    if (!run.data) return [];
    const bySnapshot = new Map<string, Record<string, number | string>>();
    for (const q of run.data.quintile_means) {
      const row = bySnapshot.get(q.snapshot) ?? { snapshot: q.snapshot };
      row[`Q${q.quintile}`] = q.mean_realized_return;
      bySnapshot.set(q.snapshot, row);
    }
    return Array.from(bySnapshot.values()).sort((a, b) =>
      String(a.snapshot).localeCompare(String(b.snapshot)),
    );
  }, [run.data]);

  const quintileKeys = useMemo(() => {
    if (!run.data) return [] as string[];
    const set = new Set<number>();
    run.data.quintile_means.forEach((q: BacktestQuintileMean) =>
      set.add(q.quintile),
    );
    return Array.from(set)
      .sort((a, b) => a - b)
      .map((q) => `Q${q}`);
  }, [run.data]);

  if (run.isLoading) {
    return (
      <div className="p-6">
        <Spinner />
      </div>
    );
  }
  if (run.error) {
    return (
      <div className="p-6 text-danger">{(run.error as Error).message}</div>
    );
  }
  if (!run.data) {
    return <div className="p-6 text-fg-muted">Run not found.</div>;
  }

  const ready = run.data.ready;
  const reportSrc = `/api/backtest/runs/${id}/report.html`;

  return (
    <div className="flex flex-col gap-4 p-4 lg:p-6">
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-baseline gap-3">
            <h1 className="text-xl font-semibold">Run {run.data.id}</h1>
            <Pill tone="accent">{run.data.mode}</Pill>
          </div>
          <Link to="/backtest" className="text-sm text-fg-muted hover:underline">
            ← back to runs
          </Link>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm text-fg-muted">
          {run.data.primary_metric !== null &&
            run.data.primary_metric !== undefined && (
              <span>
                primary metric:{" "}
                <strong className="text-fg">
                  {run.data.primary_metric.toFixed(3)}
                </strong>
              </span>
            )}
          {run.data.weights && (
            <details>
              <summary className="cursor-pointer">weights</summary>
              <pre className="mt-1 overflow-auto rounded-md bg-bg-subtle p-2 text-xs">
                {JSON.stringify(run.data.weights, null, 2)}
              </pre>
            </details>
          )}
        </div>
        <div
          className={cn(
            "rounded-md border px-3 py-2 text-sm",
            ready
              ? "border-success bg-success/10 text-success"
              : "border-warning bg-warning/10 text-warning",
          )}
        >
          {ready
            ? "READY — Spearman thresholds met across snapshots."
            : "NOT READY — see snapshot table for which periods missed."}
        </div>
      </header>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-bg-subtle">
        {(["summary", "report"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "px-3 py-2 text-sm font-medium",
              tab === t
                ? "border-b-2 border-accent text-fg"
                : "text-fg-muted hover:text-fg",
            )}
          >
            {t === "summary" ? "Summary" : "Report"}
          </button>
        ))}
      </div>

      {tab === "summary" && (
        <div className="flex flex-col gap-4">
          <Card>
            <h2 className="mb-2 font-semibold">Spearman by snapshot</h2>
            <DataTable
              data={run.data.snapshots}
              columns={spearmanColumns}
              rowKey={(r) => r.snapshot}
              initialSorting={[{ id: "snapshot", desc: false }]}
              enableColumnVisibility={false}
            />
          </Card>
          <Card>
            <h2 className="mb-2 font-semibold">Quintile mean realized return</h2>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={quintileChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2330" />
                  <XAxis dataKey="snapshot" stroke="#9aa0ad" />
                  <YAxis stroke="#9aa0ad" />
                  <Tooltip
                    contentStyle={{
                      background: "#171a23",
                      border: "1px solid #1f2330",
                    }}
                  />
                  <Legend />
                  {quintileKeys.map((q, i) => (
                    <Bar
                      key={q}
                      dataKey={q}
                      fill={
                        [
                          "#e15c5c",
                          "#d9a441",
                          "#9aa0ad",
                          "#7a9ff2",
                          "#3aaf85",
                        ][i % 5]
                      }
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
          {run.data.baseline?.primary_metric !== undefined && (
            <Card>
              <h2 className="mb-2 font-semibold">Baseline comparison</h2>
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="bg-bg-subtle">
                    <th className="px-3 py-2 text-left">Metric</th>
                    <th className="px-3 py-2 text-left">Run</th>
                    <th className="px-3 py-2 text-left">Baseline</th>
                    <th className="px-3 py-2 text-left">Δ</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-t border-bg-subtle">
                    <td className="px-3 py-2">Primary metric</td>
                    <td className="px-3 py-2">
                      {run.data.primary_metric?.toFixed(3) ?? "—"}
                    </td>
                    <td className="px-3 py-2">
                      {run.data.baseline.primary_metric?.toFixed(3) ?? "—"}
                    </td>
                    <td className="px-3 py-2">
                      {run.data.primary_metric !== null &&
                      run.data.primary_metric !== undefined &&
                      run.data.baseline.primary_metric !== null &&
                      run.data.baseline.primary_metric !== undefined
                        ? (
                            run.data.primary_metric -
                            run.data.baseline.primary_metric
                          ).toFixed(3)
                        : "—"}
                    </td>
                  </tr>
                </tbody>
              </table>
            </Card>
          )}
        </div>
      )}

      {tab === "report" &&
        (mobile ? (
          <Card>
            <p className="text-fg-muted">
              The HTML report is large and not optimized for mobile.
            </p>
            <div className="mt-3">
              <Button
                variant="primary"
                onClick={() => window.open(reportSrc, "_blank", "noopener")}
              >
                Open report
              </Button>
            </div>
          </Card>
        ) : (
          <Card className="p-0">
            <iframe
              title="Backtest report"
              src={reportSrc}
              sandbox="allow-same-origin"
              className="h-[calc(100vh-16rem)] w-full rounded-xl bg-white"
            />
          </Card>
        ))}
    </div>
  );
}
