import duckdb

from rental.db import init_schema


def test_schema_is_idempotent():
    con = duckdb.connect(":memory:")
    init_schema(con)
    init_schema(con)  # re-applying must not error
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    expected = {
        # Phase 0
        "geo_zcta", "geo_county", "geo_cbsa", "geo_zcta_county_xwalk",
        "raw_zillow_zhvi", "refresh_log",
        # Phase 1 (yield) + Redfin
        "raw_zillow_zori", "raw_redfin_market",
        # Phase 2 (demand)
        "raw_bls_qcew", "raw_irs_migration", "raw_acs_demographics",
        # Phase 3 (supply)
        "raw_census_bps", "raw_acs_housing_stock",
        # Phase 4 (operability + risk)
        "raw_county_tax_rate", "ref_state_insurance",
        "raw_eviction_lab", "raw_fema_nri",
    }
    assert expected <= tables
