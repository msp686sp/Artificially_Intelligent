"""Tests for the Redfin Data Center zip-code market tracker source.

The fixture is a small uncompressed TSV (~10 zips × up to ~6 months) that
exercises the canonical "Zip Code: NNNNN" region format plus the
leading-zero zip edge case Redfin's int columns would otherwise eat.
"""

from pathlib import Path

import duckdb

from rental.db import init_schema
from rental.sources import REGISTRY, RedfinMarketSource
from rental.sources.redfin import _extract_zcta5

FIXTURE = Path(__file__).parent / "fixtures" / "redfin_market_sample.tsv"


def _con():
    con = duckdb.connect(":memory:")
    init_schema(con)
    return con


def test_registry_includes_redfin():
    assert "redfin_market" in REGISTRY
    assert REGISTRY["redfin_market"] is RedfinMarketSource


def test_extract_zcta5_handles_redfin_format():
    assert _extract_zcta5("Zip Code: 10025") == "10025"
    assert _extract_zcta5("Zip Code:10025") == "10025"
    assert _extract_zcta5(" Zip Code: 10025 ") == "10025"


def test_extract_zcta5_pads_leading_zero_zips():
    # Redfin would have returned this as int 7030 — we must restore the pad.
    assert _extract_zcta5("Zip Code: 7030") == "07030"
    assert _extract_zcta5("7030") == "07030"
    assert _extract_zcta5(7030) == "07030"


def test_extract_zcta5_rejects_garbage():
    assert _extract_zcta5(None) is None
    assert _extract_zcta5("") is None
    assert _extract_zcta5("Zip Code: ") is None


def test_redfin_load_populates_table():
    con = _con()
    rows = RedfinMarketSource().load(con, FIXTURE)
    # All fixture rows have non-null period_begin/period_end and a valid zip.
    assert rows > 0
    n = con.execute("SELECT count(*) FROM raw_redfin_market").fetchone()[0]
    assert n == rows


def test_redfin_zip_codes_are_zero_padded_five_char_strings():
    con = _con()
    RedfinMarketSource().load(con, FIXTURE)
    zips = {r[0] for r in con.execute("SELECT DISTINCT zcta5 FROM raw_redfin_market").fetchall()}
    assert all(isinstance(z, str) and len(z) == 5 for z in zips)
    # The leading-zero NJ zip survives the round-trip.
    assert "07030" in zips
    # And a normal NYC zip is still there.
    assert "10025" in zips


def test_redfin_refresh_from_fixture_logs_success():
    con = _con()
    result = RedfinMarketSource().refresh(
        con, raw_dir=Path("/tmp/_unused_redfin"), from_fixture=FIXTURE
    )
    assert result.status == "ok"
    assert result.rows_loaded > 0
    log = con.execute("SELECT source, status FROM refresh_log").fetchall()
    assert ("redfin_market", "ok") in log


def test_redfin_load_is_idempotent():
    """Re-running load on the same fixture must not duplicate rows."""
    con = _con()
    src = RedfinMarketSource()
    src.load(con, FIXTURE)
    first = con.execute("SELECT count(*) FROM raw_redfin_market").fetchone()[0]
    src.load(con, FIXTURE)
    second = con.execute("SELECT count(*) FROM raw_redfin_market").fetchone()[0]
    assert first == second


def test_redfin_load_preserves_numeric_columns():
    con = _con()
    RedfinMarketSource().load(con, FIXTURE)
    row = con.execute("""
        SELECT median_dom, median_sale_to_list, inventory,
               new_listings, median_sale_price, homes_sold
        FROM raw_redfin_market
        WHERE zcta5 = '10025' AND period_begin = DATE '2024-03-01'
    """).fetchone()
    assert row is not None
    median_dom, s2l, inv, new_listings, price, homes_sold = row
    assert median_dom == 44
    assert abs(s2l - 0.990) < 1e-9
    assert inv == 160
    assert new_listings == 32
    assert price == 1515000
    assert homes_sold == 28
