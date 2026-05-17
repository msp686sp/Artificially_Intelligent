"""YieldScore: weighted within-state robust z-score of yield features.

Inputs (DataFrame columns expected):
  - zcta5, state                 (keys)
  - gross_yield                  (or `gross_yield_monthly_pct` — auto-aliased)
  - effective_tax_rate           (optional, applied as -z)
  - insurance_rate               (optional, applied as -z)

Weights come from config/weights.yaml under the `yield_score:` key:

    yield_score:
      gross_yield: 0.50
      effective_tax_rate: 0.30   # neg z (higher tax = lower score)
      insurance_rate: 0.20       # neg z (higher premium = lower score)

Normalization is **within-state** to remove regional level effects
(California is structurally lower-yield than Ohio; we want to rank
within each state's universe). For robustness against the heavy-tailed
distributions typical of price/rent data we use **median + MAD** instead
of mean + stdev. Constant `1.4826` scales MAD to be a consistent
estimator of σ under normality.

Missing features (tax/insurance) are handled gracefully: their weight
is removed from the weighted sum and a warning is logged. This lets
the orchestrator integrate Yield half output before other agents land
their feature columns.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import yaml

from rental.config import load_yaml

log = logging.getLogger(__name__)

# Maps the config key → (dataframe column it reads, sign to apply to z).
# Negative sign means "higher raw value is worse" (we negate the z so
# the contribution is in the same direction as the others).
_FEATURE_SIGN: dict[str, int] = {
    "gross_yield": +1,
    "effective_tax_rate": -1,
    "insurance_rate": -1,
}

_GROSS_YIELD_ALIASES = ("gross_yield", "gross_yield_monthly_pct")


def _robust_z_within_state(s: pd.Series, state: pd.Series) -> pd.Series:
    """Within-state median/MAD z-score. Returns 0.0 where MAD is zero
    (single-zip states, or all-equal columns) to keep weighted sums
    finite without blowing up to NaN."""
    out = pd.Series(0.0, index=s.index, dtype=float)
    for _st, idx in s.groupby(state).groups.items():
        x = s.loc[idx].astype(float)
        med = x.median()
        mad = (x - med).abs().median()
        if mad == 0 or pd.isna(mad):
            out.loc[idx] = 0.0
        else:
            out.loc[idx] = (x - med) / (1.4826 * mad)
    return out


def yield_score(
    features: pd.DataFrame,
    weights_path: Path | None = None,
) -> pd.DataFrame:
    """Compute YieldScore per zcta5.

    Returns a DataFrame with columns: zcta5, state, yield_score, plus the
    component z-scores that contributed (prefixed `z_`) for transparency.
    """
    if "zcta5" not in features.columns:
        raise ValueError("features must include a 'zcta5' column")
    if "state" not in features.columns:
        raise ValueError("features must include a 'state' column (for within-state z)")

    # Alias gross_yield_monthly_pct → gross_yield so the weights key matches.
    df = features.copy()
    if "gross_yield" not in df.columns:
        for alias in _GROSS_YIELD_ALIASES:
            if alias in df.columns:
                df["gross_yield"] = df[alias]
                break

    if weights_path is not None:
        weights_cfg = yaml.safe_load(Path(weights_path).read_text())
    else:
        weights_cfg = load_yaml("weights.yaml")
    weights = (weights_cfg or {}).get("yield_score", {}) or {}

    contributions: dict[str, pd.Series] = {}
    used_weight_total = 0.0
    for feature_key, weight in weights.items():
        if feature_key not in df.columns:
            log.warning(
                "yield_score: feature %r missing from input; "
                "skipping its weight (%.2f) and renormalizing.",
                feature_key, weight,
            )
            continue
        sign = _FEATURE_SIGN.get(feature_key, +1)
        z = _robust_z_within_state(df[feature_key], df["state"])
        contributions[f"z_{feature_key}"] = sign * z
        used_weight_total += weight

    if used_weight_total == 0:
        raise ValueError(
            "yield_score: no input features matched any configured weights; "
            "cannot compute a score."
        )

    # Build the weighted sum, normalizing by the total of *used* weights so
    # missing features don't silently shrink the score.
    score = pd.Series(0.0, index=df.index, dtype=float)
    for feature_key, weight in weights.items():
        if feature_key not in df.columns:
            continue
        score = score + (weight / used_weight_total) * contributions[f"z_{feature_key}"]

    out = pd.DataFrame({
        "zcta5": df["zcta5"].values,
        "state": df["state"].values,
        "yield_score": score.values,
    })
    for col, series in contributions.items():
        out[col] = series.values
    return out
