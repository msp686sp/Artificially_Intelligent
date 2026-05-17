// Hand-written TypeScript types matching the API contracts in
// docs/gooey-plan.md §5. Other agents will refine these as they
// implement their slice of the API; the production build will
// eventually replace this file with an OpenAPI-generated client.

// =====================================================================
// Health + meta
// =====================================================================

export type SourceStatus = "ok" | "stale" | "error" | "never";

export interface HealthInfo {
  status: "ok" | "degraded" | "down";
  version: string;
  uptime_s: number;
  warehouse_path?: string | null;
  manifest_path?: string | null;
}

export interface VersionInfo {
  api: string;
  app: string;
  python: string;
}

// =====================================================================
// Sources
// =====================================================================

export interface SourceSummary {
  name: string;
  last_refresh: string | null;
  rows_loaded: number | null;
  status: SourceStatus;
  source_url?: string | null;
  license?: string | null;
  cadence?: string | null;
  warehouse_rows?: number | null;
  error?: string | null;
}

export interface SchemaColumn {
  name: string;
  type: string;
  nullable: boolean;
}

export interface SourceSchema {
  table: string;
  columns: SchemaColumn[];
  row_count: number | null;
}

export interface PreviewPage {
  columns: string[];
  rows: Array<Record<string, unknown>>;
  total: number;
  limit: number;
  offset: number;
}

export interface RefreshJobResponse {
  job_id: string;
}

/** Server-Sent / WebSocket event from /api/events for a refresh job. */
export interface RefreshJobEvent {
  type: string;
  job_id: string;
  payload?: Record<string, unknown>;
  ts?: number;
  timestamp?: string;
}

// =====================================================================
// SQL + schema
// =====================================================================

export interface SqlRunRequest {
  query: string;
  limit?: number;
  read_only?: boolean;
}

export interface SqlRunResponse {
  columns: string[];
  rows: Array<Record<string, unknown>>;
  elapsed_ms: number;
  row_count: number;
  truncated?: boolean;
}

export interface SchemaTableNode {
  kind: "table" | "view";
  name: string;
  columns: SchemaColumn[];
  row_count: number | null;
}

export type SchemaTree = SchemaTableNode[];

// =====================================================================
// Rankings + zips
// =====================================================================

export interface RankingsQuery {
  state?: string;
  metro?: string;
  min_score?: number;
  max_score?: number;
  sort?: string;
  order?: "asc" | "desc";
  limit?: number;
  offset?: number;
  filters_yaml?: string;
}

export interface RankingRow {
  zcta5: string;
  state?: string | null;
  metro?: string | null;
  county?: string | null;
  market_score: number;
  yield_score?: number | null;
  demand_score?: number | null;
  supply_score?: number | null;
  operability_score?: number | null;
  risk_score?: number | null;
  [feature: string]: unknown;
}

export interface RankingsPage {
  rows: RankingRow[];
  total: number;
  limit: number;
  offset: number;
}

export interface ZipDetail {
  zcta5: string;
  identity: {
    state?: string | null;
    metro?: string | null;
    county?: string | null;
  };
  scores: {
    market_score: number;
    yield_score?: number | null;
    demand_score?: number | null;
    supply_score?: number | null;
    operability_score?: number | null;
    risk_score?: number | null;
  };
  features: Array<{ name: string; raw: number | null; zscore: number | null }>;
  filters_passed?: string[];
  filters_failed?: string[];
}

export interface CompareResponse {
  zips: Record<string, ZipDetail>;
}

export interface TimeseriesPoint {
  date: string;
  value: number | null;
}

export interface TimeseriesResponse {
  zcta5: string;
  series: TimeseriesPoint[];
}

// =====================================================================
// Charts
// =====================================================================

export interface HistogramBin {
  x0: number;
  x1: number;
  count: number;
}

export interface HistogramResponse {
  bins: HistogramBin[];
  dim: string;
}

export interface ScatterPoint {
  x: number;
  y: number;
  zcta5?: string;
}

export interface ScatterResponse {
  points: ScatterPoint[];
  x_label: string;
  y_label: string;
}

// =====================================================================
// Manifest + config
// =====================================================================

export interface ManifestEntry {
  source: string;
  last_refresh: string | null;
  rows_loaded: number;
  status: SourceStatus;
  error?: string | null;
  age_seconds?: number | null;
}

export interface ConfigFile {
  content: string;
  parsed?: unknown;
}

export type ConfigFileName = "filters.yaml" | "weights.yaml" | "watchlist.yaml";

// =====================================================================
// Backtest
// =====================================================================

export interface BacktestRunRequest {
  start_year: number;
  end_year: number;
}

export interface BacktestTuneRequest {
  train_start: number;
  train_end: number;
  validate_start: number;
  validate_end: number;
}

export interface BacktestJobResponse {
  job_id: string;
  run_id: number;
}

export interface BacktestRunSummary {
  id: number;
  started_at: string;
  finished_at: string | null;
  mode: "run" | "tune";
  weights: Record<string, number>;
  primary_metric: number | null;
  ready: boolean | null;
}

export interface BacktestRunDetail extends BacktestRunSummary {
  snapshots: Array<{ snapshot: string; spearman: number | null; n: number }>;
  quintile_bins: Array<{ quintile: number; mean: number; n: number }>;
  html_report_path: string | null;
}

// =====================================================================
// Refresh log
// =====================================================================

export interface RefreshLogRow {
  id: number;
  source: string;
  started_at: string;
  finished_at: string | null;
  status: SourceStatus;
  rows_loaded: number | null;
  error: string | null;
}

// =====================================================================
// WebSocket events
// =====================================================================

export type WsEventType =
  | "refresh.progress"
  | "refresh.complete"
  | "refresh.error"
  | "backtest.progress"
  | "backtest.complete"
  | "backtest.error";

export interface WsEvent<P = Record<string, unknown>> {
  type: WsEventType;
  job_id: string;
  payload: P;
}

export interface RefreshProgressPayload {
  step?: string;
  percent?: number;
  eta_seconds?: number | null;
  rows_loaded?: number;
  error?: string;
  source?: string;
}

export interface BacktestProgressPayload {
  step?: string;
  percent?: number;
  snapshots_done?: number;
  snapshots_total?: number;
  run_id?: number;
  error?: string;
}
