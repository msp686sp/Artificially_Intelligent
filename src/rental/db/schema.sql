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
-- Phase 2 (Demand half) — BLS QCEW county-level employment & wages.
-- Source: https://data.bls.gov/cew/data/files/{year}/csv/{year}_annual_singlefile.zip
-- License: U.S. Government work, public domain. Cadence: annual files land
-- ~May; quarterly files land ~6 months after the quarter close.
-- We filter to county-grain rows (area_fips length 5) at load time, dropping
-- nation/state/MSA aggregates.
-- ============================================================
CREATE TABLE IF NOT EXISTS raw_bls_qcew (
    area_fips      VARCHAR,
    year           INTEGER,
    quarter        INTEGER,    -- 1..4 for quarterly, 0 for annual avg
    industry_code  VARCHAR,    -- NAICS code (e.g. '10' total, '62' health care)
    own_code       INTEGER,    -- ownership (0=total covered, 5=private, etc.)
    employment     BIGINT,     -- avg monthly employment for the period
    total_wages    BIGINT,     -- total wages, whole dollars
    snapshot_date  DATE,
    PRIMARY KEY (area_fips, year, quarter, industry_code, own_code, snapshot_date)
);

-- ============================================================
-- Phase 2 (Demand half) — IRS SOI county-to-county migration.
-- Source: https://www.irs.gov/statistics/soi-tax-stats-migration-data
-- Files like countyinflow1920.csv / countyoutflow1920.csv (TY2019 → TY2020).
-- License: U.S. Government work, public domain. Cadence: annual, ~2yr lag.
-- ============================================================
CREATE TABLE IF NOT EXISTS raw_irs_migration (
    year             INTEGER,    -- end-year of the migration (1920 file → 2020)
    flow_direction   VARCHAR,    -- 'inflow' or 'outflow'
    origin_fips      VARCHAR,    -- 5-char county FIPS (or special aggregate)
    dest_fips        VARCHAR,    -- 5-char county FIPS (or special aggregate)
    returns          BIGINT,     -- number of tax returns
    exemptions       BIGINT,     -- number of personal exemptions (~people)
    agi              BIGINT,     -- aggregate adjusted gross income, thousands $
    snapshot_date    DATE,
    PRIMARY KEY (year, flow_direction, origin_fips, dest_fips, snapshot_date)
);

-- ============================================================
-- Phase 2 (Demand half) — ACS 5-year demographics, ZCTA-grain.
-- Source: https://api.census.gov/data/{year}/acs/acs5
--   ?get=B01003_001E,B19013_001E,B01002_001E&for=zip+code+tabulation+area:*
-- License: U.S. Government work, public domain. Cadence: annual, December.
-- B19013_001E uses -666666666 as the Census "not available" sentinel; we
-- coerce those to NULL at load time.
-- ============================================================
CREATE TABLE IF NOT EXISTS raw_acs_demographics (
    zcta5                   VARCHAR,
    year                    INTEGER,   -- ACS 5yr endyear
    population              BIGINT,    -- B01003_001E
    median_household_income BIGINT,    -- B19013_001E (whole dollars)
    median_age              DOUBLE,    -- B01002_001E
    snapshot_date           DATE,
    PRIMARY KEY (zcta5, year, snapshot_date)
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

-- ============================================================
-- Phase 1 (Yield half) — added by agent/phase2-yield.
-- Additive only: new raw tables for Zillow ZORI (rent index) and
-- Census geo. Schema for geo_zcta / geo_county / geo_cbsa /
-- geo_zcta_county_xwalk above already matches what the loaders write.
-- ============================================================
CREATE TABLE IF NOT EXISTS raw_zillow_zori (
    region_id        VARCHAR,
    zcta5            VARCHAR,
    state            VARCHAR,
    metro            VARCHAR,
    county_name      VARCHAR,
    observation_date DATE,
    zori             DOUBLE,
    snapshot_date    DATE,
    PRIMARY KEY (zcta5, observation_date, snapshot_date)
);
