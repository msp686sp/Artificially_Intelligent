from pathlib import Path

import duckdb

from rental.db import init_schema
from rental.sources import EvictionLabSource

FIXTURE = Path(__file__).parent / "fixtures" / "eviction_lab_sample.csv"


def _con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    init_schema(con)
    return con


def test_eviction_load_shape():
    con = _con()
    rows = EvictionLabSource().load(con, FIXTURE)
    # 8 rows, but 1 has both filings + rate as NaN -> dropped. Expect 7.
    assert rows == 7
    n = con.execute("SELECT count(*) FROM raw_eviction_lab").fetchone()[0]
    assert n == 7


def test_eviction_county_fips_zero_padded():
    con = _con()
    EvictionLabSource().load(con, FIXTURE)
    fips = {
        r[0]
        for r in con.execute("SELECT DISTINCT county_fips FROM raw_eviction_lab").fetchall()
    }
    assert all(len(f) == 5 for f in fips)
    assert "36061" in fips


def test_eviction_multi_year_per_county_preserved():
    con = _con()
    EvictionLabSource().load(con, FIXTURE)
    years = sorted(
        r[0]
        for r in con.execute(
            "SELECT DISTINCT year FROM raw_eviction_lab WHERE county_fips = '17031'"
        ).fetchall()
    )
    assert years == [2016, 2018]


def test_eviction_refresh_logs_success():
    con = _con()
    result = EvictionLabSource().refresh(con, raw_dir=Path("/tmp/_unused"), from_fixture=FIXTURE)
    assert result.status == "ok"
    assert result.rows_loaded == 7
