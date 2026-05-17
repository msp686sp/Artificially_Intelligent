"""Zip detail + zip compare endpoints.

``GET /api/zips/{zcta5}`` returns the full bundle that the
``/rankings/:zcta5`` page renders: identity, sub-scores + z-scores,
raw features, ZHVI/ZORI/Redfin time series, and the filter-status
matrix. ``GET /api/zips/compare`` aggregates the bundle for up to N
zips and emits a diff helper.

Design notes:

- The endpoint must not 500 on an empty warehouse. A zip with no
  Redfin data still returns a valid detail bundle with
  ``redfin: []``. A zip the warehouse has never heard of returns
  404 — that's still an error, but a typed one.

- Z-scores are computed on the fly from the feature frame so we
  never have to materialize a second "zip_features_with_z" table.
  Within-state z is the right comparison cohort per
  ``rental.scoring.normalize``.

- Filter status comes from running each enabled filter individually
  and recording its pass/skip decision. That's what the
  ``/rankings/:zcta5`` Filter Status card displays.
"""

from __future__ import annotations

import math
from typing import Any

import duckdb
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_con
from api.models.zips import (
    FeatureDiff,
    FilterStatus,
    RedfinPoint,
    ZHVIPoint,
    ZipCompareResponse,
    ZipDetail,
    ZipIdentity,
    ZipScores,
    ZORIPoint,
)
from rental.filters import load_filter_config
from rental.scoring import (
    compute_market_score,
    populate_zip_features,
    populate_zip_scores,
)
from rental.scoring.normalize import zscore_within_state

router = APIRouter(prefix="/zips", tags=["zips"])

# Columns from feature_zip / zip_features we expose under "features"
# in the detail bundle. Keeping this explicit means we don't leak
# bookkeeping columns (snapshot_date, primary keys) to the GUI.
_FEATURE_COLS = (
    "median_home_price",
    "latest_zori",
    "gross_yield_monthly_pct",
    "rent_growth_5yr_cagr",
    "zori_coverage_months",
    "population_cagr_10yr",
    "rent_controlled",
    "high_climate_risk",
)


@router.get("/compare", response_model=ZipCompareResponse)
def compare_zips(
    zcta5s: str = Query(..., description="Comma-separated zip list (e.g. 10025,46220)"),
    con: duckdb.DuckDBPyConnection = Depends(get_con),
) -> ZipCompareResponse:
    """Compare-page payload.

    Returns one detail bundle per requested zip plus a flat ``diffs``
    list, one entry per numeric feature, mapping zip → value. Missing
    zips are returned with an empty detail bundle rather than failing
    the whole request — the compare page should still render the zips
    that *do* exist.
    """
    requested = [z.strip() for z in zcta5s.split(",") if z.strip()]
    if not requested:
        raise HTTPException(status_code=400, detail="zcta5s required")

    bundles: dict[str, ZipDetail] = {}
    for z in requested:
        try:
            bundles[z] = _build_detail(con, z)
        except HTTPException as e:
            if e.status_code == 404:
                bundles[z] = _empty_detail(z)
            else:
                raise

    diffs = _build_diffs(bundles)
    return ZipCompareResponse(zips=bundles, diffs=diffs)


@router.get("/{zcta5}", response_model=ZipDetail)
def get_zip_detail(
    zcta5: str,
    con: duckdb.DuckDBPyConnection = Depends(get_con),
) -> ZipDetail:
    return _build_detail(con, zcta5)


# ---------------------------------------------------------------------------
# Internal builders.
# ---------------------------------------------------------------------------


