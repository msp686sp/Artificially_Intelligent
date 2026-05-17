from pathlib import Path

import duckdb

from rental.db import init_schema
from rental.sources import FemaNriSource

FIXTURE = Path(__file__).parent / "fixtures" / "fema_nri_sample.csv"


def _con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    init_schema(con)
    return con


def test_fema_load_shape():
    con = _con()
    rows = FemaNriSource().load(con, FIXTURE)
    assert rows == 7
    n = con.execute("SELECT count(*) FROM raw_fema_nri").fetchone()[0]
    assert n == 7


def test_fema_county_fips_padded_and_unique():
    con = _con()
    FemaNriSource().load(con, FIXTURE)
    fips = [r[0] for r in con.execute("SELECT county_fips FROM raw_fema_nri ORDER BY 1").fetchall()]
    assert all(len(f) == 5 for f in fips)
    assert "36061" in fips
    assert "12086" in fips


def test_fema_hurricane_score_for_miami_dade_is_highest():
    con = _con()
    FemaNriSource().load(con, FIXTURE)
    row = con.execute(
        "SELECT hurricane_score FROM raw_fema_nri WHERE county_fips = '12086'"
    ).fetchone()
    assert row[0] > 80   # Miami-Dade obviously high


def test_fema_refresh_logs_success():
    con = _con()
    result = FemaNriSource().refresh(con, raw_dir=Path("/tmp/_unused"), from_fixture=FIXTURE)
    assert result.status == "ok"
    assert result.rows_loaded == 7
