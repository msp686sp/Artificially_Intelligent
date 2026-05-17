import type { TimeSeriesPoint } from "../api/types";
import { TimeSeriesLine, type LineSeries } from "./TimeSeriesLine";

export interface ZhviLineProps {
  series: Array<{ name: string; data: TimeSeriesPoint[] | undefined | null; color?: string }>;
  height?: number;
}

export function ZhviLine({ series, height = 260 }: ZhviLineProps) {
  const ls: LineSeries[] = series.map((s) => ({ name: s.name, data: s.data, color: s.color }));
  return <TimeSeriesLine series={ls} height={height} yAxisLabel="ZHVI ($)" />;
}

export default ZhviLine;