def _build_detail(con: duckdb.DuckDBPyConnection, zcta5: str) -> ZipDetail:
    """Assemble the full detail bundle for one zip."""
    # Self-heal: ensure features + scores are materialized.
    populate_zip_features(con)
    populate_zip_scores(con)

    scores_df = compute_market_score(con)
    row = scores_df[scores_df["zcta5"] == zcta5]
    if row.empty:
        # Even with no scores we may still have raw ZHVI/ZORI/Redfin for
        # the zip — surface those so the page still renders. But if the
        # zip is wholly unknown to every table, 404.
        if not _zip_known_anywhere(con, zcta5):
            raise HTTPException(status_code=404, detail=f"Unknown zip {zcta5}")

    identity = _build_identity(con, zcta5, scores_df)
    scores = _build_scores(row)
    features_df = _features_for(con, zcta5)
    z_scores = _z_scores_for(scores_df, zcta5)

    return ZipDetail(
        identity=identity,
        scores=scores,
        z_scores=z_scores,
        features=_features_to_dict(features_df),
        zhvi=_zhvi_series(con, zcta5),
        zori=_zori_series(con, zcta5),
        redfin=_redfin_series(con, zcta5),
        filters=_filter_status(con, zcta5, features_df),
    )


def _empty_detail(zcta5: str) -> ZipDetail:
    return ZipDetail(
        identity=ZipIdentity(zcta5=zcta5),
        scores=ZipScores(),
    )


def _zip_known_anywhere(con: duckdb.DuckDBPyConnection, zcta5: str) -> bool:
    for table in ("raw_zillow_zhvi", "raw_zillow_zori", "raw_redfin_market"):
        try:
            n = con.execute(
                f"SELECT count(*) FROM {table} WHERE zcta5 = ?", [zcta5]
            ).fetchone()[0]
        except duckdb.CatalogException:
            n = 0
        if n:
            return True
    return False


def _build_identity(
    con: duckdb.DuckDBPyConnection, zcta5: str, scores_df: pd.DataFrame
) -> ZipIdentity:
    """Pull identity columns from zip_scores if available, else ZHVI."""
    if not scores_df.empty:
        match = scores_df[scores_df["zcta5"] == zcta5]
        if not match.empty:
            r = match.iloc[0]
            return ZipIdentity(
                zcta5=zcta5,
                state=_str_or_none(r.get("state")),
                metro=_str_or_none(r.get("metro")),
                county_name=_str_or_none(r.get("county_name")),
            )
    try:
        ident = con.execute(
            """
            SELECT state, metro, county_name
            FROM raw_zillow_zhvi
            WHERE zcta5 = ?
            ORDER BY snapshot_date DESC, observation_date DESC
            LIMIT 1
            """,
            [zcta5],
        ).fetchone()
    except duckdb.CatalogException:
        ident = None
    if ident:
        return ZipIdentity(
            zcta5=zcta5,
            state=_str_or_none(ident[0]),
            metro=_str_or_none(ident[1]),
            county_name=_str_or_none(ident[2]),
        )
    return ZipIdentity(zcta5=zcta5)


def _build_scores(row: pd.DataFrame) -> ZipScores:
    if row.empty:
        return ZipScores()
    r = row.iloc[0]
    return ZipScores(
        market_score=_float_or_none(r.get("market_score")),
        yield_score=_float_or_none(r.get("yield_score")),
        demand_score=_float_or_none(r.get("demand_score")),
        supply_score=_float_or_none(r.get("supply_score")),
        operability_score=_float_or_none(r.get("operability_score")),
        risk_score=_float_or_none(r.get("risk_score")),
    )


def _z_scores_for(scores_df: pd.DataFrame, zcta5: str) -> dict[str, float | None]:
    """Within-state z-score for each sub-score, restricted to this zip."""
    out: dict[str, float | None] = {}
    if scores_df.empty or "state" not in scores_df.columns:
        return out
    sub_cols = [
        c
        for c in (
            "yield_score",
            "demand_score",
            "supply_score",
            "operability_score",
            "risk_score",
            "market_score",
        )
        if c in scores_df.columns
    ]
    for col in sub_cols:
        try:
            z = zscore_within_state(scores_df, col)
        except KeyError:
            continue
        # Align z back to the score frame to look up this zip.
        joined = scores_df[["zcta5"]].assign(z=z.values)
        match = joined[joined["zcta5"] == zcta5]
        if match.empty:
            out[col] = None
        else:
            out[col] = _float_or_none(match.iloc[0]["z"])
    return out


