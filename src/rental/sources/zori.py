"""Zillow Observed Rent Index (ZORI), single-family + condo + multifamily, smoothed, by ZIP.

Public CSV at:
  https://files.zillowstatic.com/research/public_csvs/zori/
    Zip_zori_uc_sfrcondomfr_sm_month.csv

License: Zillow Research data is provided free for non-commercial use
(https://www.zillow.com/research/data/). Refresh cadence: monthly.

The CSV is wide-format (one column per month); we melt to long-format
(zcta5, observation_date, zori) before loading. Mirrors the ZHVI ETL
shape one-for-one so downstream feature code can treat the two
interchangeably.
"""

from datetime import date
from pathlib import Path

import duckdb
import httpx
import pandas as pd

from rental.sources.base import Source

ZORI_URL = (
    "https://files.zillowstatic.com/research/public_csvs/zori/"
    "Zip_zori_uc_sfrcondomfr_sm_month.csv"
)

_ID_COLS = ["RegionID", "RegionName", "State", "Metro", "CountyName"]
_NON_DATE_COLS = {"RegionID", "SizeRank", "RegionName", "RegionType",
                  "StateName", "State", "Metro", "CountyName"}


class ZillowZORISource(Source):
    name = "zillow_zori"

    def fetch(self, raw_dir: Path) -> Path:
        raw_dir.mkdir(parents=True, exist_ok=True)
        target = raw_dir / f"zori_{date.today().isoformat()}.csv"
        with httpx.stream("GET", ZORI_URL, timeout=180, follow_redirects=True) as r:
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
            value_name="zori",
        )
        long["observation_date"] = pd.to_datetime(long["observation_date"]).dt.date
        long = long.dropna(subset=["zori"])
        long["snapshot_date"] = date.today()
        long = long.rename(columns={
            "RegionID": "region_id",
            "RegionName": "zcta5",
            "State": "state",
            "Metro": "metro",
            "CountyName": "county_name",
        })
        long["zcta5"] = long["zcta5"].astype(str).str.zfill(5)

        con.register("_zori_stage", long)
        con.execute("""
            INSERT OR REPLACE INTO raw_zillow_zori
            SELECT region_id, zcta5, state, metro, county_name,
                   observation_date, zori, snapshot_date
            FROM _zori_stage
        """)
        con.unregister("_zori_stage")
        return len(long)
