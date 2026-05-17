import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useBacktestRunsByIds } from "@/hooks/useBacktestRun";
import { Card, Spinner } from "@/components/ui";
import { cn } from "@/lib/cn";

const LINE_COLORS = [
  "#5b8def",
  "#3aaf85",
  "#d9a441",
  "#e15c5c",
  "#9aa0ad",
  "#7a9ff2",
  "#a06bff",
  "#ff8aa7",
];

export default function BacktestCompare() {
  const [params] = useSearchParams();
  const ids = useMemo(
    () =>
      (params.get("ids") ?? "")
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
    [params],
  );
  const queries = useBacktestRunsByIds(ids);
  const loading = queries.some((q) => q.isLoading);
  const errors = queries.filter((q) => q.error).map((q) => q.error as Error);
  const runs = queries.map((q) => q.data).filter((d): d is NonNullable<typeof d> => Boolean(d));

  const weightKeys = useMemo(() => {
    const set = new Set<string>();
    for (const r of runs) {
      for (const k of Object.keys(r.weights ?? {})) set.add(k);
    }
    return Array.from(set).sort();
  }, [runs]);

  const baselineFirstRun = runs[0];

  const spearmanChartData = useMemo(() => {
    const snapshotSet = new Set<string>();
    for (const r of runs) {
      r.snapshots.forEach((s) => snapshotSet.add(s.snapshot));
    }
    const snapshots = Array.from(snapshotSet).sort();
    return snapshots.map((snapshot) => {
      const row: Record<string, number | string> = { snapshot };
      for (const r of runs) {
        const match = r.snapshots.find((s) => s.snapshot === snapshot);
        if (match) row[r.id] = match.spearman;
      }
      return row;
    });
  }, [runs]);

  if (ids.length === 0) {
    return (
      <div className="p-6 text-fg-muted">
        No run IDs provided. <Link to="/backtest">Pick some.</Link>
      </div>
    );
  }
  if (loading) {
    return (
      <div className="p-6">
        <Spinner />
      </div>
    );
  }
  if (errors.length > 0) {
    return (
      <div className="p-6 text-danger">
        {errors.map((e, i) => (
          <div key={i}>{e.message}</div>
        ))}
      </div>
    );
  }

  return (
    <div
      className="flex flex-col gap-4 p-4 lg:p-6"
      data-testid="backtest-compare-root"
    >
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold">Compare runs</h1>
        <Link to="/backtest" className="text-sm text-fg-muted hover:underline">
          ← back to runs
        </Link>
      </header>
      <div className="text-sm text-fg-muted">
        Comparing {runs.length} run{runs.length === 1 ? "" : "s"}:{" "}
        {runs.map((r, i) => (
          <span key={r.id}>
            <Link to={`/backtest/${r.id}`} className="text-accent hover:underline">
              {r.id}
            </Link>
            {i < runs.length - 1 ? ", " : ""}
          </span>
        ))}
      </div>

      <Card>
        <h2 className="mb-2 font-semibold">Weight diff</h2>
        <div className="overflow-auto">
          <table
            data-testid="backtest-compare-weight-diff"
            className="min-w-full text-sm"
          >
            <thead className="bg-bg-subtle">
              <tr>
                <th className="px-3 py-2 text-left">Weight</th>
                {runs.map((r) => (
                  <th key={r.id} className="px-3 py-2 text-left">
                    {r.id}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {weightKeys.map((key) => {
                const values = runs.map((r) => r.weights?.[key]);
                const allEq = values.every((v) => v === values[0]);
                return (
                  <tr key={key} className="border-t border-bg-subtle">
                    <td className="px-3 py-2 font-medium">{key}</td>
                    {values.map((v, i) => (
                      <td
                        key={runs[i].id}
                        className={cn(
                          "px-3 py-2",
                          !allEq && "bg-warning/10 text-warning",
                        )}
                      >
                        {v === undefined ? "—" : v.toFixed(3)}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <Card>
        <h2 className="mb-2 font-semibold">Spearman by snapshot</h2>
        <div className="h-72" data-testid="backtest-compare-spearman">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={spearmanChartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2330" />
              <XAxis dataKey="snapshot" stroke="#9aa0ad" />
              <YAxis stroke="#9aa0ad" domain={[-1, 1]} />
              <Tooltip
                contentStyle={{
                  background: "#171a23",
                  border: "1px solid #1f2330",
                }}
              />
              <Legend />
              {runs.map((r, i) => (
                <Line
                  key={r.id}
                  type="monotone"
                  dataKey={r.id}
                  stroke={LINE_COLORS[i % LINE_COLORS.length]}
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {baselineFirstRun?.baseline?.primary_metric !== undefined && (
        <Card>
          <h2 className="mb-2 font-semibold">Baseline deltas</h2>
          <div className="overflow-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-bg-subtle">
                <tr>
                  <th className="px-3 py-2 text-left">Run</th>
                  <th className="px-3 py-2 text-left">Primary metric</th>
                  <th className="px-3 py-2 text-left">Baseline</th>
                  <th className="px-3 py-2 text-left">Δ</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => {
                  const base = r.baseline?.primary_metric ?? null;
                  const delta =
                    r.primary_metric !== null &&
                    r.primary_metric !== undefined &&
                    base !== null &&
                    base !== undefined
                      ? r.primary_metric - base
                      : null;
                  return (
                    <tr key={r.id} className="border-t border-bg-subtle">
                      <td className="px-3 py-2">{r.id}</td>
                      <td className="px-3 py-2">
                        {r.primary_metric?.toFixed(3) ?? "—"}
                      </td>
                      <td className="px-3 py-2">
                        {base !== null && base !== undefined
                          ? base.toFixed(3)
                          : "—"}
                      </td>
                      <td
                        className={cn(
                          "px-3 py-2",
                          delta !== null && delta > 0 && "text-success",
                          delta !== null && delta < 0 && "text-danger",
                        )}
                      >
                        {delta === null ? "—" : delta.toFixed(3)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