def _features_for(con: duckdb.DuckDBPyConnection, zcta5: str) -> pd.DataFrame:
    try:
        return con.execute(
            "SELECT * FROM zip_features WHERE zcta5 = ?", [zcta5]
        ).df()
    except duckdb.CatalogException:
        return pd.DataFrame()


def _features_to_dict(features_df: pd.DataFrame) -> dict[str, Any]:
    if features_df.empty:
        return {}
    r = features_df.iloc[0]
    out: dict[str, Any] = {}
    for col in _FEATURE_COLS:
        if col in features_df.columns:
            out[col] = _scalar_or_none(r.get(col))
    return out


def _zhvi_series(
    con: duckdb.DuckDBPyConnection, zcta5: str, since: str | None = None
) -> list[ZHVIPoint]:
    try:
        df = con.execute(
            """
            WITH snap AS (SELECT MAX(snapshot_date) AS s FROM raw_zillow_zhvi)
            SELECT observation_date AS date, zhvi AS value
            FROM raw_zillow_zhvi, snap
            WHERE zcta5 = ? AND snapshot_date = snap.s
            ORDER BY observation_date
            """,
            [zcta5],
        ).df()
    except duckdb.CatalogException:
        return []
    return [
        ZHVIPoint(date=r["date"], value=_float_or_none(r["value"]))
        for _, r in df.iterrows()
    ]


def _zori_series(
    con: duckdb.DuckDBPyConnection, zcta5: str
) -> list[ZORIPoint]:
    try:
        df = con.execute(
            """
            WITH snap AS (SELECT MAX(snapshot_date) AS s FROM raw_zillow_zori)
            SELECT observation_date AS date, zori AS value
            FROM raw_zillow_zori, snap
            WHERE zcta5 = ? AND snapshot_date = snap.s
            ORDER BY observation_date
            """,
            [zcta5],
        ).df()
    except duckdb.CatalogException:
        return []
    return [
        ZORIPoint(date=r["date"], value=_float_or_none(r["value"]))
        for _, r in df.iterrows()
    ]


def _redfin_series(
    con: duckdb.DuckDBPyConnection, zcta5: str
) -> list[RedfinPoint]:
    try:
        df = con.execute(
            """
            WITH snap AS (SELECT MAX(snapshot_date) AS s FROM raw_redfin_market)
            SELECT period_end, median_dom, median_sale_to_list, inventory
            FROM raw_redfin_market, snap
            WHERE zcta5 = ? AND snapshot_date = snap.s
            ORDER BY period_end
            """,
            [zcta5],
        ).df()
    except duckdb.CatalogException:
        return []
    return [
        RedfinPoint(
            period_end=r["period_end"],
            median_dom=_float_or_none(r.get("median_dom")),
            median_sale_to_list=_float_or_none(r.get("median_sale_to_list")),
            inventory=_float_or_none(r.get("inventory")),
        )
        for _, r in df.iterrows()
    ]


def _filter_status(
    con: duckdb.DuckDBPyConnection,
    zcta5: str,
    features_df: pd.DataFrame,
) -> list[FilterStatus]:
    """One row per filter in filters.yaml — pass / fail / skipped."""
    try:
        cfg = load_filter_config()
    except FileNotFoundError:
        return []

    out: list[FilterStatus] = []
    for name, spec in cfg.items():
        if not isinstance(spec, dict):
            out.append(FilterStatus(name=name, passes=False, skipped=True))
            continue
        if not spec.get("enabled"):
            out.append(
                FilterStatus(
                    name=name, passes=False, skipped=True, reason="disabled in config"
                )
            )
            continue
        passes, reason = _evaluate_filter(name, spec, features_df)
        if passes is None:
            out.append(
                FilterStatus(
                    name=name, passes=False, skipped=True, reason=reason
                )
            )
        else:
            out.append(
                FilterStatus(name=name, passes=passes, skipped=False, reason=reason)
            )
    return out


