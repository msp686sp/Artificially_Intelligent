import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Legend,
} from "recharts";
import type { TimeSeriesPoint } from "../api/types";

const SERIES_COLORS = ["#5b8def", "#3aaf85", "#d9a441", "#e15c5c", "#c084fc", "#22d3ee", "#f472b6"];

export interface LineSeries {
  name: string;
  data: TimeSeriesPoint[] | undefined | null;
  color?: string;
}

export interface TimeSeriesLineProps {
  series: LineSeries[];
  height?: number;
  yAxisLabel?: string;
  /** Show the legend (defaults: on if >1 series). */
  showLegend?: boolean;
  /** Compact axis ticks (used in mini-charts). */
  compact?: boolean;
}

function mergeSeries(series: LineSeries[]): Record<string, number | string | null>[] {
  const byDate = new Map<string, Record<string, number | string | null>>();
  for (const s of series) {
    for (const p of s.data ?? []) {
      if (!byDate.has(p.date)) byDate.set(p.date, { date: p.date });
      byDate.get(p.date)![s.name] = p.value;
    }
  }
  return Array.from(byDate.values()).sort((a, b) =>
    String(a.date).localeCompare(String(b.date)),
  );
}

export function TimeSeriesLine({
  series,
  height = 260,
  yAxisLabel,
  showLegend,
  compact = false,
}: TimeSeriesLineProps) {
  const data = mergeSeries(series);
  const legend = showLegend ?? series.length > 1;
  return (
    <div style={{ width: "100%", height }} data-testid="timeseries-line">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="#2a2f3a" strokeDasharray="3 3" />
          <XAxis
            dataKey="date"
            stroke="#9aa0ad"
            tick={{ fontSize: compact ? 9 : 11 }}
            minTickGap={compact ? 40 : 16}
          />
          <YAxis
            stroke="#9aa0ad"
            tick={{ fontSize: compact ? 9 : 11 }}
            width={compact ? 32 : 50}
            label={
              yAxisLabel
                ? { value: yAxisLabel, angle: -90, position: "insideLeft", fill: "#9aa0ad" }
                : undefined
            }
          />
          <Tooltip
            contentStyle={{ background: "#171a23", border: "1px solid #2a2f3a", color: "#e6e8ee" }}
          />
          {legend ? <Legend wrapperStyle={{ fontSize: 11 }} /> : null}
          {series.map((s, i) => (
            <Line
              key={s.name}
              type="monotone"
              dataKey={s.name}
              stroke={s.color ?? SERIES_COLORS[i % SERIES_COLORS.length]}
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default TimeSeriesLine;
