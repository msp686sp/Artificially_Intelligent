"""OperabilityScore — within-state z-score, weighted sum.

For each zip we z-score three operability features *within state* (so that
a Tennessee zip is compared against other Tennessee zips, not against
California), then weighted-sum them. Higher score = easier to operate.

Default weights (overridable via ``config/weights.yaml``):
  - effective_tax_rate:     -0.40   (lower tax → higher score)
  - insurance_rate_estimate:-0.30   (lower premium → higher score)
  - eviction_filing_rate:   -0.30   (lower filings → higher score)

Within-state z-scoring is the right choice for these features: property
tax and insurance averages are state-government driven, and benchmarking
a zip's relative pain against its state peer group is what an SFR operator
actually wants. If a state has <2 zips with the feature, the z-score for
that state is NaN by definition.
"""

from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

from rental.config import load_yaml
from rental.features.operability_features import operability_feature_frame

DEFAULT_WEIGHTS = {
    "effective_tax_rate": -0.40,
    "insurance_rate_estimate": -0.30,
    "eviction_filing_rate": -0.30,
}


def _within_state_zscore(df: pd.DataFrame, col: str, state_col: str = "state") -> pd.Series:
    """Z-score ``col`` within each ``state_col`` group. NaNs preserved."""
    grouped = df.groupby(state_col)[col]
    mean = grouped.transform("mean")
    # ddof=0 keeps the score defined for groups of size 1 (returns 0).
    std = grouped.transform(lambda s: s.std(ddof=0))
    z = (df[col] - mean) / std.replace(0, np.nan)
    return z


def _load_weights() -> dict[str, float]:
    try:
        cfg = load_yaml("weights.yaml") or {}
    except FileNotFoundError:
        return dict(DEFAULT_WEIGHTS)
    section = cfg.get("operability_score") or {}
    if not section:
        return dict(DEFAULT_WEIGHTS)
    # Null values are placeholders (e.g. Redfin features pending Phase 6 tuning);
    # skip them so the section can document upcoming features without breaking.
    return {k: float(v) for k, v in section.items() if v is not None}


def operability_score(
    con: duckdb.DuckDBPyConnection,
    weights: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Return zcta5 + per-feature z-scores + composite ``operability_score``."""
    w = weights or _load_weights()
    df = operability_feature_frame(con)

    if df.empty:
        return pd.DataFrame(
            columns=["zcta5", "state", *[f"z_{c}" for c in w], "operability_score"]
        )

    # If state column missing (e.g., empty insurance branch), patch from geo_zcta.
    if "state" not in df.columns or df["state"].isna().all():
        states = con.execute("SELECT zcta5, state FROM geo_zcta").df()
        df = df.drop(columns=["state"], errors="ignore").merge(states, on="zcta5", how="left")

    for col in w:
        if col not in df.columns:
            df[col] = np.nan
        df[f"z_{col}"] = _within_state_zscore(df, col)

    composite = pd.Series(0.0, index=df.index)
    any_present = pd.Series(False, index=df.index)
    for col, weight in w.items():
        z = df[f"z_{col}"]
        composite = composite.add(z.fillna(0) * weight, fill_value=0)
        any_present = any_present | z.notna()
    df["operability_score"] = composite.where(any_present, other=np.nan)

    keep = ["zcta5", "state", *list(w.keys()), *[f"z_{c}" for c in w], "operability_score"]
    keep = [c for c in keep if c in df.columns]
    return df[keep].sort_values("operability_score", ascending=False).reset_index(drop=True)
