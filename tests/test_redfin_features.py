"""Tests for the Redfin-derived feature pipeline.

Covers:
- trailing 3mo means with full, sparse, and single-observation windows
- YoY DOM delta when both endpoints exist, and NaN when they don't
- YoY inventory % change with sign and magnitude checks
- zip codes flow through as 5-char strings with leading zeros preserved
"""

from pathlib import Path

import duckdb
import pandas as pd

from rental.db import init_schema
from rental.features import redfin_features
from rental.sources import RedfinMarketSource

FIXTURE = Path(__file__).parent / "fixtures" / "redfin_market_sample.tsv"


def _loaded_con():
    con = duckdb.connect(":memory:")
    init_schema(con)
    RedfinMarketSource().load(con, FIXTURE)
    return con


def _row(df: pd.DataFrame, zcta5: str) -> pd.Series:
    matches = df[df["zcta5"] == zcta5]
    assert len(matches) == 1, f"expected one row for {zcta5}, got {len(matches)}"
    return matches.iloc[0]


def test_features_returns_one_row_per_zip():
    con = _loaded_con()
    df = redfin_features(con)
    n_zips = con.execute("SELECT COUNT(DISTINCT zcta5) FROM raw_redfin_market").fetchone()[0]
    assert len(df) == n_zips
    assert df["zcta5"].is_unique


def test_features_empty_warehouse_returns_empty_frame():
    con = duckdb.connect(":memory:")
    init_schema(con)
    df = redfin_features(con)
    assert df.empty
    assert list(df.columns) == [
        "zcta5",
        "latest_period_begin",
        "dom_3mo_avg",
        "dom_yoy_delta",
        "sale_to_list_3mo_avg",
        "inventory_yoy_change",
    ]


def test_dom_3mo_avg_full_window():
    df = redfin_features(_loaded_con())
    # 10025 latest is 2024-03-01; window is Jan/Feb/Mar 2024 → DOM 55, 49, 44.
    assert _row(df, "10025")["dom_3mo_avg"] == (55 + 49 + 44) / 3
    # 60614 latest is 2024-06-01; window is Apr/May/Jun 2024 → DOM 28, 26, 25.
    assert _row(df, "60614")["dom_3mo_avg"] == (28 + 26 + 25) / 3


def test_dom_3mo_avg_with_sparse_window_uses_available_obs():
    """44102 is missing 2024-05; the trailing window for latest=2024-06 keeps
    April and June and averages those two."""
    df = redfin_features(_loaded_con())
    assert _row(df, "44102")["dom_3mo_avg"] == (22 + 24) / 2


def test_dom_3mo_avg_single_observation_returns_nan():
    """99501 has exactly one month of data — not enough for a 3mo mean."""
    df = redfin_features(_loaded_con())
    val = _row(df, "99501")["dom_3mo_avg"]
    assert pd.isna(val)


def test_sale_to_list_3mo_avg():
    df = redfin_features(_loaded_con())
    # 30312: Apr/May/Jun 2024 → 0.980 + 0.983 + 0.985 averaged.
    expected = (0.980 + 0.983 + 0.985) / 3
    assert abs(_row(df, "30312")["sale_to_list_3mo_avg"] - expected) < 1e-9


def test_dom_yoy_delta_positive_signals_softening():
    """46220 DOM rose 18 → 26 between Jun 2023 and Jun 2024 — softening market."""
    df = redfin_features(_loaded_con())
    assert _row(df, "46220")["dom_yoy_delta"] == 26 - 18


def test_dom_yoy_delta_negative_signals_tightening():
    """10025 DOM fell 51 → 44 between Mar 2023 and Mar 2024 — tightening."""
    df = redfin_features(_loaded_con())
    assert _row(df, "10025")["dom_yoy_delta"] == 44 - 51


def test_dom_yoy_delta_nan_when_prior_year_missing():
    """60614 only has 2024 data — there is no Jun 2023 to anchor the YoY."""
    df = redfin_features(_loaded_con())
    assert pd.isna(_row(df, "60614")["dom_yoy_delta"])


def test_inventory_yoy_change_is_fractional():
    """46220 inventory 88 → 102 in Jun 2023→2024."""
    df = redfin_features(_loaded_con())
    expected = (102 - 88) / 88
    assert abs(_row(df, "46220")["inventory_yoy_change"] - expected) < 1e-9


def test_inventory_yoy_change_nan_when_short_history():
    df = redfin_features(_loaded_con())
    assert pd.isna(_row(df, "60614")["inventory_yoy_change"])
    assert pd.isna(_row(df, "99501")["inventory_yoy_change"])


def test_features_preserve_zip_code_padding():
    df = redfin_features(_loaded_con())
    assert "07030" in set(df["zcta5"])
    assert all(len(z) == 5 for z in df["zcta5"])


def test_features_use_latest_snapshot_only():
    """If a newer snapshot lands, the older one must not pollute the panel."""
    con = _loaded_con()
    # Pretend an older, stale snapshot exists alongside today's data.
    con.execute("""
        INSERT INTO raw_redfin_market
        SELECT zcta5, period_begin, period_end, 999.0, 0.5,
               1.0, 1.0, 1.0, 1.0, DATE '1999-01-01'
        FROM raw_redfin_market
        WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM raw_redfin_market)
    """)
    df = redfin_features(con)
    # If the stale snapshot leaked, the 10025 DOM avg would be 999.
    assert _row(df, "10025")["dom_3mo_avg"] == (55 + 49 + 44) / 3
