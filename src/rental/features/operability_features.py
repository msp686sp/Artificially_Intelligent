"""Operability features (Phase 4).

Three zip-level features:
  - ``effective_tax_rate``     — county-level rate, weighted to zip via
                                 ``geo_zcta_county_xwalk.res_ratio``.
  - ``insurance_rate_estimate`` — state-level average premium joined onto each
                                 zip's state. Not zip-specific yet.
                                 TODO: replace with zip-level multiplier once
                                 Phase 5 climate-adjusted insurance lands.
  - ``eviction_filing_rate``   — county-level filing rate, weighted to zip
                                 via ``geo_zcta_county_xwalk.res_ratio``.

Each function returns a pandas DataFrame keyed on ``zcta5``. If the
crosswalk table is empty (e.g., another agent hasn't populated it yet) the
county-derived features return an empty DataFrame so downstream scoring
gracefully sees NaNs.
"""

from __future__ import annotations

import duckdb
import pandas as pd


def effective_tax_rate(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """zcta5 -> effective_tax_rate (residential-population-weighted county avg).

    Uses the latest snapshot per county. A zip that overlaps multiple
    counties gets a weighted average using ``res_ratio``.
    """
    return con.execute(
        """
        WITH latest AS (
            SELECT county_fips, MAX(snapshot_date) AS snap
            FROM raw_county_tax_rate
            GROUP BY county_fips
        ),
        latest_rate AS (
            SELECT t.county_fips, t.year, t.effective_rate
            FROM raw_county_tax_rate t
            INNER JOIN latest l
              ON l.county_fips = t.county_fips AND l.snap = t.snapshot_date
        )
        SELECT x.zcta5,
               SUM(lr.effective_rate * x.res_ratio) /
                   NULLIF(SUM(x.res_ratio), 0) AS effective_tax_rate
        FROM geo_zcta_county_xwalk x
        INNER JOIN latest_rate lr ON lr.county_fips = x.county_fips
        GROUP BY x.zcta5
        ORDER BY x.zcta5
        """
    ).df()


def insurance_rate_estimate(
    con: duckdb.DuckDBPyConnection,
    policy_form: str = "HO-3",
) -> pd.DataFrame:
    """zcta5 -> insurance_rate_estimate from the bundled state averages.

    Joins each zip to its state via ``geo_zcta``, then to the most-recent
    year in ``ref_state_insurance`` for the requested policy form. Returns
    one row per zip in ``geo_zcta`` that has a state match.

    TODO (Phase 5): apply a zip-level climate multiplier so this is no
    longer state-uniform. Until then, every zip in a state shares its
    state's average premium.
    """
    return con.execute(
        """
        WITH latest_year AS (
            SELECT state, policy_form, MAX(year) AS yr
            FROM ref_state_insurance
            WHERE policy_form = ?
            GROUP BY state, policy_form
        ),
        latest_premium AS (
            SELECT r.state, r.year, r.avg_annual_premium, r.policy_form
            FROM ref_state_insurance r
            INNER JOIN latest_year ly
              ON ly.state = r.state
             AND ly.policy_form = r.policy_form
             AND ly.yr = r.year
        )
        SELECT z.zcta5,
               z.state,
               lp.year AS insurance_year,
               lp.avg_annual_premium AS insurance_rate_estimate
        FROM geo_zcta z
        INNER JOIN latest_premium lp ON lp.state = z.state
        ORDER BY z.zcta5
        """,
        [policy_form],
    ).df()


def eviction_filing_rate(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """zcta5 -> eviction_filing_rate (county-level, latest year, res_ratio-weighted)."""
    return con.execute(
        """
        WITH latest_snap AS (
            SELECT county_fips, MAX(snapshot_date) AS snap
            FROM raw_eviction_lab
            GROUP BY county_fips
        ),
        latest_year AS (
            SELECT e.county_fips, MAX(e.year) AS yr
            FROM raw_eviction_lab e
            INNER JOIN latest_snap ls
              ON ls.county_fips = e.county_fips AND ls.snap = e.snapshot_date
            GROUP BY e.county_fips
        ),
        latest_rate AS (
            SELECT e.county_fips, e.year, e.eviction_filing_rate
            FROM raw_eviction_lab e
            INNER JOIN latest_snap ls
              ON ls.county_fips = e.county_fips AND ls.snap = e.snapshot_date
            INNER JOIN latest_year ly
              ON ly.county_fips = e.county_fips AND ly.yr = e.year
            WHERE e.eviction_filing_rate IS NOT NULL
        )
        SELECT x.zcta5,
               SUM(lr.eviction_filing_rate * x.res_ratio) /
                   NULLIF(SUM(x.res_ratio), 0) AS eviction_filing_rate
        FROM geo_zcta_county_xwalk x
        INNER JOIN latest_rate lr ON lr.county_fips = x.county_fips
        GROUP BY x.zcta5
        ORDER BY x.zcta5
        """
    ).df()


def operability_feature_frame(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Wide table: one row per zip, columns for each operability feature.

    Outer-joins the three components so a zip missing one input still
    surfaces (with NaN in the missing column). Used by the OperabilityScore
    aggregator.
    """
    tax = effective_tax_rate(con)
    ins = insurance_rate_estimate(con)
    evic = eviction_filing_rate(con)

    out = tax.merge(
        ins[["zcta5", "state", "insurance_rate_estimate"]],
        on="zcta5",
        how="outer",
    ).merge(evic, on="zcta5", how="outer")
    return out
