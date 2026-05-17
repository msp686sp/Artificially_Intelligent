"""End-to-end backtest harness tests on synthetic data.

These exercise the full path: PIT snapshot -> score_fn -> realized
returns -> Spearman/quintiles -> walk-forward tune -> report render.
"""

from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from rental.backtest.assumptions import WeightGrid
from rental.backtest.report import _svg_line_chart, build_context, render_report
from rental.backtest.run import (
    BacktestResult,
    bootstrap_top_minus_bottom_ci,
    run_backtest,
    spearman_rho,
)
from rental.backtest.tune import tune_weights
from rental.db import init_schema

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    init_schema(c)
    c.execute("""
        CREATE TABLE IF NOT EXISTS raw_zillow_zori (
            zcta5 VARCHAR,
            observation_date DATE,
            zori DOUBLE,
            snapshot_date DATE,
            PRIMARY KEY (zcta5, observation_date, snapshot_date)
        )
    """)
    z = pd.read_csv(FIXTURE_DIR / "synthetic_zhvi_long.csv", dtype={"zcta5": str})
    z["observation_date"] = pd.to_datetime(z["observation_date"]).dt.date
    z["snapshot_date"] = date(2025, 1, 1)
    z["region_id"] = "0"
    z["state"] = "CA"
    z["metro"] = "Synthetic"
    z["county_name"] = "Test"
    c.register("_z", z)
    c.execute("""
        INSERT INTO raw_zillow_zhvi
        SELECT region_id, zcta5, state, metro, county_name,
               observation_date, zhvi, snapshot_date FROM _z
    """)
    c.unregister("_z")
    r = pd.read_csv(FIXTURE_DIR / "synthetic_zori_long.csv", dtype={"zcta5": str})
    r["observation_date"] = pd.to_datetime(r["observation_date"]).dt.date
    r["snapshot_date"] = date(2025, 1, 1)
    r["region_id"] = "0"
    r["state"] = "CA"
    r["metro"] = "Synthetic"
    r["county_name"] = "Test"
    c.register("_r", r)
    c.execute("""
        INSERT INTO raw_zillow_zori
        SELECT region_id, zcta5, state, metro, county_name,
               observation_date, zori, snapshot_date FROM _r
    """)
    c.unregister("_r")
    return c


def _yield_score_fn(features: pd.DataFrame) -> pd.DataFrame:
    out = features[["zcta5"]].copy()
    out["score"] = features["gross_yield_monthly_pct"].fillna(0.0)
    return out


def test_spearman_rho_basic():
    a = pd.Series([1, 2, 3, 4, 5])
    b = pd.Series([2, 4, 6, 8, 10])
    assert spearman_rho(a, b) == pytest.approx(1.0)
    c = pd.Series([5, 4, 3, 2, 1])
    assert spearman_rho(a, c) == pytest.approx(-1.0)


def test_spearman_rho_nan_when_too_few_points():
    import math as m
    assert m.isnan(spearman_rho(pd.Series([1, 2]), pd.Series([1, 2])))


def test_run_backtest_produces_results(con):
    dates = [date(2013, 1, 31), date(2014, 1, 31), date(2015, 1, 31)]
    result = run_backtest(con, dates, _yield_score_fn)
    assert isinstance(result, BacktestResult)
    assert len(result.snapshots) == 3
    for s in result.snapshots:
        assert s.n_zips == 5
        # Quintile means: 5 buckets but only 5 zips -> 1 per bucket
        assert len(s.quintile_means) == 5
        # By construction yield rank == realized return rank,
        # so Spearman must be 1.0.
        assert s.spearman == pytest.approx(1.0)


def test_run_backtest_baselines_present(con):
    dates = [date(2014, 1, 31)]
    result = run_backtest(con, dates, _yield_score_fn)
    s = result.snapshots[0]
    assert {"yield_only_spearman", "equal_weighted_spearman",
            "random_spearman"} <= set(s.baselines.keys())


def test_run_backtest_validates_score_fn_contract(con):
    def bad_fn(_features):
        return pd.DataFrame({"foo": [1]})
    with pytest.raises(ValueError, match="score_fn must return"):
        run_backtest(con, [date(2013, 1, 31)], bad_fn)


