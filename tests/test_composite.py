from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from rental.db import init_schema
from rental.scoring import init_composite_views
from rental.scoring.composite import (
    compute_market_score,
    load_market_weights,
)

FIXTURE = Path(__file__).parent / "fixtures" / "zip_scores_stub.csv"


def _stub_scores() -> pd.DataFrame:
    return pd.read_csv(FIXTURE, dtype={"zcta5": str})


def test_load_market_weights_matches_yaml():
    w = load_market_weights("config/weights.yaml")
    assert w["yield_score"] == pytest.approx(0.25)
    assert w["demand_score"] == pytest.approx(0.30)
    assert w["supply_score"] == pytest.approx(0.20)
    assert w["operability_score"] == pytest.approx(0.20)
    assert w["risk_score"] == pytest.approx(-0.05)


def test_compute_market_score_matches_hand_computation():
    scores = _stub_scores()
    out = compute_market_score(scores=scores)
    weights = load_market_weights("config/weights.yaml")

    # Hand-recompute composite for one row (Memphis 38104).
    memphis = scores.loc[scores["zcta5"] == "38104"].iloc[0]
    expected = (
        weights["yield_score"] * memphis["yield_score"]
        + weights["demand_score"] * memphis["demand_score"]
        + weights["supply_score"] * memphis["supply_score"]
        + weights["operability_score"] * memphis["operability_score"]
        + weights["risk_score"] * memphis["risk_score"]
    )
    row = out.loc[out["zcta5"] == "38104"].iloc[0]
    assert row["market_score"] == pytest.approx(expected, rel=1e-9)


def test_compute_market_score_is_sorted_descending():
    out = compute_market_score(scores=_stub_scores())
    ms = out["market_score"].to_numpy()
    assert np.all(np.diff(ms) <= 0), "market_score must be descending"


def test_compute_market_score_returns_contract_columns():
    out = compute_market_score(scores=_stub_scores())
    for col in ("zcta5", "state", "metro", "market_score"):
        assert col in out.columns


def test_partial_subscores_do_not_crash():
    # Only yield + demand present; others missing. Composite uses
    # available sub-scores weighted by their config weights.
    df = pd.DataFrame({
        "zcta5": ["10001", "10002"],
        "state": ["NY", "NY"],
        "yield_score": [1.0, -1.0],
        "demand_score": [0.5, 0.5],
    })
    out = compute_market_score(scores=df)
    assert len(out) == 2
    weights = load_market_weights("config/weights.yaml")
    expected = weights["yield_score"] * 1.0 + weights["demand_score"] * 0.5
    assert out.iloc[0]["market_score"] == pytest.approx(expected)


def test_all_nan_subscores_drops_row():
    df = pd.DataFrame({
        "zcta5": ["10001", "10002"],
        "state": ["NY", "NY"],
        "yield_score": [1.0, np.nan],
        "demand_score": [0.5, np.nan],
        "supply_score": [np.nan, np.nan],
        "operability_score": [np.nan, np.nan],
        "risk_score": [np.nan, np.nan],
    })
    out = compute_market_score(scores=df)
    assert list(out["zcta5"]) == ["10001"]


def test_empty_scores_returns_empty_frame():
    out = compute_market_score(scores=pd.DataFrame())
    assert out.empty
    assert "market_score" in out.columns


def test_compute_market_score_reads_from_zip_scores_view():
    # End-to-end through DuckDB: insert stub rows, then read via the view.
    con = duckdb.connect(":memory:")
    init_schema(con)
    init_composite_views(con)
    scores = _stub_scores().copy()
    scores["snapshot_date"] = pd.Timestamp("2026-01-01").date()
    con.register("_stub", scores)
    con.execute("INSERT INTO zip_scores SELECT * FROM _stub")
    out = compute_market_score(con)
    assert len(out) == 5
    assert "market_score" in out.columns
    # Sorted desc.
    ms = out["market_score"].to_numpy()
    assert np.all(np.diff(ms) <= 0)


def test_compute_market_score_handles_missing_table():
    # Fresh in-memory DB, no schema applied: should NOT raise.
    con = duckdb.connect(":memory:")
    out = compute_market_score(con)
    assert out.empty
