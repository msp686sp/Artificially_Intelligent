from pathlib import Path

import duckdb

from rental.db import init_schema
from rental.sources import CountyTaxRateSource

FIXTURE = Path(__file__).parent / "fixtures" / "county_tax_sample.json"


def _con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    init_schema(con)
    return con


def test_county_tax_load_filters_sentinels_and_nulls():
    con = _con()
    rows = CountyTaxRateSource().load(con, FIXTURE)
    # 7 input rows: 1 has null tax, 1 has -666666666 home value -> both dropped.
    assert rows == 5
    n = con.execute("SELECT count(*) FROM raw_county_tax_rate").fetchone()[0]
    assert n == 5


def test_county_tax_county_fips_is_state_plus_county():
    con = _con()
    CountyTaxRateSource().load(con, FIXTURE)
    fips = {r[0] for r in con.execute("SELECT county_fips FROM raw_county_tax_rate").fetchall()}
    # state 36 + county 061 -> 36061 (Manhattan).
    assert "36061" in fips
    # state 39 + county 035 -> 39035 (Cuyahoga, Cleveland).
    assert "39035" in fips
    # All 5 chars.
    assert all(len(f) == 5 for f in fips)


def test_county_tax_effective_rate_matches_division():
    con = _con()
    CountyTaxRateSource().load(con, FIXTURE)
    row = con.execute(
        "SELECT median_tax_paid, median_home_value, effective_rate "
        "FROM raw_county_tax_rate WHERE county_fips = '17031'"
    ).fetchone()
    tax, home, rate = row
    assert tax == 3100
    assert home == 340000
    assert abs(rate - 3100 / 340000) < 1e-9


def test_county_tax_refresh_logs_success():
    con = _con()
    result = CountyTaxRateSource().refresh(con, raw_dir=Path("/tmp/_unused"), from_fixture=FIXTURE)
    assert result.status == "ok"
    assert result.rows_loaded == 5
    log = con.execute("SELECT source, rows_loaded, status FROM refresh_log").fetchall()
    assert log == [("county_tax_rate", 5, "ok")]
