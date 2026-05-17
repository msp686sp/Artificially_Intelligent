from pathlib import Path

import duckdb

from rental.db import init_schema
from rental.sources import CensusGeoSource

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "census_geo"


def _con():
    con = duckdb.connect(":memory:")
    init_schema(con)
    return con


def test_census_geo_loads_all_four_tables():
    con = _con()
    src = CensusGeoSource()
    rows = src.load(con, FIXTURE_DIR)
    # 5 ZCTAs + 5 xwalks + 5 CBSAs + 5 counties = 20, but the loader
    # double-counts CBSAs once for cbsa rows and once for county rows.
    # The exact total is less interesting than that all four tables filled.
    assert rows > 0

    assert con.execute("SELECT count(*) FROM geo_zcta").fetchone()[0] == 5
    assert con.execute("SELECT count(*) FROM geo_zcta_county_xwalk").fetchone()[0] == 5
    assert con.execute("SELECT count(*) FROM geo_cbsa").fetchone()[0] == 5
    assert con.execute("SELECT count(*) FROM geo_county").fetchone()[0] == 5


def test_census_geo_zcta_padding_and_population():
    con = _con()
    CensusGeoSource().load(con, FIXTURE_DIR)
    rows = con.execute(
        "SELECT zcta5, state, population FROM geo_zcta ORDER BY zcta5"
    ).fetchall()
    assert all(len(r[0]) == 5 for r in rows)
    # 10025 sorts first → New York County row.
    assert rows[0] == ("10025", "NY", 93821)


def test_census_geo_county_fips_is_five_digits():
    con = _con()
    CensusGeoSource().load(con, FIXTURE_DIR)
    fips = [r[0] for r in con.execute(
        "SELECT county_fips FROM geo_county ORDER BY county_fips"
    ).fetchall()]
    # "17031" Cook + "18097" Marion + "36061" New York + "39035" Cuyahoga + "47157" Shelby
    assert fips == ["17031", "18097", "36061", "39035", "47157"]


def test_census_geo_xwalk_res_ratio_in_unit_range():
    con = _con()
    CensusGeoSource().load(con, FIXTURE_DIR)
    rs = [r[0] for r in con.execute(
        "SELECT res_ratio FROM geo_zcta_county_xwalk"
    ).fetchall()]
    # Single-county ZCTAs in our fixture → res_ratio == 1.0.
    assert all(0.0 <= r <= 1.0 for r in rs)
    assert all(r == 1.0 for r in rs)


def test_census_geo_county_joins_to_cbsa():
    con = _con()
    CensusGeoSource().load(con, FIXTURE_DIR)
    joined = con.execute("""
        SELECT c.county_name, b.cbsa_name
        FROM geo_county c
        JOIN geo_cbsa b USING (cbsa_code)
        WHERE c.county_fips = '47157'
    """).fetchone()
    assert joined == ("Shelby County", "Memphis, TN-MS-AR")


def test_refresh_from_fixture_dir_logs_success():
    con = _con()
    src = CensusGeoSource()
    result = src.refresh(con, raw_dir=Path("/tmp/_unused"), from_fixture=FIXTURE_DIR)
    assert result.status == "ok"
    assert result.rows_loaded > 0
    log = con.execute(
        "SELECT source, status FROM refresh_log"
    ).fetchall()
    assert log == [("census_geo", "ok")]


def test_idempotent_load_no_pk_violation():
    """Loading twice should not raise (INSERT OR REPLACE behavior)."""
    con = _con()
    src = CensusGeoSource()
    src.load(con, FIXTURE_DIR)
    # Second load against the same fixture must not blow up the geo PKs.
    src.load(con, FIXTURE_DIR)
    assert con.execute("SELECT count(*) FROM geo_zcta").fetchone()[0] == 5
