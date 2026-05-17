"""Zillow Home Value Index (ZHVI), all-homes, smoothed, seasonally adjusted, by ZIP.

Public CSV at:
  https://files.zillowstatic.com/research/public_csvs/zhvi/
    Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv

The CSV is wide-format (one column per month); we melt to long-format
(zcta5, observation_date, zhvi) before loading.
"""

from datetime import date
from pathlib import Path

import duckdb
import httpx
import pandas as pd

from rental.sources.base import Source

ZHVI_URL = (
    "https://files.zillowstatic.com/research/public_csvs/zhvi/"
    "Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv"
)

_ID_COLS = ["RegionID", "RegionName", "State", "Metro", "CountyName"]
_NON_DATE_COLS = {"RegionID", "SizeRank", "RegionName", "RegionType",
                  "StateName", "State", "Metro", "CountyName"}


class ZillowZHVISource(Source):
    name = "zillow_zhvi"

    def fetch(self, raw_dir: Path) -> Path:
        raw_dir.mkdir(parents=True, exist_ok=True)
        target = raw_dir / f"zhvi_{date.today().isoformat()}.csv"
        with httpx.stream("GET", ZHVI_URL, timeout=180, follow_redirects=True) as r:
            r.raise_for_status()
            with target.open("wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
        return target

    def load(self, con: duckdb.DuckDBPyConnection, raw_path: Path) -> int:
        df = pd.read_csv(raw_path, dtype={"RegionName": str})

        date_cols = [c for c in df.columns if c not in _NON_DATE_COLS]
        long = df.melt(
            id_vars=_ID_COLS,
            value_vars=date_cols,
            var_name="observation_date",
            value_name="zhvi",
        )
        long["observation_date"] = pd.to_datetime(long["observation_date"]).dt.date
        long = long.dropna(subset=["zhvi"])
        long["snapshot_date"] = date.today()
        long = long.rename(columns={
            "RegionID": "region_id",
            "RegionName": "zcta5",
            "State": "state",
            "Metro": "metro",
            "CountyName": "county_name",
        })
        long["zcta5"] = long["zcta5"].astype(str).str.zfill(5)

        con.register("_zhvi_stage", long)
        con.execute("""
            INSERT OR REPLACE INTO raw_zillow_zhvi
            SELECT region_id, zcta5, state, metro, county_name,
                   observation_date, zhvi, snapshot_date
            FROM _zhvi_stage
        """)
        con.unregister("_zhvi_stage")
        return len(long)
