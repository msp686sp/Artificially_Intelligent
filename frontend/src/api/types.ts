/**
 * Lightweight TypeScript shapes for the responses our pages consume.
 *
 * These are intentionally permissive (fields optional) because the upstream
 * FastAPI schema is owned by agents 2 & 3 and may add fields over time.
 */

export type SortOrder = "asc" | "desc";

export interface RankingRow {
  zcta5: string;
  state?: string | null;
  metro?: string | null;
  county_name?: string | null;
  market_score: number;
  yield_score?: number | null;
  growth_score?: number | null;
  stability_score?: number | null;
  affordability_score?: number | null;
  risk_score?: number | null;
  median_home_value?: number | null;
  median_rent?: number | null;
  gross_yield_monthly_pct?: number | null;
  [k: string]: unknown;
}

export interface RankingsResponse {
  rows: RankingRow[];
  total: number;
  limit: number;
  offset: number;
  sort?: string;
  order?: SortOrder;
}

export interface SubScores {
  yield_score?: number | null;
  growth_score?: number | null;
  stability_score?: number | null;
  affordability_score?: number | null;
  risk_score?: number | null;
  [k: string]: unknown;
}

export interface FeatureEntry {
  name: string;
  raw?: number | null;
  z?: number | null;
  sign?: "+" | "-" | "0" | null;
  contribution?: number | null;
}

export interface FilterStatusEntry {
  name: string;
  passes: boolean;
  threshold?: number | null;
  value?: number | null;
  message?: string | null;
}

export interface CardEntries {
  [k: string]: number | string | null | undefined;
}

export interface ZipDetail {
  zcta5: string;
  state?: string | null;
  metro?: string | null;
  county_name?: string | null;
  market_score?: number | null;
  sub_scores?: SubScores;
  features?: FeatureEntry[];
  filter_status?: FilterStatusEntry[];
  tax?: CardEntries;
  insurance?: CardEntries;
  eviction?: CardEntries;
  climate?: CardEntries;
  [k: string]: unknown;
}

export interface TimeSeriesPoint {
  date: string;
  value: number | null;
}

export interface TimeSeriesResponse {
  zcta5: string;
  series: TimeSeriesPoint[];
  [k: string]: unknown;
}

export interface RedfinSeriesResponse {
  zcta5: string;
  dom?: TimeSeriesPoint[];
  sale_to_list?: TimeSeriesPoint[];
  inventory?: TimeSeriesPoint[];
}

export interface ConfigFile {
  content: string;
  parsed?: unknown;
}

export interface RankingsDryRunDiff {
  added: string[];
  removed: string[];
  score_deltas: Array<{ zcta5: string; old: number | null; new: number | null; delta: number }>;
}
