from pathlib import Path

import duckdb

from rental.db import init_schema
from rental.features import latest_zhvi_per_zip
from rental.sources import ZillowZHVISource

FIXTURE = Path(__file__).parent / "fixtures" / "zhvi_sample.csv"


def _con():
    con = duckdb.connect(":memory:")
    init_schema(con)
    return con


def test_zhvi_load_shape():
    con = _con()
    src = ZillowZHVISource()
    rows = src.load(con, FIXTURE)
    # 5 zips × 3 monthly columns = 15 rows
    assert rows == 15
    n = con.execute("SELECT count(*) FROM raw_zillow_zhvi").fetchone()[0]
    assert n == 15


def test_zhvi_zip_padding_preserved():
    con = _con()
    ZillowZHVISource().load(con, FIXTURE)
    zips = {r[0] for r in con.execute("SELECT DISTINCT zcta5 FROM raw_zillow_zhvi").fetchall()}
    # All zips must be 5 chars (the Cleveland 44102 case proves padding is non-destructive).
    assert all(len(z) == 5 for z in zips)
    assert "10025" in zips and "44102" in zips


def test_refresh_from_fixture_logs_success():
    con = _con()
    src = ZillowZHVISource()
    result = src.refresh(con, raw_dir=Path("/tmp/_unused"), from_fixture=FIXTURE)
    assert result.status == "ok"
    assert result.rows_loaded == 15
    log = con.execute("SELECT source, rows_loaded, status FROM refresh_log").fetchall()
    assert log == [("zillow_zhvi", 15, "ok")]


def test_latest_zhvi_per_zip_returns_one_row_per_zip_sorted():
    con = _con()
    ZillowZHVISource().load(con, FIXTURE)
    df = latest_zhvi_per_zip(con)
    assert len(df) == 5
    assert df["zhvi"].is_monotonic_decreasing
    assert df["observation_date"].nunique() == 1   # all rows from latest date
