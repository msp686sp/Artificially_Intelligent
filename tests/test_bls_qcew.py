from pathlib import Path

import duckdb

from rental.db import init_schema
from rental.sources import BLSQcewSource

FIXTURE = Path(__file__).parent / "fixtures" / "qcew_sample.csv"


def _con():
    con = duckdb.connect(":memory:")
    init_schema(con)
    return con


def test_qcew_load_filters_national_aggregate():
    con = _con()
    src = BLSQcewSource()
    rows = src.load(con, FIXTURE)
    # The fixture has 61 data rows; the first row (area_fips=US000) is the
    # nation-wide aggregate and must be dropped at load time.
    assert rows == 60
    area_count = con.execute(
        "SELECT COUNT(DISTINCT area_fips) FROM raw_bls_qcew"
    ).fetchone()[0]
    assert area_count == 5  # 17031, 36061, 18097, 47157, 39035


def test_qcew_area_fips_padded_and_filtered_to_county_grain():
    con = _con()
    BLSQcewSource().load(con, FIXTURE)
    fips_lengths = {
        r[0]
        for r in con.execute(
            "SELECT DISTINCT length(area_fips) FROM raw_bls_qcew"
        ).fetchall()
    }
    assert fips_lengths == {5}


def test_qcew_quarter_zero_for_annual_rows():
    con = _con()
    BLSQcewSource().load(con, FIXTURE)
    # Every fixture row is annual (qtr="A"); load() must coerce to 0.
    quarters = {
        r[0] for r in con.execute("SELECT DISTINCT quarter FROM raw_bls_qcew").fetchall()
    }
    assert quarters == {0}


def test_qcew_refresh_from_fixture_logs_success():
    con = _con()
    src = BLSQcewSource()
    result = src.refresh(con, raw_dir=Path("/tmp/_unused"), from_fixture=FIXTURE)
    assert result.status == "ok"
    assert result.rows_loaded == 60
    log = con.execute(
        "SELECT source, rows_loaded, status FROM refresh_log"
    ).fetchall()
    assert log == [("bls_qcew", 60, "ok")]


def test_qcew_sector_breakdown_per_county():
    """Each county should have the 5 tenant-relevant sectors for each year."""
    con = _con()
    BLSQcewSource().load(con, FIXTURE)
    counts = con.execute(
        """
        SELECT area_fips, year, COUNT(DISTINCT industry_code) AS n_industries
        FROM raw_bls_qcew
        WHERE industry_code IN ('62', '61', '44', '72', '31')
        GROUP BY area_fips, year
        ORDER BY area_fips, year
        """
    ).fetchall()
    # 5 counties × 2 years × 5 sectors each.
    assert len(counts) == 10
    assert all(n == 5 for _, _, n in counts)
