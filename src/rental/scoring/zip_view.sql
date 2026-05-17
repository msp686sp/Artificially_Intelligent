-- Phase 5 composite layer: views that the ranking pipeline consumes.
--
-- The underlying sub-score and feature tables are produced by sibling
-- agents (one per dimension). To keep this idempotent and resilient to
-- partial coverage, we:
--
--   1. Ensure the canonical zip_scores skeleton table always exists
--      (created in schema.sql).
--   2. CREATE OR REPLACE VIEW zip_scores_v as a thin pass-through over
--      that table, exposing the contract columns the composite reader
--      expects. If the table is empty, the view is empty — the
--      pipeline degrades gracefully rather than crashing.
--   3. CREATE OR REPLACE VIEW zip_features as a stub union of the
--      feature columns the hard filters need. Each feature source
--      agent will replace this view (or extend it via a separate DDL)
--      once their underlying table lands.
--
-- The Python loader (`init_composite_views`) runs this script after
-- schema.sql, so referenced tables exist as empty skeletons.

-- Pass-through view over the zip_scores skeleton. Sibling agents write
-- to the underlying table; downstream consumers read this view.
CREATE OR REPLACE VIEW zip_scores_v AS
SELECT
    zcta5,
    state,
    metro,
    county_name,
    yield_score,
    demand_score,
    supply_score,
    operability_score,
    risk_score,
    snapshot_date
FROM zip_scores;

-- Features view (stub). Today this returns no rows because no feature
-- tables exist yet. As sibling agents land yield/demand/supply/risk
-- feature tables, they replace this view with a real join. The hard
-- filter engine tolerates missing columns, so the pipeline still runs.
CREATE OR REPLACE VIEW zip_features AS
SELECT
    CAST(NULL AS VARCHAR)  AS zcta5,
    CAST(NULL AS VARCHAR)  AS state,
    CAST(NULL AS VARCHAR)  AS metro,
    CAST(NULL AS VARCHAR)  AS county_name,
    CAST(NULL AS DOUBLE)   AS median_home_price,
    CAST(NULL AS DOUBLE)   AS gross_yield_monthly_pct,
    CAST(NULL AS INTEGER)  AS zori_coverage_months,
    CAST(NULL AS DOUBLE)   AS population_cagr_10yr,
    CAST(NULL AS BOOLEAN)  AS rent_controlled,
    CAST(NULL AS BOOLEAN)  AS high_climate_risk
WHERE FALSE;
