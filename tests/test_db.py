import duckdb

from rental.db import init_schema


def test_schema_is_idempotent():
    con = duckdb.connect(":memory:")
    init_schema(con)
    init_schema(con)  # re-applying must not error
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    expected = {
        "geo_zcta", "geo_county", "geo_cbsa", "geo_zcta_county_xwalk",
        "raw_zillow_zhvi", "refresh_log",
        # Phase 4 (operability + risk)
        "raw_county_tax_rate", "ref_state_insurance",
        "raw_eviction_lab", "raw_fema_nri",
    }
    assert expected <= tables
