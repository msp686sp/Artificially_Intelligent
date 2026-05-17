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

-- ----- Phase 4: Operability + Risk raw layer -----
-- County effective property-tax rate, derived from ACS B25103 / B25077.
CREATE TABLE IF NOT EXISTS raw_county_tax_rate (
    county_fips        VARCHAR,
    year               INTEGER,
    median_tax_paid    DOUBLE,
    median_home_value  DOUBLE,
    effective_rate     DOUBLE,   -- median_tax_paid / median_home_value
    snapshot_date      DATE,
    PRIMARY KEY (county_fips, year, snapshot_date)
);

-- Curated state-level homeowner insurance averages (NAIC Homeowners Insurance
-- Report). Bundled as a versioned reference table, not refreshed dynamically.
CREATE TABLE IF NOT EXISTS ref_state_insurance (
    state                VARCHAR,
    year                 INTEGER,
    avg_annual_premium   DOUBLE,
    policy_form          VARCHAR,   -- e.g. 'HO-3'
    source               VARCHAR,
    PRIMARY KEY (state, year, policy_form)
);

-- Eviction Lab county-level filings + rates.
CREATE TABLE IF NOT EXISTS raw_eviction_lab (
    county_fips           VARCHAR,
    year                  INTEGER,
    evictions_filed       DOUBLE,
    eviction_filing_rate  DOUBLE,   -- filings per 100 renter households
    snapshot_date         DATE,
    PRIMARY KEY (county_fips, year, snapshot_date)
);

-- FEMA National Risk Index, county grain.
CREATE TABLE IF NOT EXISTS raw_fema_nri (
    county_fips        VARCHAR,
    risk_index_score   DOUBLE,
    flood_score        DOUBLE,
    wildfire_score     DOUBLE,
    hurricane_score    DOUBLE,
    heatwave_score     DOUBLE,
    snapshot_date      DATE,
    PRIMARY KEY (county_fips, snapshot_date)
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
