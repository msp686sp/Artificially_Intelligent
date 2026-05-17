-- Rental warehouse schema (Phase 0).
-- Idempotent. Add later-phase tables in additive ALTER blocks below.

-- ============================================================
-- Geographic spine (populated in a later Phase 0 step from
-- Census ZCTA Gazetteer + ZCTA-County relationship file).
-- ============================================================
CREATE TABLE IF NOT EXISTS geo_zcta (
    zcta5         VARCHAR PRIMARY KEY,
    state         VARCHAR,
    population    INTEGER,
    aland_sqmi    DOUBLE
);

CREATE TABLE IF NOT EXISTS geo_county (
    county_fips   VARCHAR PRIMARY KEY,
    state         VARCHAR,
    county_name   VARCHAR,
    cbsa_code     VARCHAR,
    population    INTEGER
);

CREATE TABLE IF NOT EXISTS geo_cbsa (
    cbsa_code     VARCHAR PRIMARY KEY,
    cbsa_name     VARCHAR,
    cbsa_type     VARCHAR  -- 'Metropolitan' or 'Micropolitan'
);

CREATE TABLE IF NOT EXISTS geo_zcta_county_xwalk (
    zcta5            VARCHAR,
    county_fips      VARCHAR,
    res_ratio        DOUBLE,   -- residential population share of the zcta in this county
    PRIMARY KEY (zcta5, county_fips)
);

-- ============================================================
-- Raw source layer (mirrors source files; append/upsert).
-- ============================================================
CREATE TABLE IF NOT EXISTS raw_zillow_zhvi (
    region_id        VARCHAR,
    zcta5            VARCHAR,
    state            VARCHAR,
    metro            VARCHAR,
    county_name      VARCHAR,
    observation_date DATE,
    zhvi             DOUBLE,
    snapshot_date    DATE,
    PRIMARY KEY (zcta5, observation_date, snapshot_date)
);

-- ============================================================
-- Phase 1/3 (Redfin): zip-code market tracker (DOM, sale-to-list,
-- inventory). Sourced from Redfin Data Center's public S3 TSV.
-- Owned by the Redfin agent; consumed by SupplyScore and
-- OperabilityScore feature builders.
-- ============================================================
CREATE TABLE IF NOT EXISTS raw_redfin_market (
    zcta5                VARCHAR,
    period_begin         DATE,
    period_end           DATE,
    median_dom           DOUBLE,
    median_sale_to_list  DOUBLE,
    inventory            DOUBLE,
    new_listings         DOUBLE,
    median_sale_price    DOUBLE,
    homes_sold           DOUBLE,
    snapshot_date        DATE,
    PRIMARY KEY (zcta5, period_begin, snapshot_date)
);

-- ============================================================
-- Refresh audit.
-- ============================================================
CREATE TABLE IF NOT EXISTS refresh_log (
    source        VARCHAR,
    started_at    TIMESTAMP,
    finished_at   TIMESTAMP,
    rows_loaded   BIGINT,
    status        VARCHAR,
    error         VARCHAR
);
