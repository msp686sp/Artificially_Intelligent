import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { SubScores } from "../api/types";

/**
 * 5-axis radar over the platform's sub-scores.
 * Supports single-zip rendering or overlay of multiple zips.
 */

const AXES: Array<{ key: keyof SubScores; label: string }> = [
  { key: "yield_score", label: "Yield" },
  { key: "growth_score", label: "Growth" },
  { key: "stability_score", label: "Stability" },
  { key: "affordability_score", label: "Affordability" },
  { key: "risk_score", label: "Risk" },
];

const SERIES_COLORS = ["#5b8def", "#3aaf85", "#d9a441", "#e15c5c", "#c084fc", "#22d3ee", "#f472b6"];

export interface RadarSeries {
  /** Display name (e.g. zcta5). */
  name: string;
  scores: SubScores | null | undefined;
  /** Optional color override. */
  color?: string;
}

export interface SubScoreRadarProps {
  series: RadarSeries[];
  height?: number;
  /** Force the radius scale (0-100 typical). */
  domain?: [number, number];
}

export function SubScoreRadar({ series, height = 260, domain = [0, 100] }: SubScoreRadarProps) {
  // Recharts radar wants a flat array of points keyed by metric name.
  const data = AXES.map((ax) => {
    const row: Record<string, number | string | null> = { metric: ax.label };
    for (const s of series) {
      const v = s.scores?.[ax.key];
      row[s.name] = typeof v === "number" ? v : null;
    }
    return row;
  });
  return (
    <div style={{ width: "100%", height }} data-testid="subscore-radar">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} cx="50%" cy="50%" outerRadius="70%">
          <PolarGrid stroke="#2a2f3a" />
          <PolarAngleAxis dataKey="metric" stroke="#9aa0ad" tick={{ fontSize: 11 }} />
          <PolarRadiusAxis domain={domain} stroke="#2a2f3a" tick={{ fontSize: 10 }} />
          {series.map((s, i) => (
            <Radar
              key={s.name}
              name={s.name}
              dataKey={s.name}
              stroke={s.color ?? SERIES_COLORS[i % SERIES_COLORS.length]}
              fill={s.color ?? SERIES_COLORS[i % SERIES_COLORS.length]}
              fillOpacity={series.length > 1 ? 0.12 : 0.3}
            />
          ))}
          <Tooltip
            contentStyle={{ background: "#171a23", border: "1px solid #2a2f3a", color: "#e6e8ee" }}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default SubScoreRadar;
