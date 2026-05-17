from pathlib import Path

import duckdb

from rental.db import init_schema
from rental.sources import ACSDemographicsSource

FIXTURE = Path(__file__).parent / "fixtures" / "acs_sample.json"


def _con():
    con = duckdb.connect(":memory:")
    init_schema(con)
    return con


def test_acs_load_shape():
    con = _con()
    rows = ACSDemographicsSource().load(con, FIXTURE)
    assert rows == 7  # 7 ZCTAs in the fixture
    n = con.execute("SELECT count(*) FROM raw_acs_demographics").fetchone()[0]
    assert n == 7


def test_acs_zcta_padding_preserved():
    con = _con()
    ACSDemographicsSource().load(con, FIXTURE)
    zips = {
        r[0]
        for r in con.execute(
            "SELECT DISTINCT zcta5 FROM raw_acs_demographics"
        ).fetchall()
    }
    assert all(len(z) == 5 for z in zips)
    assert "10025" in zips and "44102" in zips


def test_acs_na_sentinel_coerced_to_null():
    """Census -666666666 sentinel must become NULL, not -666666666."""
    con = _con()
    ACSDemographicsSource().load(con, FIXTURE)
    row = con.execute(
        "SELECT median_household_income FROM raw_acs_demographics WHERE zcta5 = '59001'"
    ).fetchone()
    assert row[0] is None


def test_acs_year_carried_from_payload():
    con = _con()
    ACSDemographicsSource().load(con, FIXTURE)
    years = {
        r[0]
        for r in con.execute(
            "SELECT DISTINCT year FROM raw_acs_demographics"
        ).fetchall()
    }
    assert years == {2022}


def test_acs_refresh_from_fixture_logs_success():
    con = _con()
    result = ACSDemographicsSource().refresh(
        con, raw_dir=Path("/tmp/_unused"), from_fixture=FIXTURE
    )
    assert result.status == "ok"
    assert result.rows_loaded == 7
