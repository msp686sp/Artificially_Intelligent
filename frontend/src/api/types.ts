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
  /** Optional schema namespace (DuckDB attaches `main` by default). */
  schema?: string;
  kind: "table" | "view";
  name: string;
  columns: SchemaColumn[];
  row_count: number | null;
}

export type SchemaTree = SchemaTableNode[];

// =====================================================================
// Rankings + zips
// =====================================================================

export type SortOrder = "asc" | "desc";

/** Generic shape for the side-card key/value lists on the zip detail page. */
export interface CardEntries {
  [key: string]: unknown;
}

/** Engineered feature row on the zip detail page. */
export interface FeatureEntry {
  name: string;
  raw?: number | null;
  zscore?: number | null;
  /** Alias for zscore — agent 6 routes use this shorter name. */
  z?: number | null;
  sign?: "+" | "-";
  contribution?: number | null;
}

/** One row in the per-zip filter status panel. Accepts either the
 * agent-2/canonical {status:"pass"|"fail"|"skip"} shape or agent-6's
 * {passes:bool, value} variant. */
export interface FilterStatusEntry {
  name: string;
  status?: "pass" | "fail" | "skip";
  reason?: string;
  passes?: boolean;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  value?: any;
}

export interface RankingsQuery {
  state?: string;
  metro?: string;
  min_score?: number;
  max_score?: number;
  sort?: string;
  order?: SortOrder;
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

/** Back-compat alias used by agent 6's hooks. */
export type RankingsResponse = RankingsPage;

/** Flat shape used by the agent-6 zip-detail routes. The API returns the
 * fields documented in plan §5, and agent 6 chose a flat layout. Older
 * code that referenced `identity.county` etc. still works because both
 * old and new fields are present below. */
export interface ZipDetail {
  zcta5: string;
  state?: string | null;
  metro?: string | null;
  county?: string | null;
  county_name?: string | null;

  market_score?: number | null;

  /** Nested optional alias (older callers). */
  identity?: {
    state?: string | null;
    metro?: string | null;
    county?: string | null;
  };
  scores?: {
    market_score?: number;
    yield_score?: number | null;
    demand_score?: number | null;
    supply_score?: number | null;
    operability_score?: number | null;
    risk_score?: number | null;
  };
  /** Flat sub-scores for the radar chart. */
  sub_scores?: {
    yield_score?: number | null;
    demand_score?: number | null;
    supply_score?: number | null;
    operability_score?: number | null;
    risk_score?: number | null;
  };
  features?: Array<{ name: string; raw: number | null; zscore: number | null }> | Record<string, unknown>;
  filters_passed?: string[];
  filters_failed?: string[];
  /** Per-filter result. Accepted as either array or dict form. */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  filter_status?: any;
  tax?: Record<string, unknown>;
  insurance?: Record<string, unknown>;
  eviction?: Record<string, unknown>;
  climate?: Record<string, unknown>;
  /** Index signature so compare-page code can iterate. */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  [key: string]: any;
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

/** Back-compat aliases for agent 6's hook names. */
export type TimeSeriesResponse = TimeseriesResponse;
export type TimeSeriesPoint = TimeseriesPoint;

/** Agent 7 backtest types. */
export interface BacktestRunSummary {
  id: number | string;
  mode?: string;
  started_at?: string;
  finished_at?: string | null;
  status?: string;
  weights?: Record<string, number>;
  primary_metric?: number | null;
  report_path?: string | null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  [key: string]: any;
}

/** A single point along the backtest snapshot grid. */
export interface BacktestSnapshot {
  snapshot: string;
  spearman?: number | null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  [key: string]: any;
}

/** Back-compat alias for agent 7's snapshot-spearman tables. */
export type BacktestSnapshotSpearman = BacktestSnapshot;

/** Quintile-mean row for the bar chart on the run-detail page. */
export interface BacktestQuintileMean {
  snapshot: string;
  quintile: number;
  mean_realized_return: number;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  [key: string]: any;
}

export interface BacktestRunDetail extends BacktestRunSummary {
  snapshots?: BacktestSnapshot[];
  quintile_bins?: unknown[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  baseline?: any;
}

export interface RunRequest {
  start_year: number;
  end_year: number;
}

export interface TuneRequest {
  train_start: number;
  train_end: number;
  validate_start: number;
  validate_end: number;
}

/** WebSocket event over /api/events. */
export interface JobEvent {
  type: string;
  job_id: string;
  payload?: Record<string, unknown>;
  ts?: number;
  timestamp?: string;
}

/** Back-compat aliases for agent 7's hooks. */
export type SqlResponse = SqlRunResponse;
export type SchemaTable = SchemaTableNode;

/** Sub-score bundle for the radar chart. Includes both the canonical
 * 5-dimension names (yield/demand/supply/operability/risk) and the
 * agent-6 chart's growth/stability/affordability projections. */
export interface SubScores {
  yield_score?: number | null;
  demand_score?: number | null;
  supply_score?: number | null;
  operability_score?: number | null;
  risk_score?: number | null;
  growth_score?: number | null;
  stability_score?: number | null;
  affordability_score?: number | null;
}

/** Redfin trio (DOM + sale-to-list + inventory) series response. Agent 6's
 * routes destructure flat ``dom``/``sale_to_list``/``inventory`` arrays. */
export interface RedfinSeriesResponse {
  zcta5: string;
  dom?: Array<{ date: string; value: number | null }>;
  sale_to_list?: Array<{ date: string; value: number | null }>;
  inventory?: Array<{ date: string; value: number | null }>;
  series?: Array<{
    period_end: string;
    median_dom?: number | null;
    median_sale_to_list?: number | null;
    inventory?: number | null;
  }>;
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

// Note: BacktestRunSummary / BacktestRunDetail are declared earlier in
// this file (permissive shape that absorbs both agent 6 + 7 callers).
// Agent 7's stricter declarations have been removed in integration.

// Back-compat aliases for agent 7's hooks.
export type JobResponse = BacktestJobResponse;
export type SqlRequest = SqlRunRequest;

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
