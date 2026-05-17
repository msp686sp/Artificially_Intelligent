import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export interface ScoreHistogramProps {
  /** Raw market_score values to bin. */
  values: number[];
  /** Bin count, default 20. */
  bins?: number;
  height?: number;
}

/**
 * Cheap client-side histogram used as a sidebar widget on /rankings when
 * there is room. Keeps the layout informative even on slow API responses.
 */
export function ScoreHistogram({ values, bins = 20, height = 160 }: ScoreHistogramProps) {
  const cleaned = values.filter((v) => typeof v === "number" && !Number.isNaN(v));
  if (cleaned.length === 0) {
    return (
      <div className="rounded-lg border border-bg-panel bg-bg-subtle p-3 text-xs text-fg-subtle">
        No scores yet.
      </div>
    );
  }
  const min = Math.min(...cleaned);
  const max = Math.max(...cleaned);
  const step = (max - min) / bins || 1;
  const buckets = Array.from({ length: bins }, (_, i) => ({
    bin: `${(min + step * i).toFixed(0)}`,
    count: 0,
    start: min + step * i,
    end: min + step * (i + 1),
  }));
  for (const v of cleaned) {
    let idx = Math.floor((v - min) / step);
    if (idx >= bins) idx = bins - 1;
    if (idx < 0) idx = 0;
    buckets[idx].count += 1;
  }
  return (
    <div style={{ width: "100%", height }} data-testid="score-histogram">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={buckets} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="#2a2f3a" strokeDasharray="3 3" />
          <XAxis dataKey="bin" stroke="#9aa0ad" tick={{ fontSize: 10 }} />
          <YAxis stroke="#9aa0ad" tick={{ fontSize: 10 }} width={28} />
          <Tooltip
            contentStyle={{ background: "#171a23", border: "1px solid #2a2f3a", color: "#e6e8ee" }}
          />
          <Bar dataKey="count" fill="#5b8def" isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default ScoreHistogram;
