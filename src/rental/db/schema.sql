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

-- ------------------------------------------------------------
-- Phase 3 (supply): Census Building Permits Survey, county grain.
-- One row per (county, year, period) where period is 'annual' or
-- '01'..'12' for monthly observations.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw_census_bps (
    county_fips         VARCHAR,
    year                INTEGER,
    period              VARCHAR,   -- 'annual' or zero-padded month '01'..'12'
    single_family_units INTEGER,
    multi_family_units  INTEGER,
    total_units         INTEGER,
    total_value         BIGINT,    -- USD, reported by BPS as construction value
    snapshot_date       DATE,
    PRIMARY KEY (county_fips, year, period, snapshot_date)
);

-- ------------------------------------------------------------
-- Phase 3 (supply): ACS B25001 total housing units, county grain.
-- Used to normalize permits → permits-per-1000-housing-units.
-- Demand agent owns ACS demographics (population/income); this is a
-- separate, narrow housing-stock fetch so the supply layer doesn't
-- depend on demand-agent column choices. Orchestrator may dedupe later.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw_acs_housing_stock (
    county_fips         VARCHAR,
    year                INTEGER,   -- ACS 5-year end year
    total_housing_units INTEGER,
    snapshot_date       DATE,
    PRIMARY KEY (county_fips, year, snapshot_date)
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
