"""RiskScore — climate + concentration. Higher hazard → lower score.

Phase 4 implements the climate half (FEMA NRI composite + hazard-specific
sub-scores). Employer-concentration (HHI) lands in Phase 5; we leave a
weighted slot for it but tolerate its absence today.

Default weights (overridable via ``config/weights.yaml``):
  - climate_risk_score:  -0.50   (national z-score)
  - flood_risk:          -0.15
  - wildfire_risk:       -0.15
  - hurricane_risk:      -0.20

We z-score *nationally* (not within state) because climate hazard is
intrinsically a national-comparison feature: a flood-prone Houston zip is
flood-prone whether or not the rest of Texas floods.
"""

from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

from rental.config import load_yaml
from rental.features.risk_features import climate_risk_features

DEFAULT_WEIGHTS = {
    "climate_risk_score": -0.50,
    "flood_risk": -0.15,
    "wildfire_risk": -0.15,
    "hurricane_risk": -0.20,
}


def _zscore(series: pd.Series) -> pd.Series:
    mean = series.mean(skipna=True)
    std = series.std(ddof=0, skipna=True)
    if pd.isna(std) or std == 0:
        return pd.Series(np.nan, index=series.index)
    return (series - mean) / std


def _load_weights() -> dict[str, float]:
    try:
        cfg = load_yaml("weights.yaml") or {}
    except FileNotFoundError:
        return dict(DEFAULT_WEIGHTS)
    section = cfg.get("risk_score") or {}
    if not section:
        return dict(DEFAULT_WEIGHTS)
    return {k: float(v) for k, v in section.items()}


def risk_score(
    con: duckdb.DuckDBPyConnection,
    weights: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Return zcta5 + per-feature z-scores + composite ``risk_score``."""
    w = weights or _load_weights()
    df = climate_risk_features(con)

    if df.empty:
        return pd.DataFrame(
            columns=["zcta5", *[f"z_{c}" for c in w], "risk_score"]
        )

    for col in w:
        if col not in df.columns:
            df[col] = np.nan
        df[f"z_{col}"] = _zscore(df[col])

    composite = pd.Series(0.0, index=df.index)
    any_present = pd.Series(False, index=df.index)
    for col, weight in w.items():
        z = df[f"z_{col}"]
        composite = composite.add(z.fillna(0) * weight, fill_value=0)
        any_present = any_present | z.notna()
    df["risk_score"] = composite.where(any_present, other=np.nan)

    keep = ["zcta5", *list(w.keys()), *[f"z_{c}" for c in w], "risk_score"]
    keep = [c for c in keep if c in df.columns]
    return df[keep].sort_values("risk_score", ascending=False).reset_index(drop=True)
