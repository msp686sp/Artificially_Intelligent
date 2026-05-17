"""Pre-computed chart payloads for the rankings + zip pages.

Each endpoint returns data the frontend can hand straight to Recharts
without a transform step. Scatter is sampled to 2000 points so a
nationwide warehouse doesn't blow up the wire format; the user can
drill into specific zips via the SQL workbench when they need raw
density.
"""

from __future__ import annotations

from datetime import date

import duckdb
import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_con
from api.models.charts import (
    HistogramBin,
    RedfinSeriesPoint,
    ScatterPoint,
    ScatterResponse,
    ScoreDistributionResponse,
    TimeSeriesPoint,
)
from rental.scoring import (
    compute_market_score,
    populate_zip_features,
    populate_zip_scores,
)

router = APIRouter(prefix="/charts", tags=["charts"])

_VALID_SCORE_DIMS = {
    "market_score",
    "yield_score",
    "demand_score",
    "supply_score",
    "operability_score",
    "risk_score",
}

# Feature columns we know how to plot. Anything else gets a 400.
_VALID_FEATURE_DIMS = {
    "median_home_price",
    "latest_zori",
    "gross_yield_monthly_pct",
    "rent_growth_5yr_cagr",
    "zori_coverage_months",
}

_SCATTER_SAMPLE_CAP = 2000


@router.get("/score-distribution", response_model=ScoreDistributionResponse)
def score_distribution(
    dim: str = Query("market_score", description="Score column to histogram"),
    bins: int = Query(20, ge=2, le=200),
    con: duckdb.DuckDBPyConnection = Depends(get_con),
) -> ScoreDistributionResponse:
    if dim not in _VALID_SCORE_DIMS:
        raise HTTPException(
            status_code=400,
            detail=f"dim must be one of {sorted(_VALID_SCORE_DIMS)}",
        )
    populate_zip_features(con)
    populate_zip_scores(con)
    scores = compute_market_score(con)
    if scores.empty or dim not in scores.columns:
        return ScoreDistributionResponse(dim=dim, bins=[])
    series = scores[dim].dropna().astype(float)
    if series.empty:
        return ScoreDistributionResponse(dim=dim, bins=[])

    # ``numpy.histogram`` returns counts + edges; we zip them into the
    # explicit bin model the frontend expects.
    counts, edges = np.histogram(series.values, bins=bins)
    out_bins = [
        HistogramBin(
            bin_start=float(edges[i]),
            bin_end=float(edges[i + 1]),
            count=int(counts[i]),
        )
        for i in range(len(counts))
    ]
    return ScoreDistributionResponse(dim=dim, bins=out_bins)


@router.get("/feature-vs-score", response_model=ScatterResponse)
def feature_vs_score(
    feature: str = Query(..., description="Feature column on the X axis"),
    score: str = Query("market_score", description="Score column on the Y axis"),
    con: duckdb.DuckDBPyConnection = Depends(get_con),
) -> ScatterResponse:
    if feature not in _VALID_FEATURE_DIMS:
        raise HTTPException(
            status_code=400,
            detail=f"feature must be one of {sorted(_VALID_FEATURE_DIMS)}",
        )
    if score not in _VALID_SCORE_DIMS:
        raise HTTPException(
            status_code=400,
            detail=f"score must be one of {sorted(_VALID_SCORE_DIMS)}",
        )
    populate_zip_features(con)
    populate_zip_scores(con)
    scores = compute_market_score(con)
    if scores.empty:
        return ScatterResponse(feature=feature, score=score, points=[])
    try:
        feats = con.execute("SELECT * FROM zip_features").df()
    except duckdb.CatalogException:
        feats = pd.DataFrame()
    if feature not in feats.columns:
        return ScatterResponse(feature=feature, score=score, points=[])

    merged = scores[["zcta5", score]].merge(
        feats[["zcta5", feature]], on="zcta5", how="inner"
    )
    merged = merged.dropna(subset=[score, feature])
    if len(merged) > _SCATTER_SAMPLE_CAP:
        # Deterministic sample keyed on zcta5 so screenshot tests don't
        # flap. ``sample`` with a fixed random_state is fine here.
        merged = merged.sample(_SCATTER_SAMPLE_CAP, random_state=0)
    points = [
        ScatterPoint(
            zcta5=str(r["zcta5"]),
            x=float(r[feature]),
            y=float(r[score]),
        )
        for _, r in merged.iterrows()
    ]
    return ScatterResponse(feature=feature, score=score, points=points)


@router.get("/zhvi/{zcta5}", response_model=list[TimeSeriesPoint])
def zhvi_series(
    zcta5: str,
    since: date | None = Query(None, description="Inclusive earliest observation_date"),
    con: duckdb.DuckDBPyConnection = Depends(get_con),
) -> list[TimeSeriesPoint]:
    return _time_series(con, "raw_zillow_zhvi", "zhvi", zcta5, since)


@router.get("/zori/{zcta5}", response_model=list[TimeSeriesPoint])
def zori_series(
    zcta5: str,
    since: date | None = Query(None),
    con: duckdb.DuckDBPyConnection = Depends(get_con),
) -> list[TimeSeriesPoint]:
    return _time_series(con, "raw_zillow_zori", "zori", zcta5, since)


@router.get("/redfin/{zcta5}", response_model=list[RedfinSeriesPoint])
def redfin_series(
    zcta5: str,
    since: date | None = Query(None),
    con: duckdb.DuckDBPyConnection = Depends(get_con),
) -> list[RedfinSeriesPoint]:
    try:
        q = """
            WITH snap AS (SELECT MAX(snapshot_date) AS s FROM raw_redfin_market)
            SELECT period_end, median_dom, median_sale_to_list, inventory
            FROM raw_redfin_market, snap
            WHERE zcta5 = ? AND snapshot_date = snap.s
        """
        params: list = [zcta5]
        if since is not None:
            q += " AND period_end >= ?"
            params.append(since)
        q += " ORDER BY period_end"
        df = con.execute(q, params).df()
    except duckdb.CatalogException:
        return []
    return [
        RedfinSeriesPoint(
            period_end=r["period_end"],
            median_dom=_float_or_none(r.get("median_dom")),
            median_sale_to_list=_float_or_none(r.get("median_sale_to_list")),
            inventory=_float_or_none(r.get("inventory")),
        )
        for _, r in df.iterrows()
    ]


def _time_series(
    con: duckdb.DuckDBPyConnection,
    table: str,
    value_col: str,
    zcta5: str,
    since: date | None,
) -> list[TimeSeriesPoint]:
    """Shared ZHVI/ZORI fetch — they have the same shape."""
    try:
        q = f"""
            WITH snap AS (SELECT MAX(snapshot_date) AS s FROM {table})
            SELECT observation_date AS date, {value_col} AS value
            FROM {table}, snap
            WHERE zcta5 = ? AND snapshot_date = snap.s
        """
        params: list = [zcta5]
        if since is not None:
            q += " AND observation_date >= ?"
            params.append(since)
        q += " ORDER BY observation_date"
        df = con.execute(q, params).df()
    except duckdb.CatalogException:
        return []
    return [
        TimeSeriesPoint(date=r["date"], value=_float_or_none(r["value"]))
        for _, r in df.iterrows()
    ]


def _float_or_none(v) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:
        return None
    return f
