"""Composite score function for the Phase 6 backtest harness.

The backtest pipeline runs ``snapshot_features`` to produce a flat,
point-in-time features DataFrame and hands that DataFrame to an injected
``score_fn``. The production sub-score producers in ``rental.scoring`` are
all wired to read raw warehouse tables via a DuckDB connection — which is
the wrong seam for the backtest, since the whole point of the PIT
snapshot is that data has *already* been filtered to what was visible at
``as_of``.

This module bridges the gap with a small **adapter layer** that runs the
same z-score + weighted-sum math the production scorers use, but against
the flat features frame:

  - YieldScore uses the gross_yield / tax / insurance columns directly
    (those are present in the snapshot output).
  - Demand / Supply / Operability / Risk inputs aren't in the snapshot
    today, so their contribution degrades to NaN and is dropped from
    the weighted sum (mirroring the partial-coverage behavior the
    production ``compute_market_score`` already has).
  - State is required for within-state z-scoring. The snapshot frame
    doesn't carry it, so we look it up from ``raw_zillow_zhvi`` once per
    call (a cheap distinct-zip lookup). Falls back to a single ``_ALL_``
    group if the table is missing or the state is unknown for a zip.

Design choice: an adapter on the flat frame is dramatically simpler than
materializing the snapshot into a temp DuckDB and re-running the
producers — the producers reach back into half-a-dozen sibling tables we
don't have in PIT form. The weighted-sum-with-skipped-NaN logic is
already standard across the sub-score modules, so we replicate it once
here rather than refactor every producer to accept a frame.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from rental.scoring.composite import load_market_weights
from rental.scoring.normalize import zscore_within_state

# Weight keys live in the market_score block keyed by short names
# (yield/demand/supply/operability/risk). The composite reader maps them
# onto sub-score column names; we keep the short names internal here so
# the tuner's WeightVector drops straight in.
_DIMENSION_TO_COLUMN = {
    "yield": "yield_score",
    "demand": "demand_score",
    "supply": "supply_score",
    "operability": "operability_score",
    "risk": "risk_score",
}

# Per-dimension feature contributors. Each entry is (column, sign): sign
# is +1 when "higher feature → higher score" and -1 when "higher → worse".
# Only Yield has features present in the PIT snapshot today; the others
# are wired here for forward-compat so when sibling agents extend the
# PIT snapshot to carry their inputs, the scorer picks them up
# automatically without a code change.
_DIMENSION_FEATURES: dict[str, list[tuple[str, int]]] = {
    "yield": [
        ("gross_yield_monthly_pct", +1),
        ("effective_tax_rate", -1),
        ("insurance_rate", -1),
    ],
    "demand": [
        ("wage_weighted_job_cagr_5yr", +1),
        ("net_migration_per_1000", +1),
        ("hh_income_growth_5yr", +1),
    ],
    "supply": [
        ("permits_per_1000_units_5yr_avg", -1),
        ("multifamily_share_permits", -1),
        ("supply_pressure_index", -1),
    ],
    "operability": [
        ("effective_tax_rate", -1),
        ("insurance_rate_estimate", -1),
        ("eviction_filing_rate", -1),
    ],
    "risk": [
        ("climate_risk_score", -1),
        ("flood_risk", -1),
        ("wildfire_risk", -1),
        ("hurricane_risk", -1),
    ],
}

ScoreFn = Callable[[pd.DataFrame], pd.DataFrame]


def default_market_weights(
    weights_path: str | Path = "config/weights.yaml",
) -> dict[str, float]:
    """Return the ``market_score:`` block keyed by short dimension names.

    The on-disk composite reader keys by sub-score column name
    (``yield_score`` etc.); the backtest tuner keys by short name
    (``yield`` etc.). We translate once at the boundary so callers get
    the form they expect.
    """
    by_col = load_market_weights(weights_path)
    inverse = {col: short for short, col in _DIMENSION_TO_COLUMN.items()}
    return {inverse[col]: w for col, w in by_col.items() if col in inverse}


def _attach_state(
    features: pd.DataFrame,
    con: duckdb.DuckDBPyConnection | None,
) -> pd.DataFrame:
    """Attach a ``state`` column to ``features`` if it's missing.

    The PIT snapshot doesn't carry state today, so we look it up from
    ``raw_zillow_zhvi``. If the table is missing or every zip is
    unmapped, every row falls back to a single ``_ALL_`` group so the
    within-state z-score still has a peer set to compare against.
    """
    if "state" in features.columns and features["state"].notna().any():
        out = features.copy()
        out["state"] = out["state"].fillna("_ALL_")
        return out

    out = features.copy()
    states: pd.DataFrame | None = None
    if con is not None:
        try:
            states = con.execute(
                "SELECT DISTINCT zcta5, state FROM raw_zillow_zhvi"
            ).df()
        except duckdb.CatalogException:
            states = None
        except Exception:
            states = None

    if states is None or states.empty:
        out["state"] = "_ALL_"
        return out

    out = out.drop(columns=["state"], errors="ignore").merge(
        states.drop_duplicates(subset=["zcta5"]),
        on="zcta5",
        how="left",
    )
    out["state"] = out["state"].fillna("_ALL_")
    return out


def _dimension_score(
    df: pd.DataFrame,
    feature_specs: list[tuple[str, int]],
) -> pd.Series:
    """Compute one sub-score column: signed within-state z-scores,
    averaged across whichever features are actually present.

    Returns a Series aligned to ``df.index``. Rows with zero usable
    features get NaN; rows with at least one usable feature get the mean
    of the signed z-scores of their present features.
    """
    contributions: list[pd.Series] = []
    for col, sign in feature_specs:
        if col not in df.columns:
            continue
        values = pd.to_numeric(df[col], errors="coerce")
        if values.notna().sum() == 0:
            continue
        local = pd.DataFrame({col: values, "state": df["state"]}, index=df.index)
        z = zscore_within_state(local, col)
        contributions.append(sign * z)

    if not contributions:
        return pd.Series(np.nan, index=df.index, dtype=float)

    stacked = pd.concat(contributions, axis=1)
    # Row-mean over only the non-null contributions. Mirrors the
    # production composite_score behavior: a row with at least one
    # finite contribution gets a finite score, otherwise NaN.
    return stacked.mean(axis=1, skipna=True)


def _composite_from_features(
    features: pd.DataFrame,
    weights: dict[str, float],
    con: duckdb.DuckDBPyConnection | None = None,
) -> pd.DataFrame:
    """Heart of the scorer: compute the per-dimension sub-scores from
    the flat features frame and combine them with ``weights``.

    Always returns a DataFrame with columns ``zcta5`` and ``score``.
    NaN scores propagate (the backtest's merge with realized returns
    will drop them).
    """
    if features.empty or "zcta5" not in features.columns:
        return pd.DataFrame({
            "zcta5": pd.Series(dtype=str),
            "score": pd.Series(dtype=float),
        })

    df = _attach_state(features, con)

    sub_scores: dict[str, pd.Series] = {}
    for dim, specs in _DIMENSION_FEATURES.items():
        sub_scores[dim] = _dimension_score(df, specs)

    # Weighted sum across dimensions, skipping NaN contributions per row
    # so a thin warehouse (only ZHVI/ZORI loaded) still gets a usable
    # rank from the yield dimension alone.
    rows = pd.DataFrame(index=df.index)
    for dim, series in sub_scores.items():
        w = float(weights.get(dim, 0.0))
        if w == 0.0:
            continue
        rows[dim] = w * series

    if rows.empty or rows.shape[1] == 0:
        score = pd.Series(np.nan, index=df.index, dtype=float)
    else:
        # min_count=1: at least one dimension must be present for a
        # row's score to be finite; otherwise the composite is NaN.
        score = rows.sum(axis=1, skipna=True, min_count=1)

    out = pd.DataFrame({
        "zcta5": df["zcta5"].astype(str).values,
        "score": score.values,
    })
    return out


def composite_score_fn(
    features: pd.DataFrame,
    con: duckdb.DuckDBPyConnection | None = None,
    weights: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Backtest-compatible score function using the production composite.

    Returns a DataFrame with columns ``[zcta5, score]``.

    The optional ``con`` lets the scorer look up the state column when
    the PIT snapshot doesn't already carry it. Optional ``weights`` (keyed
    by short dimension name) override the on-disk config — primarily for
    tests; production callers should use :func:`composite_score_factory`
    instead, which closes over a weights dict explicitly.
    """
    if weights is None:
        try:
            weights = default_market_weights()
        except FileNotFoundError:
            weights = {}
    return _composite_from_features(features, weights, con=con)


def composite_score_factory(
    weights: dict[str, float],
    con: duckdb.DuckDBPyConnection | None = None,
) -> ScoreFn:
    """Return a score_fn closed over a specific weight vector.

    The tuner builds many score_fns (one per grid point) and feeds each
    through the backtest. This factory shape matches the existing
    ``ScoreFactory`` callable in ``rental.backtest.tune``.
    """
    fixed_weights = dict(weights)

    def fn(features: pd.DataFrame) -> pd.DataFrame:
        return _composite_from_features(features, fixed_weights, con=con)

    return fn
