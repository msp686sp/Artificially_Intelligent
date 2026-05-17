// Types returned by api-core (agent 1). Keep these aligned with the
// pydantic schemas; the production build will replace this hand-rolled
// file with an OpenAPI-generated client.

export type SourceStatus = "ok" | "stale" | "error" | "never";

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

export interface ManifestEntry {
  source: string;
  last_refresh: string | null;
  rows_loaded: number;
  status: SourceStatus;
  error?: string | null;
  age_seconds?: number | null;
}

export interface RefreshLogRow {
  id: number;
  source: string;
  started_at: string;
  finished_at: string | null;
  status: SourceStatus;
  rows_loaded: number | null;
  error: string | null;
}

export interface VersionInfo {
  api: string;
  app: string;
  python: string;
}

export interface HealthInfo {
  status: "ok" | "degraded" | "down";
  version: string;
  uptime_s: number;
  warehouse_path?: string | null;
  manifest_path?: string | null;
}

export interface RefreshJobResponse {
  job_id: string;
}

export interface RefreshJobEvent {
  type: "refresh.progress" | "refresh.complete" | "refresh.error";
  job_id: string;
  payload: {
    step?: string;
    percent?: number;
    eta_seconds?: number | null;
    rows_loaded?: number;
    error?: string;
    source?: string;
  };
}

export interface RankingsTop {
  zcta5: string;
  state?: string | null;
  metro?: string | null;
  market_score: number;
}