def test_walk_forward_train_validate_split(con):
    """The harness must score train and validate on disjoint snapshots."""
    seen_dates: list[date] = []

    def factory(_w):
        def fn(features: pd.DataFrame) -> pd.DataFrame:
            seen_dates.append(features["as_of"].iloc[0])
            out = features[["zcta5"]].copy()
            out["score"] = features["gross_yield_monthly_pct"].fillna(0.0)
            return out
        return fn

    # Tiny grid: 1×1×1×1×1 = 1 point so the test stays fast.
    grid = WeightGrid([0.25], [0.30], [0.20], [0.20], [-0.05])
    train = [date(2013, 1, 31), date(2014, 1, 31)]
    validate = [date(2018, 1, 31), date(2019, 1, 31)]
    tune = tune_weights(con, train, validate, factory, grid=grid)

    # Train snapshots seen once; validate snapshots seen once.
    train_set = set(train)
    validate_set = set(validate)
    train_visits = [d for d in seen_dates if d in train_set]
    validate_visits = [d for d in seen_dates if d in validate_set]
    assert sorted(train_visits) == sorted(train)
    assert sorted(validate_visits) == sorted(validate)
    # Disjointness on the captured visits:
    assert not (set(train_visits) & set(validate_visits))
    # Tune produced sensible numbers (rho ≈ 1 by construction)
    assert tune.train_mean_spearman == pytest.approx(1.0)
    assert tune.validate_mean_spearman == pytest.approx(1.0)


def test_bootstrap_ci_yields_three_floats(con):
    dates = [date(2014, 1, 31)]
    result = run_backtest(con, dates, _yield_score_fn)
    lo, mid, hi = bootstrap_top_minus_bottom_ci(
        result.snapshots[0].universe, n_bootstrap=100, seed=1,
    )
    assert lo <= mid <= hi


def test_svg_chart_renders_for_quintiles():
    svg = _svg_line_chart([0.1, 0.2, 0.3, 0.4, 0.5])
    assert "<svg" in svg
    assert "polyline" in svg
    # Empty input still emits an svg tag.
    assert "<svg" in _svg_line_chart([])


def test_report_context_marks_ready_when_significant(con):
    dates = [date(2013, 1, 31), date(2014, 1, 31), date(2015, 1, 31)]
    result = run_backtest(con, dates, _yield_score_fn)
    ctx = build_context(result)
    # With monotonic synthetic data every snapshot is significant.
    assert ctx.ready


def test_report_renders_to_disk(con, tmp_path):
    dates = [date(2013, 1, 31), date(2014, 1, 31)]
    result = run_backtest(con, dates, _yield_score_fn)
    out = render_report(result, tmp_path / "backtest_report.html")
    assert out.exists()
    html = out.read_text()
    assert "Rental Backtest Report" in html
    assert "<svg" in html
    # Either banner ('READY' or 'NOT READY') must appear.
    assert "READY" in html


def test_report_not_ready_banner_when_no_signal(con, tmp_path):
    """A noise score_fn must trip the NOT READY banner."""
    import random

    def random_fn(features: pd.DataFrame) -> pd.DataFrame:
        rng = random.Random(0)
        out = features[["zcta5"]].copy()
        out["score"] = [rng.random() for _ in range(len(features))]
        return out

    dates = [date(2013, 1, 31), date(2014, 1, 31), date(2015, 1, 31)]
    # Inject a score that is deliberately anti-correlated with realized return,
    # so the top-minus-bottom is negative on every snapshot.
    def anti_fn(features: pd.DataFrame) -> pd.DataFrame:
        out = features[["zcta5"]].copy()
        # Lower yield -> higher score = anti rank
        out["score"] = -features["gross_yield_monthly_pct"].fillna(0.0)
        return out
    result = run_backtest(con, dates, anti_fn)
    ctx = build_context(result)
    assert not ctx.ready

    out = render_report(result, tmp_path / "r.html")
    assert "NOT READY" in out.read_text()
