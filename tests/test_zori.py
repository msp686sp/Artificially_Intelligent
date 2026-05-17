from pathlib import Path

import duckdb

from rental.db import init_schema
from rental.sources import ZillowZORISource

FIXTURE = Path(__file__).parent / "fixtures" / "zori_sample.csv"


def _con():
    con = duckdb.connect(":memory:")
    init_schema(con)
    return con


def test_zori_load_shape():
    con = _con()
    src = ZillowZORISource()
    rows = src.load(con, FIXTURE)
    # 5 zips × 4 monthly columns = 20 rows
    assert rows == 20
    n = con.execute("SELECT count(*) FROM raw_zillow_zori").fetchone()[0]
    assert n == 20


def test_zori_zip_padding_preserved():
    con = _con()
    ZillowZORISource().load(con, FIXTURE)
    zips = {r[0] for r in con.execute(
        "SELECT DISTINCT zcta5 FROM raw_zillow_zori"
    ).fetchall()}
    # 44102 verifies pad is non-destructive on a leading-non-zero zip.
    assert all(len(z) == 5 for z in zips)
    assert "10025" in zips and "44102" in zips


def test_refresh_from_fixture_logs_success():
    con = _con()
    src = ZillowZORISource()
    result = src.refresh(con, raw_dir=Path("/tmp/_unused"), from_fixture=FIXTURE)
    assert result.status == "ok"
    assert result.rows_loaded == 20
    log = con.execute(
        "SELECT source, rows_loaded, status FROM refresh_log"
    ).fetchall()
    assert log == [("zillow_zori", 20, "ok")]


def test_zori_observation_date_parsing():
    con = _con()
    ZillowZORISource().load(con, FIXTURE)
    dates = sorted({r[0].isoformat() for r in con.execute(
        "SELECT DISTINCT observation_date FROM raw_zillow_zori"
    ).fetchall()})
    assert dates == ["2019-02-28", "2023-12-31", "2024-01-31", "2024-02-29"]