def _evaluate_filter(
    name: str, spec: dict, features_df: pd.DataFrame
) -> tuple[bool | None, str | None]:
    """Run one filter against a single-row features frame.

    Returns ``(passes, reason)``. ``passes=None`` indicates "skipped"
    (column missing or value NULL with no decidable answer).
    """
    if features_df.empty:
        return None, "no features for zip"
    r = features_df.iloc[0]

    column_for: dict[str, str] = {
        "median_home_price": "median_home_price",
        "zori_coverage": "zori_coverage_months",
        "gross_yield_monthly_pct": "gross_yield_monthly_pct",
        "exclude_rent_controlled": "rent_controlled",
        "exclude_high_climate_risk": "high_climate_risk",
        "exclude_shrinking_metros": "population_cagr_10yr",
    }
    col = column_for.get(name)
    if col is None or col not in features_df.columns:
        return None, f"feature {col} unavailable"
    val = r.get(col)
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None, f"{col} is NULL for zip"

    if name == "median_home_price":
        return _band_check(float(val), spec), f"value={val}"
    if name == "zori_coverage":
        min_m = spec.get("min_months", spec.get("min"))
        if min_m is None:
            return True, None
        return float(val) >= float(min_m), f"value={val} min={min_m}"
    if name == "gross_yield_monthly_pct":
        return _band_check(float(val), spec), f"value={val}"
    if name == "exclude_rent_controlled":
        return not bool(val), f"rent_controlled={val}"
    if name == "exclude_high_climate_risk":
        return not bool(val), f"high_climate_risk={val}"
    if name == "exclude_shrinking_metros":
        floor = spec.get("population_cagr_min")
        if floor is None:
            return True, None
        return float(val) >= float(floor), f"value={val} floor={floor}"
    return None, "unknown filter"


def _band_check(v: float, spec: dict) -> bool:
    lo = spec.get("min")
    hi = spec.get("max")
    if lo is not None and v < float(lo):
        return False
    if hi is not None and v > float(hi):
        return False
    return True


def _build_diffs(bundles: dict[str, ZipDetail]) -> list[FeatureDiff]:
    """One FeatureDiff per numeric feature seen in any bundle.

    Bool / string features are passed through as-is; the frontend
    decides whether to render them in the comparison grid.
    """
    if not bundles:
        return []

    # Feature universe = sub-scores + raw features that appear anywhere.
    feature_names: list[str] = [
        "market_score",
        "yield_score",
        "demand_score",
        "supply_score",
        "operability_score",
        "risk_score",
    ]
    for d in bundles.values():
        for k in d.features:
            if k not in feature_names:
                feature_names.append(k)

    diffs: list[FeatureDiff] = []
    for f in feature_names:
        values: dict[str, Any] = {}
        for z, d in bundles.items():
            if f in {
                "market_score",
                "yield_score",
                "demand_score",
                "supply_score",
                "operability_score",
                "risk_score",
            }:
                values[z] = getattr(d.scores, f)
            else:
                values[z] = d.features.get(f)
        diffs.append(FeatureDiff(feature=f, values=values))
    return diffs


# ---------------------------------------------------------------------------
# Tiny coercion helpers (shared with rankings.py-style modules).
# ---------------------------------------------------------------------------


def _float_or_none(v) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f


def _str_or_none(v) -> str | None:
    if v is None:
        return None
    s = str(v)
    if s in ("nan", "NaT", "None", "<NA>"):
        return None
    return s


def _scalar_or_none(v):
    """For feature dicts: keep bools/strings as themselves, NaN → None."""
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return _float_or_none(v)
    s = str(v)
    if s in ("nan", "NaT", "None", "<NA>"):
        return None
    return s
