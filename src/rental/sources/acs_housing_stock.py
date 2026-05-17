"""ACS 5-year B25001 total housing units, county grain.

Used to normalize permits to a per-housing-unit basis (the
``permits_per_1000_units`` feature). Source:

    https://api.census.gov/data/{year}/acs/acs5?get=NAME,B25001_001E
        &for=county:*&in=state:*

The API returns a JSON 2-D array — first row is the header, remaining
rows are values. Variable ``B25001_001E`` is "total housing units" from
the ACS 5-year detailed tables.

The demand agent owns broader ACS demographics (``raw_acs_demographics``).
We pull this narrow B25001 slice into a separate table so the supply
layer doesn't reach across agents; the orchestrator can dedupe if both
tables end up carrying total-housing-units.

License: U.S. Census Bureau public-domain (Title 13).
Refresh cadence: annual (ACS 5-year vintage releases each December).
"""

import json
from datetime import date
from pathlib import Path

import duckdb
import httpx
import pandas as pd

from rental.sources.base import Source

# B25001_001E = total housing units (ACS 5-year detailed table).
ACS_HOUSING_STOCK_URL_TEMPLATE = (
    "https://api.census.gov/data/{year}/acs/acs5"
    "?get=NAME,B25001_001E&for=county:*&in=state:*"
)


def _default_vintage() -> int:
    # ACS 5-year for end-year N drops in late N+1. Pin to the year that
    # is reliably published at run time.
    return date.today().year - 2


class ACSHousingStockSource(Source):
    name = "acs_housing_stock"

    def __init__(self, year: int | None = None):
        self.year = year if year is not None else _default_vintage()

    def fetch(self, raw_dir: Path) -> Path:
        raw_dir.mkdir(parents=True, exist_ok=True)
        url = ACS_HOUSING_STOCK_URL_TEMPLATE.format(year=self.year)
        target = raw_dir / f"acs_housing_stock_{self.year}_{date.today().isoformat()}.json"
        with httpx.stream("GET", url, timeout=120, follow_redirects=True) as r:
            r.raise_for_status()
            with target.open("wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
        return target

    def load(self, con: duckdb.DuckDBPyConnection, raw_path: Path) -> int:
        df = _parse_acs_json(raw_path)
        df["snapshot_date"] = date.today()
        df["year"] = self.year

        con.register("_acs_stock_stage", df)
        con.execute(
            """
            INSERT OR REPLACE INTO raw_acs_housing_stock
            SELECT county_fips, year, total_housing_units, snapshot_date
            FROM _acs_stock_stage
            """
        )
        con.unregister("_acs_stock_stage")
        return len(df)


def _parse_acs_json(path: Path) -> pd.DataFrame:
    """Convert ACS API JSON (list-of-lists) to a tidy frame.

    Header row example:
      ["NAME","B25001_001E","state","county"]
    Remaining rows carry the matching values.
    """
    payload = json.loads(path.read_text())
    if not payload or not isinstance(payload, list):
        raise ValueError("ACS response is not a non-empty list")
    header, *rows = payload
    df = pd.DataFrame(rows, columns=header)

    # Required slices: state + county codes form the 5-char FIPS.
    if not {"state", "county", "B25001_001E"} <= set(df.columns):
        raise ValueError(f"ACS payload missing expected columns: {df.columns.tolist()}")

    df["county_fips"] = (
        df["state"].astype(str).str.zfill(2) + df["county"].astype(str).str.zfill(3)
    )
    df["total_housing_units"] = pd.to_numeric(df["B25001_001E"], errors="coerce")
    df = df.dropna(subset=["total_housing_units"])
    df["total_housing_units"] = df["total_housing_units"].astype(int)
    return df[["county_fips", "total_housing_units"]]
