"""DemandScore — composite of jobs, migration, and household-income growth.

Normalization: robust within-state z-scores. For each state, the median
and median absolute deviation (MAD) of each feature are computed across
its ZCTAs, then each ZCTA's value is recentered as ``(x - median) / (1.4826 * MAD)``.
We use 1.4826 × MAD as the scale so that the result matches a Gaussian
standard deviation when the underlying distribution is normal.

Weights come from ``config/weights.yaml`` ``demand_score:`` block:
  wage_weighted_job_cagr: 0.40
  net_migration_per_1000: 0.35
  hh_income_growth:       0.25

ZCTAs missing all three features score NaN. Otherwise we use the
weighted sum of whichever features are present, rescaling the weights so
they sum to 1 across the available features (matches the YieldScore
pattern in Phase 1).
"""

from __future__ import annotations

from collections.abc import Iterable

import duckdb
import numpy as np
import pandas as pd

from rental.config import load_yaml
from rental.features.demand_features import demand_features

_FEATURE_TO_WEIGHT_KEY = {
    "wage_weighted_job_cagr_5yr": "wage_weighted_job_cagr",
    "net_migration_per_1000": "net_migration_per_1000",
    "hh_income_growth_5yr": "hh_income_growth",
}

_MAD_SCALE = 1.4826  # makes MAD a consistent estimator of σ under Gaussian


def _robust_z(values: pd.Series) -> pd.Series:
    """Median + MAD normalization, NaN-safe.

    If MAD is zero (constant column within a state), returns 0 for every
    non-null value rather than NaN — that way we treat "every zip is at
    the median" as neutral, not as missing.
    """
    v = pd.to_numeric(values, errors="coerce")
    med = v.median(skipna=True)
    mad = (v - med).abs().median(skipna=True)
    if pd.isna(med):
        return pd.Series(np.nan, index=values.index)
    if not mad or pd.isna(mad):
        return v.where(v.isna(), 0.0)
    return (v - med) / (_MAD_SCALE * mad)


def within_state_zscores(
    df: pd.DataFrame,
    feature_cols: Iterable[str],
    state_col: str = "state",
) -> pd.DataFrame:
    """Apply ``_robust_z`` group-wise by state to each feature column."""
    cols = list(feature_cols)
    out = df.copy()
    for col in cols:
        if col not in out.columns:
            out[col] = np.nan
            continue
        out[f"{col}_z"] = (
            out.groupby(state_col, group_keys=False)[col].apply(_robust_z)
        )
    return out


def _load_weights() -> dict[str, float]:
    cfg = load_yaml("weights.yaml") or {}
    block = cfg.get("demand_score") or {}
    return {k: float(v) for k, v in block.items()}


def demand_score(
    con: duckdb.DuckDBPyConnection,
    weights: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Compute DemandScore per ZCTA.

    Returns a frame with one row per ZCTA: zcta5, state, the three raw
    features, their within-state z-scores, and the composite
    ``demand_score`` column.
    """
    features = demand_features(con)
    if features.empty:
        return pd.DataFrame(
            columns=[
                "zcta5",
                "state",
                "wage_weighted_job_cagr_5yr",
                "net_migration_per_1000",
                "hh_income_growth_5yr",
                "demand_score",
            ]
        )

    # Attach the state for grouping. geo_zcta lives in another phase's
    # schema; if it's empty we fall back to a single global group.
    state_df = con.execute("SELECT zcta5, state FROM geo_zcta").df()
    if state_df.empty:
        features = features.assign(state="_ALL_")
    else:
        features = features.merge(state_df, on="zcta5", how="left")
        features["state"] = features["state"].fillna("_ALL_")

    feature_cols = list(_FEATURE_TO_WEIGHT_KEY)
    scored = within_state_zscores(features, feature_cols)

    w = dict(weights) if weights is not None else _load_weights()
    # Map config keys to feature columns; missing keys → 0.
    feature_weights = {
        col: float(w.get(_FEATURE_TO_WEIGHT_KEY[col], 0.0)) for col in feature_cols
    }

    def _row_score(row: pd.Series) -> float:
        num = 0.0
        denom = 0.0
        for col, weight in feature_weights.items():
            z = row.get(f"{col}_z")
            if z is None or pd.isna(z) or weight == 0:
                continue
            num += weight * z
            denom += weight
        if denom == 0:
            return float("nan")
        return num / denom

    scored["demand_score"] = scored.apply(_row_score, axis=1)
    return scored[
        [
            "zcta5",
            "state",
            *feature_cols,
            *[f"{c}_z" for c in feature_cols],
            "demand_score",
        ]
    ].sort_values("demand_score", ascending=False, na_position="last").reset_index(
        drop=True
    )
