"""ACS 5-year demographics, ZCTA-grain.

Source (Census Data API, no key required for low volume):
  https://api.census.gov/data/{year}/acs/acs5
    ?get=B01003_001E,B19013_001E,B01002_001E
    &for=zip+code+tabulation+area:*

Variables:
  B01003_001E — total population
  B19013_001E — median household income (whole dollars)
  B01002_001E — median age (years)

Response shape is the Census array-of-arrays JSON: the first row is the
header (column names), subsequent rows are records. The geography column
for ZCTA queries is ``zip code tabulation area``. The bundled fixture
mirrors that exact shape so tests exercise the same code path that the
real API hits.

License: U.S. Government work, public domain.
Cadence: annual, December release for the previous-year endyear.

Network note: in this repo's sandboxed CI, outbound to api.census.gov is
blocked. ``fetch()`` is wired against the real API for local refreshes;
tests load a bundled JSON fixture matching the wire shape.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import duckdb
import httpx
import pandas as pd

from rental.sources.base import Source

ACS_API_TEMPLATE = (
    "https://api.census.gov/data/{year}/acs/acs5"
    "?get=B01003_001E,B19013_001E,B01002_001E"
    "&for=zip+code+tabulation+area:*"
)

# Census sentinel for "not available" — appears in places like median_hh_income
# for tiny ZCTAs where they suppress the estimate. We coerce to NULL.
ACS_NA_SENTINEL = -666666666

# Most recent ACS 5yr endyear we'll attempt during fetch. Census usually
# publishes Dec of year+1, so a conservative default is year-3.
def _default_endyear_candidates() -> list[int]:
    return [date.today().year - n for n in range(2, 6)]


class ACSDemographicsSource(Source):
    """ACS 5-year ZCTA demographics (population, median HH income, median age)."""

    name = "acs_demographics"

    def fetch(self, raw_dir: Path) -> Path:
        """Pull the most recent published ACS 5yr release for all ZCTAs."""
        raw_dir.mkdir(parents=True, exist_ok=True)
        last_err: Exception | None = None
        for year in _default_endyear_candidates():
            url = ACS_API_TEMPLATE.format(year=year)
            try:
                r = httpx.get(url, timeout=180, follow_redirects=True)
            except httpx.HTTPError as exc:
                last_err = exc
                continue
            if r.status_code == 200 and r.content:
                target = raw_dir / f"acs_demographics_{year}_{date.today().isoformat()}.json"
                # The body wraps a tagged dict so we keep the endyear with the payload.
                payload = {"year": year, "data": r.json()}
                target.write_text(json.dumps(payload))
                return target

        raise RuntimeError(
            f"Could not fetch ACS 5yr ZCTA demographics in the last 5 years: {last_err}"
        )

    def load(self, con: duckdb.DuckDBPyConnection, raw_path: Path) -> int:
        payload = json.loads(raw_path.read_text())

        # Allow two shapes for flexibility:
        #   {"year": <int>, "data": [[header], [row], ...]}
        #   [[header], [row], ...]    (raw Census response)
        if isinstance(payload, dict) and "data" in payload:
            data = payload["data"]
            year = int(payload.get("year") or 0) or None
        else:
            data = payload
            year = None

        if not data or len(data) < 2:
            return 0

        header, *body = data
        df = pd.DataFrame(body, columns=header)

        # Census geography column is named "zip code tabulation area"; pad to 5.
        zcta_col = "zip code tabulation area"
        if zcta_col not in df.columns:
            # Some endyears alias the column; accept the common alternative.
            for alt in ("zcta", "zcta5"):
                if alt in df.columns:
                    zcta_col = alt
                    break
        if zcta_col not in df.columns:
            raise ValueError(
                f"ACS fixture missing ZCTA geography column; got {list(df.columns)}"
            )

        out = pd.DataFrame({
            "zcta5": df[zcta_col].astype(str).str.zfill(5),
            "population": pd.to_numeric(df.get("B01003_001E"), errors="coerce"),
            "median_household_income": pd.to_numeric(
                df.get("B19013_001E"), errors="coerce"
            ),
            "median_age": pd.to_numeric(df.get("B01002_001E"), errors="coerce"),
        })
        # Treat the Census "not available" sentinel as NULL.
        out["median_household_income"] = out["median_household_income"].where(
            out["median_household_income"] != ACS_NA_SENTINEL
        )
        # Drop rows missing all measures (pure-noise records).
        out = out.dropna(
            subset=["population", "median_household_income", "median_age"],
            how="all",
        )
        out["population"] = out["population"].astype("Int64")
        out["median_household_income"] = out["median_household_income"].astype("Int64")

        # Fall back to today's year if the payload didn't carry it.
        out["year"] = year or date.today().year
        out["snapshot_date"] = date.today()

        con.register("_acs_stage", out)
        con.execute("""
            INSERT OR REPLACE INTO raw_acs_demographics
            SELECT zcta5, year, population, median_household_income,
                   median_age, snapshot_date
            FROM _acs_stage
        """)
        con.unregister("_acs_stage")
        return len(out)
