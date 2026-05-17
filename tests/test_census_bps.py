"""Tests for the supply-side raw sources: Census BPS + ACS housing stock."""

from pathlib import Path

import duckdb

from rental.db import init_schema
from rental.sources import ACSHousingStockSource, CensusBPSSource


def test_supply_tables_exist_and_idempotent():
    """The Phase 3 raw tables must be created by init_schema and
    re-running init_schema must not error."""
    con = duckdb.connect(":memory:")
    init_schema(con)
    init_schema(con)  # idempotent
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    assert {"raw_census_bps", "raw_acs_housing_stock"} <= tables

BPS_FIXTURE = Path(__file__).parent / "fixtures" / "census_bps_sample.csv"
ACS_FIXTURE = Path(__file__).parent / "fixtures" / "acs_housing_stock_sample.json"


def _con():
    con = duckdb.connect(":memory:")
    init_schema(con)
    return con


def test_bps_load_shape():
    con = _con()
    rows = CensusBPSSource().load(con, BPS_FIXTURE)
    # 5 counties × 5 years
    assert rows == 25
    n = con.execute("SELECT count(*) FROM raw_census_bps").fetchone()[0]
    assert n == 25


def test_bps_fips_zero_padded():
    con = _con()
    CensusBPSSource().load(con, BPS_FIXTURE)
    fips = {r[0] for r in con.execute("SELECT DISTINCT county_fips FROM raw_census_bps").fetchall()}
    assert all(len(f) == 5 for f in fips)
    # Cuyahoga (Ohio) and Cook (Illinois) are present.
    assert "39035" in fips and "17031" in fips


def test_bps_totals_match_components():
    """total_units must equal sf + mf for every fixture row (sanity check on
    the parser, not a load-time invariant — but the fixture is curated to
    satisfy it and the assertion would catch silent type coercion bugs)."""
    con = _con()
    CensusBPSSource().load(con, BPS_FIXTURE)
    diffs = con.execute(
        """
        SELECT count(*) FROM raw_census_bps
        WHERE total_units <> single_family_units + multi_family_units
        """
    ).fetchone()[0]
    assert diffs == 0


def test_bps_refresh_from_fixture_logs_success():
    con = _con()
    result = CensusBPSSource().refresh(con, raw_dir=Path("/tmp/_unused"), from_fixture=BPS_FIXTURE)
    assert result.status == "ok"
    assert result.rows_loaded == 25
    log = con.execute(
        "SELECT source, rows_loaded, status FROM refresh_log WHERE source = 'census_bps'"
    ).fetchall()
    assert log == [("census_bps", 25, "ok")]


def test_acs_housing_stock_load_shape():
    con = _con()
    rows = ACSHousingStockSource(year=2022).load(con, ACS_FIXTURE)
    assert rows == 5
    n = con.execute("SELECT count(*) FROM raw_acs_housing_stock").fetchone()[0]
    assert n == 5
    years = {
        r[0]
        for r in con.execute("SELECT DISTINCT year FROM raw_acs_housing_stock").fetchall()
    }
    assert years == {2022}


def test_acs_housing_stock_fips_constructed_correctly():
    con = _con()
    ACSHousingStockSource(year=2022).load(con, ACS_FIXTURE)
    rows = con.execute(
        "SELECT county_fips, total_housing_units FROM raw_acs_housing_stock ORDER BY county_fips"
    ).fetchall()
    fips = [r[0] for r in rows]
    # Cuyahoga = 39035, Cook = 17031, New York = 36061, Marion IN = 18097, Shelby = 47157
    assert "39035" in fips and "17031" in fips and "36061" in fips
    # All fips are 5 characters.
    assert all(len(f) == 5 for f in fips)
    # Total housing units are positive integers.
    assert all(r[1] > 0 for r in rows)
