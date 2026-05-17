"""End-to-end driver: run every sub-score producer and write the unified
result into the ``zip_scores`` table that the composite reader consumes.

Each sub-score producer has its own signature (some take a DataFrame of
features, others take a DuckDB connection). This module hides those
differences and exposes a single ``populate_zip_scores(con)`` entry point
plus a sibling ``populate_zip_features(con)`` for the filter pipeline.

Robust to missing data: any producer that returns an empty frame is
treated as "no contribution this run" rather than failing the pipeline.
"""

from __future__ import annotations

from datetime import date

import duckdb
import pandas as pd

from rental.features.yield_features import yield_features
from rental.scoring.demand_score import demand_score
from rental.scoring.operability_score import operability_score
from rental.scoring.risk_score import risk_score
from rental.scoring.supply_score import compute_supply_score
from rental.scoring.yield_score import yield_score

_SUBSCORE_COLS = (
    "yield_score",
    "demand_score",
    "supply_score",
    "operability_score",
    "risk_score",
)


def _slim(df: pd.DataFrame | None, col: str) -> pd.DataFrame:
    """Reduce a producer's output to (zcta5, <col>).

    Returns an empty 2-column frame when the producer ran on empty data.
    """
    if df is None or df.empty or "zcta5" not in df.columns or col not in df.columns:
        return pd.DataFrame({"zcta5": pd.Series(dtype=str), col: pd.Series(dtype=float)})
    return df[["zcta5", col]].drop_duplicates(subset=["zcta5"])


def _zip_identity(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Identity columns from the latest ZHVI snapshot."""
    try:
        return con.execute("""
            WITH snap AS (SELECT MAX(snapshot_date) AS s FROM raw_zillow_zhvi)
            SELECT DISTINCT z.zcta5, z.state, z.metro, z.county_name
            FROM raw_zillow_zhvi z, snap
            WHERE z.snapshot_date = snap.s
        """).df()
    except duckdb.CatalogException:
        return pd.DataFrame(columns=["zcta5", "state", "metro", "county_name"])


def populate_zip_scores(
    con: duckdb.DuckDBPyConnection,
    snapshot_date: date | None = None,
) -> int:
    """Run every sub-score producer and UPSERT the merged result into
    ``zip_scores``. Returns the number of zips written."""
    snap = snapshot_date or date.today()
    yf = yield_features(con)
    y = yield_score(yf) if not yf.empty and "state" in yf.columns else pd.DataFrame()

    producers = [
        (y, "yield_score"),
        (_safe_call(demand_score, con), "demand_score"),
        (_safe_call(compute_supply_score, con), "supply_score"),
        (_safe_call(operability_score, con), "operability_score"),
        (_safe_call(risk_score, con), "risk_score"),
    ]

    out: pd.DataFrame | None = None
    for df, col in producers:
        slim = _slim(df, col)
        out = slim if out is None else out.merge(slim, on="zcta5", how="outer")

    if out is None:
        out = pd.DataFrame(columns=["zcta5", *_SUBSCORE_COLS])

    ident = _zip_identity(con)
    out = out.merge(ident, on="zcta5", how="left")
    out["snapshot_date"] = snap
    # Ensure every contract column exists even when a producer returned nothing.
    for c in _SUBSCORE_COLS:
        if c not in out.columns:
            out[c] = float("nan")
    for c in ("state", "metro", "county_name"):
        if c not in out.columns:
            out[c] = None
    out = out.dropna(subset=["zcta5"])
    if out.empty:
        return 0

    con.register("_zs_stage", out)
    con.execute("""
        INSERT OR REPLACE INTO zip_scores
        SELECT zcta5, state, metro, county_name,
               yield_score, demand_score, supply_score,
               operability_score, risk_score, snapshot_date
        FROM _zs_stage
    """)
    con.unregister("_zs_stage")
    return len(out)


def populate_zip_features(
    con: duckdb.DuckDBPyConnection,
    snapshot_date: date | None = None,
) -> int:
    """Materialize the filter-facing features into ``zip_features_t``.

    The legacy stub ``zip_features`` view in zip_view.sql returns no rows.
    This function populates a real table and (re)defines the view over it
    so ``apply_filters`` has data to test against.
    """
    snap = snapshot_date or date.today()
    yf = yield_features(con)
    ident = _zip_identity(con)

    if not yf.empty:
        cols = [c for c in (
            "zcta5", "state", "latest_zhvi", "latest_zori",
            "gross_yield_monthly_pct", "rent_growth_5yr_cagr",
            "zori_coverage_months",
        ) if c in yf.columns]
        feat = yf[cols].copy()
        feat = feat.rename(columns={"latest_zhvi": "median_home_price"})
    else:
        feat = pd.DataFrame(columns=[
            "zcta5", "state", "median_home_price", "latest_zori",
            "gross_yield_monthly_pct", "rent_growth_5yr_cagr",
            "zori_coverage_months",
        ])

    # Merge metro/county for downstream display + the zip_scores join.
    feat = feat.merge(ident[["zcta5", "metro", "county_name"]], on="zcta5", how="left")
    feat["snapshot_date"] = snap
    feat = feat.dropna(subset=["zcta5"])
    if feat.empty:
        return 0

    con.execute("""
        CREATE TABLE IF NOT EXISTS feature_zip (
            zcta5                   VARCHAR,
            state                   VARCHAR,
            metro                   VARCHAR,
            county_name             VARCHAR,
            median_home_price       DOUBLE,
            latest_zori             DOUBLE,
            gross_yield_monthly_pct DOUBLE,
            rent_growth_5yr_cagr    DOUBLE,
            zori_coverage_months    INTEGER,
            snapshot_date           DATE,
            PRIMARY KEY (zcta5, snapshot_date)
        )
    """)
    # Ensure column order matches the table.
    for c in (
        "state", "metro", "county_name", "median_home_price", "latest_zori",
        "gross_yield_monthly_pct", "rent_growth_5yr_cagr", "zori_coverage_months",
    ):
        if c not in feat.columns:
            feat[c] = None
    con.register("_fz_stage", feat)
    con.execute("""
        INSERT OR REPLACE INTO feature_zip
        SELECT zcta5, state, metro, county_name,
               median_home_price, latest_zori,
               gross_yield_monthly_pct, rent_growth_5yr_cagr,
               zori_coverage_months, snapshot_date
        FROM _fz_stage
    """)
    con.unregister("_fz_stage")

    # Re-point the zip_features view at the populated table so the
    # composite reader picks up the new rows transparently.
    con.execute("""
        CREATE OR REPLACE VIEW zip_features AS
        SELECT zcta5, state, metro, county_name,
               median_home_price,
               gross_yield_monthly_pct,
               zori_coverage_months,
               -- Filter columns that aren't computed yet stay NULL; the
               -- filter engine treats NULL as "data not available" and
               -- skips that filter for that zip.
               CAST(NULL AS DOUBLE)   AS population_cagr_10yr,
               CAST(NULL AS BOOLEAN)  AS rent_controlled,
               CAST(NULL AS BOOLEAN)  AS high_climate_risk
        FROM feature_zip
    """)
    return len(feat)


def _safe_call(fn, con):
    """Invoke a producer and swallow its failure to a "no contribution" frame.

    Producers that crash (because a dependency table is missing or empty)
    shouldn't take down the whole populate pass.
    """
    try:
        return fn(con)
    except Exception:
        return pd.DataFrame()
