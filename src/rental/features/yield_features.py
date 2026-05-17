"""Yield-half features: gross yield + rent-growth CAGR per zip.

Inputs:
  - raw_zillow_zhvi (price, monthly)
  - raw_zillow_zori (rent, monthly)

Outputs a single DataFrame keyed on `zcta5` with columns:
  - latest_zhvi
  - latest_zori
  - gross_yield_monthly_pct   (latest_zori / latest_zhvi) * 100  (e.g. 0.75 = 0.75%/mo)
  - rent_growth_5yr_cagr      compound annual growth rate of ZORI over the
                              most recent ~5y window, in raw units (e.g. 0.04 = 4%/yr)
  - zori_coverage_months      total ZORI observations available for the zip
                              (data-quality flag; surfaced in filters.yaml)

The 5y CAGR uses the latest observation and the closest observation
60 months earlier; if the zip has fewer than 60 months of coverage, the
oldest-available observation is used and a `cagr_window_months` column
records the actual span.

Per the spec, this function is robust to other features being missing
in downstream scoring — it only emits what it can compute from ZHVI+ZORI.
"""

from __future__ import annotations

import duckdb
import pandas as pd


def yield_features(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """One row per zip with yield + rent-growth features.

    Uses the most recent snapshot in each of the raw tables, joins on
    zcta5, and returns a DataFrame ready to merge with tax/insurance
    features from other agents.
    """
    # Latest observation per zip in each source.
    latest_zhvi = con.execute("""
        WITH snap AS (SELECT MAX(snapshot_date) AS s FROM raw_zillow_zhvi)
        SELECT z.zcta5,
               z.state,
               z.zhvi AS latest_zhvi,
               z.observation_date AS zhvi_obs_date
        FROM raw_zillow_zhvi z
        JOIN snap ON z.snapshot_date = snap.s
        JOIN (
            SELECT zcta5, MAX(observation_date) AS d
            FROM raw_zillow_zhvi, snap
            WHERE snapshot_date = snap.s
            GROUP BY zcta5
        ) m ON m.zcta5 = z.zcta5 AND m.d = z.observation_date
    """).df()

    latest_zori = con.execute("""
        WITH snap AS (SELECT MAX(snapshot_date) AS s FROM raw_zillow_zori)
        SELECT z.zcta5,
               z.zori AS latest_zori,
               z.observation_date AS zori_obs_date
        FROM raw_zillow_zori z
        JOIN snap ON z.snapshot_date = snap.s
        JOIN (
            SELECT zcta5, MAX(observation_date) AS d
            FROM raw_zillow_zori, snap
            WHERE snapshot_date = snap.s
            GROUP BY zcta5
        ) m ON m.zcta5 = z.zcta5 AND m.d = z.observation_date
    """).df()

    coverage = con.execute("""
        WITH snap AS (SELECT MAX(snapshot_date) AS s FROM raw_zillow_zori)
        SELECT zcta5, COUNT(*) AS zori_coverage_months
        FROM raw_zillow_zori, snap
        WHERE snapshot_date = snap.s
        GROUP BY zcta5
    """).df()

    cagr = _rent_growth_cagr(con)

    out = latest_zhvi.merge(latest_zori, on="zcta5", how="inner")
    out = out.merge(coverage, on="zcta5", how="left")
    out = out.merge(cagr, on="zcta5", how="left")

    # Per the locked plan: gross_yield expressed as MONTHLY percent
    # (rent / price × 100). The filters.yaml threshold of 0.8 reads as
    # "monthly rent is at least 0.8% of price" — the classic investor
    # heuristic ~ 9.6% annual gross yield.
    out["gross_yield_monthly_pct"] = (
        out["latest_zori"] / out["latest_zhvi"]
    ) * 100.0
    return out


def _rent_growth_cagr(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Compute ZORI 5-year CAGR per zip, falling back to oldest-available
    if the zip has less than 60 months of history."""
    df = con.execute("""
        WITH snap AS (SELECT MAX(snapshot_date) AS s FROM raw_zillow_zori)
        SELECT z.zcta5, z.observation_date, z.zori
        FROM raw_zillow_zori z, snap
        WHERE z.snapshot_date = snap.s
    """).df()
    if df.empty:
        return pd.DataFrame(
            columns=["zcta5", "rent_growth_5yr_cagr", "cagr_window_months"]
        )

    df["observation_date"] = pd.to_datetime(df["observation_date"])
    df = df.dropna(subset=["zori"]).sort_values(["zcta5", "observation_date"])

    rows = []
    for zcta, g in df.groupby("zcta5"):
        latest_date = g["observation_date"].iloc[-1]
        latest_zori = g["zori"].iloc[-1]

        target_date = latest_date - pd.DateOffset(years=5)
        prior = g[g["observation_date"] <= target_date]
        if not prior.empty:
            base = prior.iloc[-1]
        else:
            # Less than 5y of history — use the earliest available.
            base = g.iloc[0]
        months = max(
            int(round((latest_date - base["observation_date"]).days / 30.4375)),
            0,
        )
        if base["zori"] and base["zori"] > 0 and months > 0:
            years = months / 12.0
            cagr = (latest_zori / base["zori"]) ** (1.0 / years) - 1.0
        else:
            cagr = None
        rows.append({
            "zcta5": zcta,
            "rent_growth_5yr_cagr": cagr,
            "cagr_window_months": months,
        })
    return pd.DataFrame(rows)
