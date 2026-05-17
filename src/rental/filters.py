"""Hard-filter engine.

Drives `config/filters.yaml`. Each filter has `enabled: true/false`;
disabled filters are silently skipped so the rankings universe isn't
narrowed beyond the user's explicit non-negotiables (see plan.md).

Filters operate on a per-zip feature frame and return a boolean mask
PLUS a summary dict explaining how many rows each filter knocked out.
That summary is what powers the CLI's "filters applied" report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

from rental.config import CONFIG_DIR


@dataclass
class FiltersApplied:
    """Audit of a single hard-filter pass."""

    rows_in: int
    rows_out: int
    per_filter: dict[str, int] = field(default_factory=dict)  # name -> rows excluded
    skipped: list[str] = field(default_factory=list)          # name -> disabled or missing col

    def summary_lines(self) -> list[str]:
        out = [f"rows in: {self.rows_in:,}  rows out: {self.rows_out:,}"]
        for name, n in self.per_filter.items():
            out.append(f"  - {name}: excluded {n:,} rows")
        for name in self.skipped:
            out.append(f"  - {name}: skipped")
        return out


def load_filter_config(filters_path: str | Path = "config/filters.yaml") -> dict:
    path = Path(filters_path)
    if not path.is_absolute():
        candidate = CONFIG_DIR / path.name if path.parent == Path("config") else path
        path = candidate if candidate.exists() else path
    raw = yaml.safe_load(path.read_text()) or {}
    return raw.get("filters") or {}


def apply_filters(
    df: pd.DataFrame,
    features_df: pd.DataFrame | None = None,
    filters_path: str | Path = "config/filters.yaml",
) -> tuple[pd.DataFrame, FiltersApplied]:
    """Apply enabled hard filters from filters.yaml.

    Parameters
    ----------
    df :
        The score frame to filter (typically the output of
        `compute_market_score`). Must contain a `zcta5` column.
    features_df :
        Per-zip feature frame providing the columns the filters reference
        (median_home_price, zori_coverage_months, etc.). If None, falls
        back to looking those columns up on `df` itself.
    filters_path :
        Path to filters.yaml.

    Returns
    -------
    (filtered_df, FiltersApplied)
        A new DataFrame containing only rows that pass every enabled
        filter, and an audit object describing what was applied.
    """
    cfg = load_filter_config(filters_path)
    audit = FiltersApplied(rows_in=len(df), rows_out=len(df))

    if df.empty:
        return df.copy(), audit

    if features_df is not None and not features_df.empty and "zcta5" in features_df.columns:
        # Outer-merge feature columns onto the score frame so we can
        # evaluate filters in one pass. Existing columns on df win.
        feat = features_df.drop_duplicates(subset=["zcta5"], keep="last")
        cols_to_add = [c for c in feat.columns if c == "zcta5" or c not in df.columns]
        merged = df.merge(feat[cols_to_add], on="zcta5", how="left")
    else:
        merged = df.copy()

    mask = pd.Series(True, index=merged.index)

    for name, spec in cfg.items():
        if not isinstance(spec, dict) or not spec.get("enabled"):
            audit.skipped.append(name)
            continue
        result = _apply_one(name, spec, merged)
        if result is None:
            audit.skipped.append(name)
            continue
        # Count rows newly excluded by this filter (was True, now False).
        newly_excluded = int((mask & ~result).sum())
        audit.per_filter[name] = newly_excluded
        mask &= result

    out = merged.loc[mask, df.columns].reset_index(drop=True)
    audit.rows_out = len(out)
    return out, audit


# ---------------------------------------------------------------------------
# Individual filter implementations.
# Each returns a boolean Series (True = keep) over `frame.index`, or None
# if the filter can't be evaluated (e.g. required column missing).
# ---------------------------------------------------------------------------

def _apply_one(name: str, spec: dict, frame: pd.DataFrame) -> pd.Series | None:
    fn = _FILTERS.get(name)
    if fn is None:
        # Unknown filter name: treat as skipped rather than crashing —
        # the YAML is user-editable and we'd rather degrade gracefully.
        return None
    return fn(spec, frame)


def _band(spec: dict, frame: pd.DataFrame, col: str) -> pd.Series | None:
    if col not in frame.columns:
        return None
    series = frame[col]
    keep = pd.Series(True, index=frame.index)
    lo = spec.get("min")
    hi = spec.get("max")
    if lo is not None:
        keep &= series.ge(lo)
    if hi is not None:
        keep &= series.le(hi)
    # NaN comparisons return False with ge/le; that excludes rows missing
    # the feature entirely. For a hard non-negotiable like price band,
    # that's the right policy (we can't bet on what we can't see).
    return keep


def _filter_median_home_price(spec: dict, frame: pd.DataFrame) -> pd.Series | None:
    return _band(spec, frame, "median_home_price")


def _filter_zori_coverage(spec: dict, frame: pd.DataFrame) -> pd.Series | None:
    if "zori_coverage_months" not in frame.columns:
        return None
    min_months = spec.get("min_months", spec.get("min"))
    if min_months is None:
        return pd.Series(True, index=frame.index)
    cov = frame["zori_coverage_months"]
    # Thin-data zips (NaN coverage) get excluded — that's the whole
    # point of this filter.
    return cov.ge(min_months).fillna(False)


def _filter_gross_yield(spec: dict, frame: pd.DataFrame) -> pd.Series | None:
    return _band(spec, frame, "gross_yield_monthly_pct")


def _filter_exclude_rent_controlled(spec: dict, frame: pd.DataFrame) -> pd.Series | None:
    if "rent_controlled" not in frame.columns:
        return None
    rc = frame["rent_controlled"].fillna(False).astype(bool)
    return ~rc


def _filter_exclude_high_climate_risk(spec: dict, frame: pd.DataFrame) -> pd.Series | None:
    if "high_climate_risk" not in frame.columns:
        return None
    hcr = frame["high_climate_risk"].fillna(False).astype(bool)
    return ~hcr


def _filter_exclude_shrinking_metros(spec: dict, frame: pd.DataFrame) -> pd.Series | None:
    if "population_cagr_10yr" not in frame.columns:
        return None
    floor = spec.get("population_cagr_min")
    if floor is None:
        return pd.Series(True, index=frame.index)
    # Missing population CAGR is treated as failing the filter — same
    # rationale as the price band.
    return frame["population_cagr_10yr"].ge(floor).fillna(False)


_FILTERS = {
    "median_home_price": _filter_median_home_price,
    "zori_coverage": _filter_zori_coverage,
    "gross_yield_monthly_pct": _filter_gross_yield,
    "exclude_rent_controlled": _filter_exclude_rent_controlled,
    "exclude_high_climate_risk": _filter_exclude_high_climate_risk,
    "exclude_shrinking_metros": _filter_exclude_shrinking_metros,
}
