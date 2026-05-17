"""County effective property-tax rate, derived from ACS 5-year tables.

Census ACS API:
  https://api.census.gov/data/2022/acs/acs5
    ?get=B25103_001E,B25077_001E&for=county:*

  B25103_001E = median real estate taxes paid (owner-occupied units, dollars)
  B25077_001E = median value of owner-occupied housing units (dollars)

We compute effective_rate = B25103 / B25077 per county and store one row per
(county_fips, year, snapshot_date).

License: public domain (US Census Bureau).
Cadence: annual (ACS 5-year vintages release each December). Refresh once a
year; results are stable mid-year.

The Census API returns a JSON array-of-arrays where the first row is the
column header. Sentinel value -666666666 (and similar negative codes) means
"data not available" and is dropped.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import duckdb
import httpx
import pandas as pd

from rental.sources.base import Source

ACS_YEAR = 2022
ACS_URL = (
    f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5"
    "?get=B25103_001E,B25077_001E&for=county:*"
)


def _to_float(value: object) -> float | None:
    """Census sentinels (-666666666 etc) and 'null' / '' become None."""
    if value is None:
        return None
    if isinstance(value, str):
        if value.strip().lower() in {"", "null", "none"}:
            return None
        try:
            f = float(value)
        except ValueError:
            return None
    else:
        try:
            f = float(value)
        except (TypeError, ValueError):
            return None
    # Census uses large negative sentinels for "no data" / "annotation".
    if f <= 0:
        return None
    return f


class CountyTaxRateSource(Source):
    name = "county_tax_rate"

    def fetch(self, raw_dir: Path) -> Path:
        raw_dir.mkdir(parents=True, exist_ok=True)
        target = raw_dir / f"county_tax_{ACS_YEAR}_{date.today().isoformat()}.json"
        with httpx.Client(timeout=180, follow_redirects=True) as client:
            r = client.get(ACS_URL)
            r.raise_for_status()
            target.write_bytes(r.content)
        return target

    def load(self, con: duckdb.DuckDBPyConnection, raw_path: Path) -> int:
        rows = json.loads(Path(raw_path).read_text())
        if not rows or len(rows) < 2:
            return 0
        header = rows[0]
        idx = {col: i for i, col in enumerate(header)}
        tax_i = idx["B25103_001E"]
        val_i = idx["B25077_001E"]
        st_i = idx["state"]
        co_i = idx["county"]

        records = []
        for r in rows[1:]:
            tax = _to_float(r[tax_i])
            home = _to_float(r[val_i])
            county_fips = f"{r[st_i]}{r[co_i]}"
            if tax is None or home is None:
                continue
            records.append(
                {
                    "county_fips": county_fips,
                    "year": ACS_YEAR,
                    "median_tax_paid": tax,
                    "median_home_value": home,
                    "effective_rate": tax / home,
                    "snapshot_date": date.today(),
                }
            )

        if not records:
            return 0

        df = pd.DataFrame.from_records(records)
        con.register("_county_tax_stage", df)
        con.execute(
            """
            INSERT OR REPLACE INTO raw_county_tax_rate
            SELECT county_fips, year, median_tax_paid, median_home_value,
                   effective_rate, snapshot_date
            FROM _county_tax_stage
            """
        )
        con.unregister("_county_tax_stage")
        return len(df)
