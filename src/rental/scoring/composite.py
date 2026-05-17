"""Composite MarketScore.

Combines five sub-scores (yield, demand, supply, operability, risk) into
a single MarketScore via a weighted sum read from `config/weights.yaml`.

Design notes:

- Sub-scores are produced by sibling agents (Phases 1-5) that write to a
  shared `zip_scores` table (see `zip_view.sql`). This module reads from
  there in production.
- For tests and ad-hoc use, callers can inject a DataFrame directly via
  the `scores` argument — that's the cleanest seam, avoids coupling to
  DuckDB state, and means a missing sub-score table doesn't crash the
  pipeline.
- The risk weight is conventionally negative (risk is bad). We don't
  enforce that; we just trust the config.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import yaml

from rental.config import CONFIG_DIR

SUB_SCORE_COLS = ("yield_score", "demand_score", "supply_score",
                  "operability_score", "risk_score")

_WEIGHT_KEYS = {
    "yield": "yield_score",
    "demand": "demand_score",
    "supply": "supply_score",
    "operability": "operability_score",
    "risk": "risk_score",
}


def load_market_weights(weights_path: str | Path = "config/weights.yaml") -> dict[str, float]:
    """Read the `market_score:` block from weights.yaml.

    Returns a dict keyed by sub-score column name (e.g. 'yield_score').
    Any missing sub-score is treated as weight 0 (i.e. excluded from the
    composite), which lets us run with partial sub-score coverage during
    early phases.
    """
    path = Path(weights_path)
    if not path.is_absolute():
        # Resolve relative to repo root via the canonical CONFIG_DIR.
        candidate = CONFIG_DIR / path.name if path.parent == Path("config") else path
        path = candidate if candidate.exists() else path
    raw = yaml.safe_load(path.read_text()) or {}
    block = raw.get("market_score") or {}
    weights: dict[str, float] = {}
    for short, col in _WEIGHT_KEYS.items():
        if short in block and block[short] is not None:
            weights[col] = float(block[short])
    return weights


def compute_market_score(
    con: duckdb.DuckDBPyConnection | None = None,
    weights_path: str | Path = "config/weights.yaml",
    scores: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Compute composite MarketScore per zip.

    Parameters
    ----------
    con :
        DuckDB connection. Used only when `scores` is not supplied;
        reads from the `zip_scores` view.
    weights_path :
        Path to weights.yaml. Top-level `market_score:` block is read.
    scores :
        Optional pre-loaded sub-scores DataFrame (dependency injection
        for tests). Must include zcta5 + at least one sub-score column.

    Returns
    -------
    DataFrame with columns: zcta5, state, metro, county_name, market_score
    plus the underlying sub-score columns for traceability. Sorted by
    market_score descending; zips with no sub-scores at all are dropped.
    """
    weights = load_market_weights(weights_path)
    df = scores if scores is not None else _load_scores_from_db(con)
    if df is None or df.empty:
        return _empty_score_frame()

    df = df.copy()
    # Ensure identity columns exist; tolerate sub-score producers that
    # don't carry metadata.
    for col in ("state", "metro", "county_name"):
        if col not in df.columns:
            df[col] = pd.NA

    # Build the weighted sum, skipping NaNs per row (a missing sub-score
    # for one zip shouldn't sink that zip's composite to NaN). Each row's
    # composite is sum_i(weight_i * score_i) over the sub-scores that
    # are actually present and finite.
    if not weights:
        df["market_score"] = float("nan")
    else:
        present_cols = [c for c in weights if c in df.columns]
        if not present_cols:
            df["market_score"] = float("nan")
        else:
            contrib = pd.DataFrame(index=df.index)
            for col in present_cols:
                contrib[col] = df[col].astype(float) * weights[col]
            df["market_score"] = contrib.sum(axis=1, skipna=True, min_count=1)

    sub_cols_present = [c for c in SUB_SCORE_COLS if c in df.columns]
    # Drop zips with no sub-scores at all — composite isn't meaningful.
    if sub_cols_present:
        df = df.dropna(how="all", subset=sub_cols_present)

    keep_cols = ["zcta5", "state", "metro", "county_name", "market_score", *sub_cols_present]
    keep_cols = [c for c in keep_cols if c in df.columns]
    out = df[keep_cols].copy()
    out = out.sort_values("market_score", ascending=False, na_position="last")
    return out.reset_index(drop=True)


def _load_scores_from_db(con: duckdb.DuckDBPyConnection | None) -> pd.DataFrame | None:
    if con is None:
        return None
    try:
        return con.execute("SELECT * FROM zip_scores").df()
    except duckdb.CatalogException:
        # View/table not yet created by a sibling agent.
        return None


def _empty_score_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=["zcta5", "state", "metro", "county_name", "market_score",
                 *SUB_SCORE_COLS],
    )
