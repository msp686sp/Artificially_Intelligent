"""Risk features (Phase 4).

Zip-level climate risk derived from FEMA National Risk Index (county grain),
downscaled to ZCTA via the residential-population crosswalk.

  - ``climate_risk_score`` — composite NRI risk index, res_ratio-weighted.
  - ``flood_risk``         — flood-specific sub-score.
  - ``wildfire_risk``      — wildfire-specific sub-score.
  - ``hurricane_risk``     — hurricane-specific sub-score.

All four come from the same FEMA snapshot. The function aggregates the
latest snapshot per county, so re-runs are idempotent.
"""

from __future__ import annotations

import duckdb
import pandas as pd


def climate_risk_features(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Wide zip-level frame: composite + four hazard-specific scores."""
    return con.execute(
        """
        WITH latest AS (
            SELECT county_fips, MAX(snapshot_date) AS snap
            FROM raw_fema_nri
            GROUP BY county_fips
        ),
        latest_nri AS (
            SELECT f.county_fips,
                   f.risk_index_score,
                   f.flood_score,
                   f.wildfire_score,
                   f.hurricane_score,
                   f.heatwave_score
            FROM raw_fema_nri f
            INNER JOIN latest l
              ON l.county_fips = f.county_fips AND l.snap = f.snapshot_date
        )
        SELECT x.zcta5,
               SUM(n.risk_index_score * x.res_ratio) /
                   NULLIF(SUM(CASE WHEN n.risk_index_score IS NULL THEN 0 ELSE x.res_ratio END), 0)
                   AS climate_risk_score,
               SUM(n.flood_score * x.res_ratio) /
                   NULLIF(SUM(CASE WHEN n.flood_score IS NULL THEN 0 ELSE x.res_ratio END), 0)
                   AS flood_risk,
               SUM(n.wildfire_score * x.res_ratio) /
                   NULLIF(SUM(CASE WHEN n.wildfire_score IS NULL THEN 0 ELSE x.res_ratio END), 0)
                   AS wildfire_risk,
               SUM(n.hurricane_score * x.res_ratio) /
                   NULLIF(SUM(CASE WHEN n.hurricane_score IS NULL THEN 0 ELSE x.res_ratio END), 0)
                   AS hurricane_risk
        FROM geo_zcta_county_xwalk x
        INNER JOIN latest_nri n ON n.county_fips = x.county_fips
        GROUP BY x.zcta5
        ORDER BY x.zcta5
        """
    ).df()


def climate_risk_score(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Subset of ``climate_risk_features`` exposing only the composite."""
    df = climate_risk_features(con)
    if df.empty:
        return df
    return df[["zcta5", "climate_risk_score"]].copy()
