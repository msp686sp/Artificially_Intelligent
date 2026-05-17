"""Eviction Lab county-level eviction filings + filing rates.

Public CSVs at:
  https://data-downloads.evictionlab.org/
    (per-state county CSVs, e.g. counties.csv inside the state ZIP)

The canonical county file has at minimum: GEOID (5-char county FIPS), year,
filings, filing-rate (filings per 100 renter households). Real downloads use
column names like ``filings_2018`` / ``filing_rate_2018`` in some vintages
and a long-form ``year`` column in others. This loader accepts either shape
and normalizes to long-form.

License: Eviction Lab data is released under the Eviction Lab Open Data
License (free for research / non-commercial; attribution required).
Cadence: annual (multi-year lag — 2018 was the headline base year, with
incremental updates from court-record partnerships since).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import httpx
import pandas as pd

from rental.sources.base import Source

# Landing page; the actual CSV path depends on the state/vintage chosen.
# Override via the fixture path in tests / when running locally.
EVICTION_LAB_URL = (
    "https://data-downloads.evictionlab.org/v1/all-counties.csv"
)


def _normalize_county_fips(value: object) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in {"nan", "none"}:
        return None
    # Eviction Lab uses GEOID with a leading zero already; pandas may strip.
    if s.endswith(".0"):
        s = s[:-2]
    return s.zfill(5)


class EvictionLabSource(Source):
    name = "eviction_lab"

    def fetch(self, raw_dir: Path) -> Path:
        raw_dir.mkdir(parents=True, exist_ok=True)
        target = raw_dir / f"eviction_lab_{date.today().isoformat()}.csv"
        with httpx.stream("GET", EVICTION_LAB_URL, timeout=180, follow_redirects=True) as r:
            r.raise_for_status()
            with target.open("wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
        return target

    def load(self, con: duckdb.DuckDBPyConnection, raw_path: Path) -> int:
        df = pd.read_csv(raw_path, dtype=str)

        # Accept two shapes: long (GEOID, year, filings, filing_rate) or wide
        # (GEOID + filings_YYYY / filing_rate_YYYY columns).
        cols_lower = {c.lower(): c for c in df.columns}
        geoid_col = (
            cols_lower.get("geoid")
            or cols_lower.get("county_fips")
            or cols_lower.get("fips")
        )
        if geoid_col is None:
            raise ValueError("Eviction Lab CSV missing GEOID column")

        if "year" in cols_lower:
            long = df.rename(
                columns={
                    geoid_col: "county_fips",
                    cols_lower["year"]: "year",
                    cols_lower.get("filings", "filings"): "evictions_filed",
                    cols_lower.get("filing_rate", "filing_rate"): "eviction_filing_rate",
                }
            )[["county_fips", "year", "evictions_filed", "eviction_filing_rate"]]
        else:
            filing_cols = [c for c in df.columns if c.lower().startswith("filings_")]
            rate_cols = [c for c in df.columns if c.lower().startswith("filing_rate_")]
            records = []
            for _, row in df.iterrows():
                gid = row[geoid_col]
                for fc in filing_cols:
                    yr = fc.split("_")[-1]
                    rc_match = [c for c in rate_cols if c.endswith(f"_{yr}")]
                    rc = rc_match[0] if rc_match else None
                    records.append(
                        {
                            "county_fips": gid,
                            "year": yr,
                            "evictions_filed": row.get(fc),
                            "eviction_filing_rate": row.get(rc) if rc else None,
                        }
                    )
            long = pd.DataFrame.from_records(records)

        long["county_fips"] = long["county_fips"].map(_normalize_county_fips)
        long = long.dropna(subset=["county_fips"])
        long["year"] = pd.to_numeric(long["year"], errors="coerce").astype("Int64")
        long = long.dropna(subset=["year"])
        long["evictions_filed"] = pd.to_numeric(long["evictions_filed"], errors="coerce")
        long["eviction_filing_rate"] = pd.to_numeric(long["eviction_filing_rate"], errors="coerce")
        long = long.dropna(subset=["evictions_filed", "eviction_filing_rate"], how="all")
        long["snapshot_date"] = date.today()
        long["year"] = long["year"].astype(int)

        con.register("_eviction_stage", long)
        con.execute(
            """
            INSERT OR REPLACE INTO raw_eviction_lab
            SELECT county_fips, year, evictions_filed, eviction_filing_rate, snapshot_date
            FROM _eviction_stage
            """
        )
        con.unregister("_eviction_stage")
        return len(long)
