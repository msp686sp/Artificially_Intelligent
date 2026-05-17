"""Robust z-score normalization.

We use median + MAD (Median Absolute Deviation) rather than mean + stdev
because zip-level feature distributions (yields, vacancy, eviction rates)
are skewed and heavy-tailed; classic z-scores get pulled around by a
handful of extreme zips. MAD-z is the standard robust replacement.

The within-state variant lets us compare zips against their own state
distribution, which is the right peer set for a buyer making
single-state operational bets.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Scaling constant that makes MAD a consistent estimator of stdev
# under the normal distribution (≈ 1 / Phi^-1(0.75)).
_MAD_TO_SIGMA = 1.4826


def _robust_z(values: pd.Series) -> pd.Series:
    """Median + MAD z-score. Returns 0.0 where MAD is 0 (degenerate group)."""
    v = values.astype(float)
    finite = v.dropna()
    if finite.empty:
        return pd.Series(np.nan, index=v.index, dtype=float)
    med = float(finite.median())
    mad = float((finite - med).abs().median())
    if mad == 0.0:
        # All values identical (or single-member group): no spread to scale.
        # Return 0 for finite values, NaN for non-finite.
        out = pd.Series(0.0, index=v.index, dtype=float)
        out[v.isna()] = np.nan
        return out
    return (v - med) / (_MAD_TO_SIGMA * mad)


def zscore_within_state(
    df: pd.DataFrame,
    value_col: str,
    state_col: str = "state",
) -> pd.Series:
    """Robust z-score of `value_col`, computed within each state group.

    - Uses median + MAD (1.4826 × MAD ≈ stdev under normality).
    - States with a single zip, or zero MAD spread, return 0.0 for finite
      values and NaN for missing values (no informative ranking possible).
    - NaN inputs propagate as NaN outputs; they do not contribute to the
      median/MAD of the group.
    - Output is aligned to the input frame's index.
    """
    if value_col not in df.columns:
        raise KeyError(f"value_col {value_col!r} not in DataFrame")
    if state_col not in df.columns:
        raise KeyError(f"state_col {state_col!r} not in DataFrame")
    if df.empty:
        return pd.Series(dtype=float, name=f"{value_col}_z")

    grouped = df.groupby(state_col, dropna=False, group_keys=False)[value_col]
    out = grouped.apply(_robust_z)
    # groupby+apply can reorder; realign to df index to keep callers safe.
    out = out.reindex(df.index)
    out.name = f"{value_col}_z"
    return out
