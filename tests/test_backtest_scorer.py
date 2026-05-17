"""Tests for the backtest composite scorer.

Covers the seam between the PIT snapshot frame and the production
weighted-sum composite. The unit tests stay synthetic so they don't
hit the warehouse; one walk-forward integration test feeds the
existing synthetic ZHVI/ZORI fixtures through ``snapshot_features``
and asserts the scorer produces a non-empty ranking.
"""

from __future__ import annotations

import math
from datetime import date
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from rental.backtest.pit import snapshot_features
from rental.backtest.scorer import (
    composite_score_factory,
    composite_score_fn,
    default_market_weights,
)
from rental.db import init_schema

FIXTURE_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------
# Synthetic features
# ---------------------------------------------------------------------


def _features(n: int = 10, *, with_state: bool = True) -> pd.DataFrame:
    """Build a synthetic features frame in the shape `snapshot_features`
    returns. Yield rises monotonically with the zip index so we can
    assert score-vs-yield rank parity."""
    zips = [f"100{i:02d}" for i in range(n)]
    yields = np.linspace(0.5, 1.4, n)
    df = pd.DataFrame({
        "zcta5": zips,
        "zhvi": np.linspace(200_000, 110_000, n),
        "zori": np.linspace(1_000, 1_540, n),
        "gross_yield_monthly_pct": yields,
        "effective_tax_rate": np.full(n, 0.011),
        "insurance_rate": np.full(n, 0.0055),
        "as_of": [date(2018, 1, 1)] * n,
    })
    if with_state:
        df["state"] = "CA"
    return df


# ---------------------------------------------------------------------
# default_market_weights
# ---------------------------------------------------------------------


def test_default_market_weights_returns_short_keys():
    w = default_market_weights()
    # Must use short names (yield/demand/...) not column names
    # (yield_score/demand_score/...). The tuner closes over short names.
    assert "yield" in w
    assert "yield_score" not in w
    # config/weights.yaml ships with all five dimensions; some may be
    # null but the four non-null ones must be there.
    for short in ("yield", "demand", "supply", "operability"):
        assert short in w


# ---------------------------------------------------------------------
# composite_score_fn — shape + behavior
# ---------------------------------------------------------------------


def test_composite_score_fn_returns_expected_columns():
    out = composite_score_fn(_features())
    assert list(out.columns) == ["zcta5", "score"]
    assert len(out) == 10


def test_composite_score_fn_empty_input_returns_empty_frame():
    out = composite_score_fn(pd.DataFrame(columns=["zcta5"]))
    assert list(out.columns) == ["zcta5", "score"]
    assert out.empty


def test_composite_score_fn_monotonic_in_yield_when_only_yield_present():
    """When the only dimension with usable inputs is yield, the composite
    score must rank zips in the same order as gross_yield_monthly_pct."""
    features = _features(n=8)
    # Pin weights to yield-only so the assertion is crisp; other
    # dimensions have no features in the synthetic frame anyway.
    out = composite_score_fn(features, weights={"yield": 1.0})
    merged = out.merge(features[["zcta5", "gross_yield_monthly_pct"]], on="zcta5")
    sorted_by_yield = merged.sort_values("gross_yield_monthly_pct")["zcta5"].tolist()
    sorted_by_score = merged.sort_values("score")["zcta5"].tolist()
    assert sorted_by_score == sorted_by_yield


def test_composite_score_fn_finite_with_partial_features():
    """Drop tax/insurance columns and verify scores stay finite — the
    yield half should still produce a usable ranking from gross_yield
    alone, and the missing demand/supply/operability/risk inputs must
    not poison the composite."""
    features = _features(n=6).drop(
        columns=["effective_tax_rate", "insurance_rate"]
    )
    out = composite_score_fn(features, weights={"yield": 1.0})
    # Every row must have a finite score; the within-state z gives 0
    # only on degenerate groups, otherwise a real number.
    assert out["score"].notna().all()
    assert np.isfinite(out["score"]).all()


def test_composite_score_fn_handles_missing_state_column():
    """Without a state column or a warehouse to look up from, the scorer
    must fall back to a single ``_ALL_`` group rather than crash."""
    features = _features(n=5, with_state=False)
    out = composite_score_fn(features, weights={"yield": 1.0})
    assert len(out) == 5
    # All in one group still produces a usable within-state z (just a
    # plain z against the whole frame).
    assert out["score"].notna().all()


def test_composite_score_fn_attaches_state_from_warehouse():
    """When state is missing from features but raw_zillow_zhvi has the
    mapping, the scorer must join it on."""
    features = _features(n=4, with_state=False)
    con = duckdb.connect(":memory:")
    init_schema(con)
    rows = pd.DataFrame({
        "region_id": ["0"] * 4,
        "zcta5": features["zcta5"].tolist(),
        "state": ["CA"] * 4,
        "metro": ["Synthetic"] * 4,
        "county_name": ["Test"] * 4,
        "observation_date": [date(2020, 1, 1)] * 4,
        "zhvi": [200000.0] * 4,
        "snapshot_date": [date(2025, 1, 1)] * 4,
    })
    con.register("_z", rows)
    con.execute("INSERT INTO raw_zillow_zhvi SELECT * FROM _z")
    con.unregister("_z")

    out = composite_score_fn(features, con=con, weights={"yield": 1.0})
    assert len(out) == 4
    assert out["score"].notna().all()


