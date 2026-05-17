"""Supply-side features.

All inputs are county grain (Census BPS, ACS B25001). We compute the
county-level features first, then apportion to ZCTAs by the residential
population share carried in ``geo_zcta_county_xwalk.res_ratio`` (each
ZCTA can span multiple counties; res_ratio sums to 1.0 per ZCTA).

Features produced (per ZCTA):

  permits_per_1000_units_5yr_avg
    Trailing 5-year average of annual permits per 1,000 housing units.
    Permits sum across the 5 most-recent BPS annual rows for the county;
    housing units come from the latest ACS B25001 snapshot. Higher
    values mean the county is adding supply faster relative to its
    existing stock.

  multifamily_share_permits
    multi_family_units / total_units, computed on the most recent
    available BPS rows for the county. The brief calls for "last 12
    months"; for annual BPS this is just the latest year. If/when we
    add monthly BPS rows the same query covers them by filtering on
    period <> 'annual' with the 12 most-recent months.

  supply_pressure_index
    A composite where high recent permits AND high MF share both push
    pressure UP. Scaled so the score is unit-free and roughly
    comparable across counties:

        pressure = 0.6 * z(permits_per_1000_units_5yr_avg)
                 + 0.4 * z(multifamily_share_permits)

    z-scores are within the returned frame's row set (national if the
    full warehouse is loaded; state-bounded scoring lives in
    rental.scoring.supply_score, which is a separate concern).

All features carry ``is_interpolated=True`` because county-grain values
are population-weighted onto ZCTAs.
"""

from __future__ import annotations

import duckdb
import pandas as pd


