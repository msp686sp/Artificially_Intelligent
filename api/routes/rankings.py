"""Rankings endpoint — paginated MarketScore table.

``GET /api/rankings`` is the bread-and-butter view: a sortable,
paginated, optionally filter-applied list of zips with their composite
+ sub-scores. The implementation hides three layers of compute behind
one stateless HTTP call:

1. ``populate_zip_features`` and ``populate_zip_scores`` are called
   first so the warehouse table is always consistent with the latest
   raw data. Both are idempotent (UPSERT keyed on snapshot_date), so
   the request is fast on a warm warehouse and self-healing on a cold
   one.

2. ``compute_market_score`` reads ``zip_scores`` and applies the
   weights in ``config/weights.yaml`` to produce the composite. We
   pull a DataFrame and operate on it in Python because (a) the
   weights live in YAML, not SQL, and (b) the optional filter step
   downstream is also pandas-native (see ``rental.filters``).

3. Optional ``filters_yaml`` body — when present, we hand it to
   ``rental.filters.apply_filters`` with the feature frame so the
   user can preview "what would my rankings look like with these
   filters?" without persisting any YAML edits.

Sorting / pagination happen last so the totals still reflect the
filter result (i.e. ``total`` is the count after filters, not before).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import duckdb
import yaml
from fastapi import APIRouter, Body, Depends, HTTPException, Query

from api.deps import get_con
from api.models.rankings import RankingRow, RankingsResponse
from rental.filters import apply_filters
from rental.scoring import (
    compute_market_score,
    populate_zip_features,
    populate_zip_scores,
)

router = APIRouter(prefix="/api", tags=["rankings"])

# Whitelisted sort columns. The frontend builds the sort dropdown from
# this list (via the OpenAPI schema), and we reject anything else to
# keep arbitrary SQL injection off the table.
_SORTABLE = {
    "zcta5",
    "market_score",
    "yield_score",
    "demand_score",
    "supply_score",
    "operability_score",
    "risk_score",
}

_SUB_SCORE_COLS = (
    "yield_score",
    "demand_score",
    "supply_score",
    "operability_score",
    "risk_score",
)


@router.get("/rankings", response_model=RankingsResponse)
def get_rankings(
    state: str | None = Query(None, description="Filter to a single 2-letter state"),
    metro: str | None = Query(None, description="Substring match against metro name"),
    min_score: float | None = Query(None, description="Inclusive minimum market_score"),
    max_score: float | None = Query(None, description="Inclusive maximum market_score"),
    sort: str = Query("market_score", description="Sort column"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=10_000),
    offset: int = Query(0, ge=0),
    filters_yaml: str | None = Body(
        None,
        embed=True,
        description=(
            "Optional raw YAML to apply as hard filters. When omitted, "
            "no filtering is applied (this is the safe default; the "
            "frontend's /filters page sends a non-empty body)."
        ),
    ),
    con: duckdb.DuckDBPyConnection = Depends(get_con),
) -> RankingsResponse:
    if sort not in _SORTABLE:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot sort by {sort!r}. Allowed: {sorted(_SORTABLE)}",
        )

    # Make the endpoint self-contained: refresh features + scores before
    # reading. Both are idempotent UPSERTs keyed on snapshot_date.
    populate_zip_features(con)
    populate_zip_scores(con)

    scores = compute_market_score(con)
    if scores.empty:
        return RankingsResponse(total=0, rows=[])

    # Apply legacy query-param filters (state / metro / score band).
    df = scores.copy()
    if state:
        df = df[df["state"] == state]
    if metro:
        df = df[df["metro"].astype(str).str.contains(metro, case=False, na=False)]
    if min_score is not None:
        df = df[df["market_score"].ge(min_score)]
    if max_score is not None:
        df = df[df["market_score"].le(max_score)]

    # Optional YAML filter overlay — sourced from the request body so
    # the frontend can ship a literal filters.yaml without URL-encoding.
    if filters_yaml:
        df = _apply_yaml_filters(con, df, filters_yaml)

    total = len(df)
    df = df.sort_values(
        sort,
        ascending=(order == "asc"),
        na_position="last",
    )
    page = df.iloc[offset : offset + limit]

    rows = [
        RankingRow(
            zcta5=str(r["zcta5"]),
            state=_str_or_none(r.get("state")),
            metro=_str_or_none(r.get("metro")),
            county_name=_str_or_none(r.get("county_name")),
            market_score=_float_or_none(r.get("market_score")),
            yield_score=_float_or_none(r.get("yield_score")),
            demand_score=_float_or_none(r.get("demand_score")),
            supply_score=_float_or_none(r.get("supply_score")),
            operability_score=_float_or_none(r.get("operability_score")),
            risk_score=_float_or_none(r.get("risk_score")),
        )
        for _, r in page.iterrows()
    ]
    return RankingsResponse(total=total, rows=rows)


def _apply_yaml_filters(
    con: duckdb.DuckDBPyConnection,
    df,
    filters_yaml: str,
):
    """Materialize ``filters_yaml`` to a tmpfile and run ``apply_filters``.

    ``rental.filters.apply_filters`` reads filters from disk by design
    (it lives close to the CLI which also reads YAML files). To keep
    that contract we write the body to a tempfile and pass the path.
    """
    try:
        parsed = yaml.safe_load(filters_yaml)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid filters YAML: {e}") from e
    if parsed is None:
        # Empty YAML = no filters. Nothing to do.
        return df
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=400,
            detail="filters_yaml must parse to a mapping",
        )

    try:
        features = con.execute("SELECT * FROM zip_features").df()
    except duckdb.CatalogException:
        features = None

    with tempfile.NamedTemporaryFile(
        "w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write(filters_yaml)
        tmp_path = Path(f.name)
    try:
        out, _audit = apply_filters(df, features_df=features, filters_path=tmp_path)
        return out
    finally:
        tmp_path.unlink(missing_ok=True)


def _float_or_none(v) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    # pandas/numpy NaN: not equal to itself.
    if f != f:
        return None
    return f


def _str_or_none(v) -> str | None:
    if v is None:
        return None
    s = str(v)
    if s in ("nan", "NaT", "None", "<NA>"):
        return None
    return s


__all__ = ["router", "_SORTABLE", "_SUB_SCORE_COLS"]
