import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export interface FeatureScatterPoint {
  feature: number;
  score: number;
  zcta5?: string;
}

export interface FeatureScatterProps {
  points: FeatureScatterPoint[];
  featureLabel: string;
  scoreLabel?: string;
  height?: number;
}

export function FeatureScatter({
  points,
  featureLabel,
  scoreLabel = "market_score",
  height = 240,
}: FeatureScatterProps) {
  return (
    <div style={{ width: "100%", height }} data-testid="feature-scatter">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 16, left: 0, bottom: 24 }}>
          <CartesianGrid stroke="#2a2f3a" strokeDasharray="3 3" />
          <XAxis
            type="number"
            dataKey="feature"
            stroke="#9aa0ad"
            tick={{ fontSize: 10 }}
            label={{ value: featureLabel, position: "insideBottom", offset: -8, fill: "#9aa0ad" }}
          />
          <YAxis
            type="number"
            dataKey="score"
            stroke="#9aa0ad"
            tick={{ fontSize: 10 }}
            width={36}
            label={{
              value: scoreLabel,
              angle: -90,
              position: "insideLeft",
              fill: "#9aa0ad",
            }}
          />
          <Tooltip
            contentStyle={{ background: "#171a23", border: "1px solid #2a2f3a", color: "#e6e8ee" }}
            cursor={{ stroke: "#2a2f3a" }}
          />
          <Scatter data={points} fill="#5b8def" isAnimationActive={false} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

export default FeatureScatter;