def county_supply_features(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """County-grain supply features. Returns one row per county_fips.

    Columns: county_fips, permits_per_1000_units_5yr_avg,
             multifamily_share_permits, supply_pressure_index
    """
    # Trailing 5-year permit totals per county. Using the 5 most-recent
    # 'annual' rows (per latest snapshot) so we don't double-count
    # monthly rows when those land.
    permits_5yr = con.execute(
        """
        WITH latest_snap AS (
            SELECT county_fips, MAX(snapshot_date) AS snap
            FROM raw_census_bps
            GROUP BY county_fips
        ),
        annual_rows AS (
            SELECT b.county_fips, b.year,
                   b.single_family_units, b.multi_family_units, b.total_units
            FROM raw_census_bps b
            INNER JOIN latest_snap ls
              ON b.county_fips = ls.county_fips AND b.snapshot_date = ls.snap
            WHERE b.period = 'annual'
        ),
        ranked AS (
            SELECT county_fips, year, total_units,
                   row_number() OVER (PARTITION BY county_fips ORDER BY year DESC) AS rn
            FROM annual_rows
        )
        SELECT county_fips,
               SUM(total_units) AS permits_5yr,
               count(*) AS years_observed
        FROM ranked
        WHERE rn <= 5
        GROUP BY county_fips
        """
    ).df()

    # Most-recent-12-months MF share. For annual data this is just the
    # newest year per county; for mixed monthly+annual data we'd swap
    # the WHERE to period <> 'annual' and LIMIT 12.
    mf_share = con.execute(
        """
        WITH latest_snap AS (
            SELECT county_fips, MAX(snapshot_date) AS snap
            FROM raw_census_bps
            GROUP BY county_fips
        ),
        latest_year AS (
            SELECT b.county_fips, MAX(b.year) AS max_year
            FROM raw_census_bps b
            INNER JOIN latest_snap ls
              ON b.county_fips = ls.county_fips AND b.snapshot_date = ls.snap
            WHERE b.period = 'annual'
            GROUP BY b.county_fips
        )
        SELECT b.county_fips,
               SUM(b.multi_family_units) AS mf_units,
               SUM(b.total_units) AS total_units
        FROM raw_census_bps b
        INNER JOIN latest_year ly
          ON b.county_fips = ly.county_fips AND b.year = ly.max_year
        INNER JOIN latest_snap ls
          ON b.county_fips = ls.county_fips AND b.snapshot_date = ls.snap
        WHERE b.period = 'annual'
        GROUP BY b.county_fips
        """
    ).df()

    # Latest ACS housing stock per county.
    stock = con.execute(
        """
        WITH latest AS (
            SELECT county_fips, MAX(year) AS max_year, MAX(snapshot_date) AS snap
            FROM raw_acs_housing_stock
            GROUP BY county_fips
        )
        SELECT s.county_fips, s.total_housing_units
        FROM raw_acs_housing_stock s
        INNER JOIN latest l
          ON s.county_fips = l.county_fips
         AND s.year = l.max_year
         AND s.snapshot_date = l.snap
        """
    ).df()

    df = permits_5yr.merge(mf_share, on="county_fips", how="outer")
    df = df.merge(stock, on="county_fips", how="left")

    # Annualized permits per 1k housing units. We divide by years_observed
    # rather than blindly /5 so counties with <5 years of data aren't
    # under-counted; rows below a 3-year floor are suppressed to NULL.
    df["permits_per_1000_units_5yr_avg"] = (
        (df["permits_5yr"] / df["years_observed"]) / df["total_housing_units"]
    ) * 1000.0
    df.loc[df["years_observed"] < 3, "permits_per_1000_units_5yr_avg"] = pd.NA
    df.loc[df["total_housing_units"].isna(), "permits_per_1000_units_5yr_avg"] = pd.NA

    df["multifamily_share_permits"] = (df["mf_units"] / df["total_units"]).where(
        df["total_units"] > 0
    )

    df["supply_pressure_index"] = _composite_pressure(
        df["permits_per_1000_units_5yr_avg"], df["multifamily_share_permits"]
    )

    return df[
        [
            "county_fips",
            "permits_per_1000_units_5yr_avg",
            "multifamily_share_permits",
            "supply_pressure_index",
        ]
    ]


def zcta_supply_features(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Apportion county-level supply features to ZCTAs by res_ratio.

    Each ZCTA's value is the res_ratio-weighted average of its constituent
    counties' values. Rows where every constituent county has a NULL
    feature value are themselves NULL for that feature.

    Returns columns: zcta5, permits_per_1000_units_5yr_avg,
                     multifamily_share_permits, supply_pressure_index,
                     is_interpolated (bool, always True)
    """
    county_df = county_supply_features(con)
    if county_df.empty:
        return pd.DataFrame(
            columns=[
                "zcta5",
                "permits_per_1000_units_5yr_avg",
                "multifamily_share_permits",
                "supply_pressure_index",
                "is_interpolated",
            ]
        )

    xwalk = con.execute(
        "SELECT zcta5, county_fips, res_ratio FROM geo_zcta_county_xwalk"
    ).df()
    if xwalk.empty:
        return pd.DataFrame(
            columns=[
                "zcta5",
                "permits_per_1000_units_5yr_avg",
                "multifamily_share_permits",
                "supply_pressure_index",
                "is_interpolated",
            ]
        )

    joined = xwalk.merge(county_df, on="county_fips", how="left")

    feature_cols = [
        "permits_per_1000_units_5yr_avg",
        "multifamily_share_permits",
        "supply_pressure_index",
    ]
    out_rows = []
    for zcta, grp in joined.groupby("zcta5"):
        row = {"zcta5": zcta}
        for col in feature_cols:
            row[col] = _weighted_mean(grp[col], grp["res_ratio"])
        row["is_interpolated"] = True
        out_rows.append(row)

    out = pd.DataFrame(out_rows)
    out = out.sort_values("zcta5").reset_index(drop=True)
    return out


def _weighted_mean(values: pd.Series, weights: pd.Series) -> float | None:
    mask = values.notna() & weights.notna()
    if not mask.any():
        return None
    v = pd.to_numeric(values[mask], errors="coerce")
    w = pd.to_numeric(weights[mask], errors="coerce")
    total_w = w.sum()
    if total_w == 0:
        return None
    return float((v * w).sum() / total_w)


def _composite_pressure(permits_per_1k: pd.Series, mf_share: pd.Series) -> pd.Series:
    """Z-combine the two pressure inputs.

    Uses each column's mean/std on the rows that have both values
    present. Returns NaN where either input is missing.
    """
    pp = pd.to_numeric(permits_per_1k, errors="coerce")
    mf = pd.to_numeric(mf_share, errors="coerce")
    mask = pp.notna() & mf.notna()
    out = pd.Series([pd.NA] * len(pp), index=pp.index, dtype="Float64")
    if mask.sum() < 2:
        return out
    pp_z = (pp - pp[mask].mean()) / (pp[mask].std() or 1.0)
    mf_z = (mf - mf[mask].mean()) / (mf[mask].std() or 1.0)
    out[mask] = (0.6 * pp_z[mask] + 0.4 * mf_z[mask]).astype("Float64")
    return out
