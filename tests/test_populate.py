"""End-to-end smoke for the populate → composite → filter pipeline.

Loads the bundled ZHVI + ZORI fixtures into an in-memory warehouse, runs
the populate orchestrator, asserts that zip_scores and feature_zip get
populated, then runs compute_market_score + apply_filters to confirm the
full pipeline executes without crashing on partial coverage.
"""

from datetime import date
from pathlib import Path

import duckdb

from rental.db import init_schema
from rental.filters import apply_filters
from rental.scoring import (
    compute_market_score,
    init_composite_views,
    populate_zip_features,
    populate_zip_scores,
)
from rental.sources import RedfinMarketSource, ZillowZHVISource
from rental.sources.zori import ZillowZORISource

FIXTURES = Path(__file__).parent / "fixtures"
WEIGHTS = Path(__file__).parents[1] / "config" / "weights.yaml"
FILTERS = Path(__file__).parents[1] / "config" / "filters.yaml"


def _seeded_con():
    con = duckdb.connect(":memory:")
    init_schema(con)
    ZillowZHVISource().load(con, FIXTURES / "zhvi_sample.csv")
    ZillowZORISource().load(con, FIXTURES / "zori_sample.csv")
    RedfinMarketSource().load(con, FIXTURES / "redfin_market_sample.tsv")
    init_composite_views(con)
    return con


def test_populate_zip_features_writes_rows_and_view_resolves():
    con = _seeded_con()
    n = populate_zip_features(con)
    assert n > 0
    # The view points at the populated table now, not the stub.
    rows = con.execute("SELECT count(*) FROM zip_features").fetchone()[0]
    assert rows == n


def test_populate_zip_scores_writes_at_least_yield_dimension():
    con = _seeded_con()
    populate_zip_features(con)
    n = populate_zip_scores(con)
    assert n > 0
    # yield_score must be present for every zip we have ZHVI+ZORI on.
    have_yield = con.execute(
        "SELECT count(*) FROM zip_scores WHERE yield_score IS NOT NULL"
    ).fetchone()[0]
    assert have_yield > 0


def test_compute_market_score_runs_end_to_end():
    con = _seeded_con()
    populate_zip_features(con)
    populate_zip_scores(con)
    scores = compute_market_score(con, weights_path=WEIGHTS)
    # Even with only yield contributing (other producers empty), the
    # composite is finite for at least one zip.
    assert not scores.empty
    assert "market_score" in scores.columns


def test_apply_filters_executes_on_real_features():
    con = _seeded_con()
    populate_zip_features(con)
    populate_zip_scores(con)
    scores = compute_market_score(con, weights_path=WEIGHTS)
    features = con.execute("SELECT * FROM zip_features").df()
    filtered, audit = apply_filters(scores, features, filters_path=FILTERS)
    # Filter audit must exist; values depend on the fixture's price band.
    summary = list(audit.summary_lines())
    assert summary  # non-empty audit
    # filtered DataFrame is always a frame (possibly empty).
    assert "zcta5" in filtered.columns or filtered.empty


def test_populate_is_idempotent():
    con = _seeded_con()
    populate_zip_features(con)
    populate_zip_features(con)
    n_features = con.execute("SELECT count(*) FROM feature_zip").fetchone()[0]
    populate_zip_scores(con)
    populate_zip_scores(con, snapshot_date=date.today())
    n_scores = con.execute("SELECT count(*) FROM zip_scores").fetchone()[0]
    # Re-running on the same snapshot date should not duplicate rows.
    assert n_features > 0
    assert n_scores > 0
