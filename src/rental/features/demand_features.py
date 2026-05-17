"""Phase 2 (Demand half) feature engineering.

Three county-grain metrics are aggregated to ZCTA using the
``geo_zcta_county_xwalk.res_ratio`` residential population weights:

  * ``wage_weighted_job_cagr_5yr`` — Σ(jobs_industry × industry_avg_wage)
    growth over 5 years, restricted to rental-tenant-relevant sectors
    (healthcare 62, education 61, retail 44, food service 72,
    manufacturing 31).
  * ``net_migration_per_1000`` — (inflow returns − outflow returns) /
    county exemptions × 1000. Uses IRS exemptions as the population
    proxy since the migration file already includes them.
  * ``hh_income_growth_5yr`` — 5-year CAGR of ACS B19013 median household
    income per ZCTA (no downscaling needed; ACS is already ZCTA-grain).

All three SQL helpers return ``pandas.DataFrame``. They tolerate missing
upstream tables (returning empty frames with the right columns) so the
demand score can run partial — useful while sibling agents are still
landing their tables.
"""

from __future__ import annotations

import duckdb
import pandas as pd

# 2-digit NAICS codes whose workforce most closely tracks SFR rental demand.
# Sourced from the build plan (Phase 2: "wage_weighted_job_cagr_5yr").
TENANT_RELEVANT_NAICS = ("62", "61", "44", "72", "31")


def _table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    return bool(
        con.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = ?",
            [name],
        ).fetchone()
    )


def wage_weighted_job_cagr_5yr(
    con: duckdb.DuckDBPyConnection,
    end_year: int | None = None,
    horizon_years: int = 5,
) -> pd.DataFrame:
    """County-grain wage-weighted job growth over the last ``horizon_years``.

    For each county we compute Σ(jobs × avg_wage) over the tenant-relevant
    sectors at the end year and (end_year − horizon_years), then take the
    CAGR. Counties missing either endpoint are dropped.
    """
    cols = ["county_fips", "end_year", "start_year", "wage_weighted_job_cagr_5yr"]
    if not _table_exists(con, "raw_bls_qcew"):
        return pd.DataFrame(columns=cols)

    if end_year is None:
        end_year = con.execute(
            "SELECT MAX(year) FROM raw_bls_qcew WHERE quarter = 0"
        ).fetchone()[0]
    if end_year is None:
        return pd.DataFrame(columns=cols)
    start_year = end_year - horizon_years

    sectors = ",".join(f"'{c}'" for c in TENANT_RELEVANT_NAICS)
    sql = f"""
        WITH sector_totals AS (
            SELECT
                area_fips AS county_fips,
                year,
                SUM(employment * (total_wages / NULLIF(employment, 0))) AS wage_weighted_jobs
            FROM raw_bls_qcew
            WHERE quarter = 0
              AND industry_code IN ({sectors})
              AND year IN ({start_year}, {end_year})
            GROUP BY area_fips, year
        ),
        pivoted AS (
            SELECT
                county_fips,
                MAX(CASE WHEN year = {start_year} THEN wage_weighted_jobs END) AS start_val,
                MAX(CASE WHEN year = {end_year}   THEN wage_weighted_jobs END) AS end_val
            FROM sector_totals
            GROUP BY county_fips
        )
        SELECT
            county_fips,
            {end_year}   AS end_year,
            {start_year} AS start_year,
            POWER(end_val / NULLIF(start_val, 0), 1.0 / {horizon_years}) - 1
                AS wage_weighted_job_cagr_5yr
        FROM pivoted
        WHERE start_val IS NOT NULL AND end_val IS NOT NULL AND start_val > 0
    """
    return con.execute(sql).df()


def net_migration_per_1000(
    con: duckdb.DuckDBPyConnection,
    year: int | None = None,
) -> pd.DataFrame:
    """County-grain net migration rate per 1,000 residents (exemption-based).

    The IRS migration file already includes a "Total Migration-US" row per
    county where origin_fips == dest_fips; we use its exemptions as the
    population denominator (matches the unit of the numerator without
    needing the ACS join).
    """
    cols = ["county_fips", "year", "net_migration_per_1000"]
    if not _table_exists(con, "raw_irs_migration"):
        return pd.DataFrame(columns=cols)

    if year is None:
        year = con.execute("SELECT MAX(year) FROM raw_irs_migration").fetchone()[0]
    if year is None:
        return pd.DataFrame(columns=cols)

    sql = """
        WITH flows AS (
            SELECT
                dest_fips AS county_fips,
                SUM(CASE WHEN flow_direction = 'inflow'
                          AND origin_fips != dest_fips THEN returns ELSE 0 END)
                    AS inflow_returns,
                SUM(CASE WHEN flow_direction = 'inflow'
                          AND origin_fips = dest_fips THEN exemptions ELSE 0 END)
                    AS pop_exemptions
            FROM raw_irs_migration
            WHERE year = ?
            GROUP BY dest_fips
        ),
        outflows AS (
            SELECT
                origin_fips AS county_fips,
                SUM(CASE WHEN flow_direction = 'outflow'
                          AND origin_fips != dest_fips THEN returns ELSE 0 END)
                    AS outflow_returns
            FROM raw_irs_migration
            WHERE year = ?
            GROUP BY origin_fips
        )
        SELECT
            f.county_fips,
            ? AS year,
            CASE WHEN f.pop_exemptions > 0
                 THEN (f.inflow_returns - COALESCE(o.outflow_returns, 0))
                      * 1000.0 / f.pop_exemptions
                 ELSE NULL END AS net_migration_per_1000
        FROM flows f
        LEFT JOIN outflows o USING (county_fips)
        WHERE f.pop_exemptions > 0
    """
    return con.execute(sql, [year, year, year]).df()


