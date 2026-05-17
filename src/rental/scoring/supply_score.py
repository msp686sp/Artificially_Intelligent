"""SupplyScore: within-state z-score of the supply-side features.

The configured weights in ``config/weights.yaml`` are *negative* because
higher supply pressure (more permits per existing unit, higher MF share,
higher composite pressure) is bad for rent growth — so the linear
combination is::

    supply_score = Σ w_i · z_state(feature_i)

with all w_i ≤ 0, meaning higher pressure → lower SupplyScore. Z-scoring
happens within each state so the score is comparable across states with
very different absolute permit levels (e.g. Texas vs. Rhode Island).

Inputs: the ZCTA-grain supply features from ``rental.features``, joined
to ``geo_zcta`` for the state code.

Outputs: a DataFrame with one row per zcta5 carrying every feature
column plus ``supply_score``. Rows that are missing any input feature
get NaN for that feature's z and contribute 0 to the sum (so a ZCTA
with partial coverage still gets a partial score rather than NULL).
"""

from __future__ import annotations

import duckdb
import pandas as pd

from rental.config import load_yaml
from rental.features import zcta_supply_features

# Mapping from the friendly config key → the feature column name.
_FEATURE_COLUMNS = {
    "permits_per_1000": "permits_per_1000_units_5yr_avg",
    "multifamily_share": "multifamily_share_permits",
    "supply_pressure_index": "supply_pressure_index",
}


def compute_supply_score(
    con: duckdb.DuckDBPyConnection,
    weights: dict | None = None,
) -> pd.DataFrame:
    """Compute the per-ZCTA SupplyScore.

    Parameters
    ----------
    con: open warehouse connection. ``raw_census_bps``, ``raw_acs_housing_stock``,
        ``geo_zcta``, and ``geo_zcta_county_xwalk`` must be populated.
    weights: optional override for the ``supply_score`` block from
        ``config/weights.yaml``. Mostly for tests.
    """
    weights = weights if weights is not None else _load_supply_weights()

    features = zcta_supply_features(con)
    if features.empty:
        return _empty_score_frame()

    # Attach state for within-state normalization.
    states = con.execute("SELECT zcta5, state FROM geo_zcta").df()
    df = features.merge(states, on="zcta5", how="left")

    for cfg_key, col in _FEATURE_COLUMNS.items():
        df[f"z_{cfg_key}"] = _state_zscore(df, col)

    # Linear combination with the configured (negative) weights.
    score = pd.Series(0.0, index=df.index)
    for cfg_key in _FEATURE_COLUMNS:
        w = float(weights.get(cfg_key, 0.0))
        z = df[f"z_{cfg_key}"].astype(float).fillna(0.0)
        score = score + w * z
    df["supply_score"] = score

    return df.sort_values("supply_score", ascending=False).reset_index(drop=True)


def _load_supply_weights() -> dict:
    weights_yaml = load_yaml("weights.yaml") or {}
    block = weights_yaml.get("supply_score") or {}
    if not block:
        # Fall back to the documented defaults so the function is usable
        # even before an operator edits weights.yaml.
        return {
            "permits_per_1000": -0.5,
            "multifamily_share": -0.3,
            "supply_pressure_index": -0.2,
        }
    return block


def _state_zscore(df: pd.DataFrame, col: str) -> pd.Series:
    """Z-score ``col`` within each state. Returns NaN where the state
    has <2 non-null observations of the column."""
    if col not in df.columns:
        return pd.Series([float("nan")] * len(df), index=df.index)
    values = pd.to_numeric(df[col], errors="coerce")
    out = pd.Series([float("nan")] * len(df), index=df.index, dtype=float)
    for state, idx in df.groupby("state").groups.items():
        if state is None or pd.isna(state):
            continue
        sub = values.loc[idx]
        valid = sub.dropna()
        if len(valid) < 2:
            continue
        mu = valid.mean()
        sigma = valid.std()
        if sigma == 0 or pd.isna(sigma):
            continue
        out.loc[idx] = (sub - mu) / sigma
    return out


def _empty_score_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "zcta5",
            "permits_per_1000_units_5yr_avg",
            "multifamily_share_permits",
            "supply_pressure_index",
            "is_interpolated",
            "state",
            "z_permits_per_1000",
            "z_multifamily_share",
            "z_supply_pressure_index",
            "supply_score",
        ]
    )