def test_composite_score_fn_all_nan_when_no_features_match():
    """If no dimension has any usable features, the score must be NaN
    rather than 0 — 0 is a real rank-able value and would lie."""
    features = pd.DataFrame({
        "zcta5": ["10001", "10002", "10003"],
        # Only an irrelevant column; no dimension has a hit.
        "junk_column": [1.0, 2.0, 3.0],
        "state": ["CA"] * 3,
    })
    out = composite_score_fn(features, weights={"yield": 1.0})
    assert out["score"].isna().all()


# ---------------------------------------------------------------------
# composite_score_factory — weights actually move the rank
# ---------------------------------------------------------------------


def test_composite_score_factory_returns_callable():
    fn = composite_score_factory({"yield": 1.0})
    assert callable(fn)
    out = fn(_features())
    assert list(out.columns) == ["zcta5", "score"]


def test_composite_score_factory_weights_move_the_ranking():
    """Two weight vectors with opposite yield signs must produce
    opposite rankings on a yield-only synthetic frame."""
    features = _features(n=6)
    up = composite_score_factory({"yield": 1.0})(features)
    down = composite_score_factory({"yield": -1.0})(features)
    up_order = up.sort_values("score")["zcta5"].tolist()
    down_order = down.sort_values("score")["zcta5"].tolist()
    assert up_order == list(reversed(down_order))


def test_composite_score_factory_zero_weights_yield_nan_score():
    """All-zero weights mean no dimension contributes — score is NaN."""
    out = composite_score_factory({})(
        _features(n=4)
    )
    assert out["score"].isna().all()


# ---------------------------------------------------------------------
# Walk-forward integration: PIT snapshot -> scorer
# ---------------------------------------------------------------------


@pytest.fixture
def warehouse_with_synth_zillow():
    con = duckdb.connect(":memory:")
    init_schema(con)
    z = pd.read_csv(FIXTURE_DIR / "synthetic_zhvi_long.csv", dtype={"zcta5": str})
    z["observation_date"] = pd.to_datetime(z["observation_date"]).dt.date
    z["snapshot_date"] = date(2025, 1, 1)
    z["region_id"] = "0"
    z["state"] = "CA"
    z["metro"] = "Synthetic"
    z["county_name"] = "Test"
    con.register("_z", z)
    con.execute("""
        INSERT INTO raw_zillow_zhvi
        SELECT region_id, zcta5, state, metro, county_name,
               observation_date, zhvi, snapshot_date FROM _z
    """)
    con.unregister("_z")
    r = pd.read_csv(FIXTURE_DIR / "synthetic_zori_long.csv", dtype={"zcta5": str})
    r["observation_date"] = pd.to_datetime(r["observation_date"]).dt.date
    r["snapshot_date"] = date(2025, 1, 1)
    r["region_id"] = "0"
    r["state"] = "CA"
    r["metro"] = "Synthetic"
    r["county_name"] = "Test"
    con.register("_r", r)
    con.execute("""
        INSERT INTO raw_zillow_zori
        SELECT region_id, zcta5, state, metro, county_name,
               observation_date, zori, snapshot_date FROM _r
    """)
    con.unregister("_r")
    return con


def test_pit_snapshot_then_composite_score_produces_ranking(
    warehouse_with_synth_zillow,
):
    con = warehouse_with_synth_zillow
    features = snapshot_features(con, date(2014, 1, 31))
    assert not features.empty

    out = composite_score_fn(features, con=con, weights={"yield": 1.0})
    assert not out.empty
    assert {"zcta5", "score"} == set(out.columns)
    # Every zip in the snapshot must come back in the score frame.
    assert sorted(out["zcta5"].tolist()) == sorted(features["zcta5"].tolist())
    assert out["score"].notna().any()
    assert np.isfinite(out["score"].dropna()).all()


def test_walk_forward_scorer_yields_monotonic_ranking(
    warehouse_with_synth_zillow,
):
    """Synthetic fixture is constructed so realized return rank == yield
    rank. The composite (yield-only weights) must therefore rank zips
    in the same order as their gross_yield_monthly_pct value."""
    con = warehouse_with_synth_zillow
    features = snapshot_features(con, date(2014, 1, 31))
    out = composite_score_fn(features, con=con, weights={"yield": 1.0})
    merged = out.merge(features[["zcta5", "gross_yield_monthly_pct"]], on="zcta5")
    # Pearson rank-correlation == 1 when both orderings agree.
    rho = merged["score"].rank().corr(merged["gross_yield_monthly_pct"].rank())
    assert not math.isnan(rho)
    assert rho == pytest.approx(1.0)