def hh_income_growth_5yr(
    con: duckdb.DuckDBPyConnection,
    end_year: int | None = None,
    horizon_years: int = 5,
) -> pd.DataFrame:
    """ZCTA-grain 5-year CAGR of ACS B19013 median household income."""
    cols = ["zcta5", "end_year", "start_year", "hh_income_growth_5yr"]
    if not _table_exists(con, "raw_acs_demographics"):
        return pd.DataFrame(columns=cols)

    if end_year is None:
        end_year = con.execute(
            "SELECT MAX(year) FROM raw_acs_demographics"
        ).fetchone()[0]
    if end_year is None:
        return pd.DataFrame(columns=cols)
    start_year = end_year - horizon_years

    sql = f"""
        WITH pivoted AS (
            SELECT
                zcta5,
                MAX(CASE WHEN year = {start_year}
                         THEN median_household_income END) AS start_val,
                MAX(CASE WHEN year = {end_year}
                         THEN median_household_income END) AS end_val
            FROM raw_acs_demographics
            WHERE year IN ({start_year}, {end_year})
            GROUP BY zcta5
        )
        SELECT
            zcta5,
            {end_year}   AS end_year,
            {start_year} AS start_year,
            POWER(end_val * 1.0 / NULLIF(start_val, 0), 1.0 / {horizon_years}) - 1
                AS hh_income_growth_5yr
        FROM pivoted
        WHERE start_val IS NOT NULL AND end_val IS NOT NULL AND start_val > 0
    """
    return con.execute(sql).df()


def county_to_zcta(
    con: duckdb.DuckDBPyConnection,
    county_df: pd.DataFrame,
    value_col: str,
) -> pd.DataFrame:
    """Aggregate a county-grain metric to ZCTA using the residential-ratio xwalk.

    The xwalk in ``geo_zcta_county_xwalk`` carries ``res_ratio`` — the
    residential population share of each ZCTA that falls in each county.
    We compute a population-weighted average of the metric across the
    counties intersecting each ZCTA. The weights are normalized to the
    counties that actually have data, so a ZCTA whose xwalk crosses a
    county with no metric value isn't penalized.
    """
    if county_df.empty:
        return pd.DataFrame(columns=["zcta5", value_col])

    con.register("_county_metric", county_df[["county_fips", value_col]])
    try:
        df = con.execute(
            f"""
            SELECT
                x.zcta5,
                SUM(m.{value_col} * x.res_ratio)
                    / NULLIF(SUM(x.res_ratio), 0) AS {value_col}
            FROM geo_zcta_county_xwalk x
            INNER JOIN _county_metric m ON x.county_fips = m.county_fips
            WHERE m.{value_col} IS NOT NULL
            GROUP BY x.zcta5
            """
        ).df()
    finally:
        con.unregister("_county_metric")
    return df


def demand_features(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Build the joined ZCTA-grain demand feature frame.

    Returns one row per ZCTA with three columns of features (plus zcta5).
    Missing features are NaN — the downstream scorer drops them with
    null-aware z-score normalization.
    """
    jobs_county = wage_weighted_job_cagr_5yr(con)
    migration_county = net_migration_per_1000(con)
    income_zcta = hh_income_growth_5yr(con)

    jobs_zcta = county_to_zcta(con, jobs_county, "wage_weighted_job_cagr_5yr")
    migration_zcta = county_to_zcta(con, migration_county, "net_migration_per_1000")

    # Start from the union of all zctas we have any feature for.
    frames = [df for df in (jobs_zcta, migration_zcta, income_zcta) if not df.empty]
    if not frames:
        return pd.DataFrame(
            columns=[
                "zcta5",
                "wage_weighted_job_cagr_5yr",
                "net_migration_per_1000",
                "hh_income_growth_5yr",
            ]
        )

    out = frames[0][["zcta5"]].copy()
    for df in frames[1:]:
        out = out.merge(df[["zcta5"]], on="zcta5", how="outer")
    for df, col in (
        (jobs_zcta, "wage_weighted_job_cagr_5yr"),
        (migration_zcta, "net_migration_per_1000"),
        (income_zcta, "hh_income_growth_5yr"),
    ):
        if df.empty:
            out[col] = float("nan")
        else:
            out = out.merge(df[["zcta5", col]], on="zcta5", how="left")
    return out.sort_values("zcta5").reset_index(drop=True)
