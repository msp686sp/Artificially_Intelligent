// Shared API types. The production build replaces this hand-rolled file with
// an OpenAPI-generated client. Keep aligned with the pydantic schemas.

export type SourceStatus = "ok" | "stale" | "error" | "never";

export interface SchemaColumn {
  name: string;
  type: string;
  nullable: boolean;
}

export interface SchemaTable {
  kind: "table" | "view";
  name: string;
  columns: SchemaColumn[];
  row_count: number | null;
  schema?: string | null;
}

export type SchemaTree = SchemaTable[];

export interface SqlRequest {
  query: string;
  limit?: number;
  read_only?: boolean;
}

export interface SqlResponse {
  columns: string[];
  rows: Array<Record<string, unknown>>;
  elapsed_ms: number;
  row_count: number;
  truncated?: boolean;
}

export type BacktestMode = "run" | "tune";
export type BacktestStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "ready"
  | "not_ready";

export interface BacktestRunSummary {
  id: string;
  mode: BacktestMode;
  started_at: string;
  finished_at?: string | null;
  duration_s?: number | null;
  primary_metric?: number | null;
  status: BacktestStatus;
  weights?: Record<string, number>;
}

export interface BacktestQuintileMean {
  snapshot: string;
  quintile: number;
  mean_realized_return: number;
}

export interface BacktestSnapshotSpearman {
  snapshot: string;
  spearman: number;
  n: number;
  baseline?: number | null;
}

export interface BacktestRunDetail extends BacktestRunSummary {
  snapshots: BacktestSnapshotSpearman[];
  quintile_means: BacktestQuintileMean[];
  baseline?: {
    primary_metric?: number | null;
    spearman_by_snapshot?: BacktestSnapshotSpearman[];
  } | null;
  ready: boolean;
  html_report_path?: string | null;
  notes?: string | null;
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

export interface JobResponse {
  job_id: string;
  run_id?: string;
}

export interface JobEvent {
  type: string; // "refresh.progress" | "backtest.progress" | ...
  job_id: string;
  payload: Record<string, unknown>;
}
