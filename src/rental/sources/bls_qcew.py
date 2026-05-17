"""BLS Quarterly Census of Employment and Wages (QCEW) — county-grain.

Public CSV-in-zip at:
  https://data.bls.gov/cew/data/files/{year}/csv/{year}_annual_singlefile.zip

The annual single-file zip contains one CSV row per
(area_fips, own_code, industry_code, agglvl_code, size_code) covering every
geography (national, state, MSA, county). We filter to county-grain rows
(``area_fips`` length 5, not all-zero) at load time. The wide schema
includes ~40 columns; we project just the rental-demand-relevant ones:
``annual_avg_emplvl`` and ``total_annual_wages`` per (area, year, industry).

License: U.S. Government work, public domain.
Cadence: annual file lands ~May of the following year; quarterly files
~6 months after each quarter close.

Network note: in this repo's sandboxed CI, outbound to data.bls.gov is
blocked. ``fetch()`` is wired against the real public URL for local
refreshes; tests load a bundled CSV fixture matching the post-parse shape
this module loads into ``raw_bls_qcew``.
"""

from __future__ import annotations

import io
import zipfile
from datetime import date
from pathlib import Path

import duckdb
import httpx
import pandas as pd

from rental.sources.base import Source

QCEW_ANNUAL_URL_TEMPLATE = (
    "https://data.bls.gov/cew/data/files/{year}/csv/{year}_annual_singlefile.zip"
)

# Columns we keep from the raw QCEW CSV; the file has ~40 columns total.
# See https://www.bls.gov/cew/about-data/downloadable-file-layouts.htm.
_KEEP_COLS = [
    "area_fips",
    "own_code",
    "industry_code",
    "agglvl_code",
    "year",
    "qtr",
    "annual_avg_emplvl",
    "total_annual_wages",
]


class BLSQcewSource(Source):
    """County-level annual QCEW employment & wages, projected to rental-relevant columns."""

    name = "bls_qcew"

    def fetch(self, raw_dir: Path) -> Path:
        """Download and unzip the latest available annual single-file.

        Walks back from the current year until a year's annual zip is
        available; writes the inner CSV to ``raw_dir``.
        """
        raw_dir.mkdir(parents=True, exist_ok=True)
        today = date.today()
        last_err: Exception | None = None
        for year in range(today.year - 1, today.year - 5, -1):
            url = QCEW_ANNUAL_URL_TEMPLATE.format(year=year)
            try:
                with httpx.stream("GET", url, timeout=300, follow_redirects=True) as r:
                    if r.status_code == 404:
                        continue
                    r.raise_for_status()
                    payload = b"".join(r.iter_bytes())
            except httpx.HTTPError as exc:
                last_err = exc
                continue

            with zipfile.ZipFile(io.BytesIO(payload)) as zf:
                csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
                if not csv_names:
                    raise RuntimeError(f"QCEW zip for {year} contained no csv: {zf.namelist()}")
                target = raw_dir / f"qcew_{year}_annual_{date.today().isoformat()}.csv"
                with zf.open(csv_names[0]) as src, target.open("wb") as dst:
                    dst.write(src.read())
                return target

        raise RuntimeError(
            f"Could not fetch a QCEW annual single-file in the last 5 years: {last_err}"
        )

    def load(self, con: duckdb.DuckDBPyConnection, raw_path: Path) -> int:
        # The single-file has many columns; only parse what we need.
        df = pd.read_csv(
            raw_path,
            dtype={
                "area_fips": str,
                "industry_code": str,
                "qtr": str,
            },
            usecols=lambda c: c in _KEEP_COLS,
        )
        # qtr is "A" for annual rows and "1".."4" for quarterly; map "A"→0.
        df["qtr"] = pd.to_numeric(
            df["qtr"].replace({"A": "0"}), errors="coerce"
        )
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
        df["own_code"] = pd.to_numeric(df.get("own_code"), errors="coerce")

        # County-grain rows have a 5-char area_fips and are not the nation-wide
        # bucket ("US000"). The QCEW also publishes state ("ST" prefix) and MSA
        # ("C" prefix) aggregates; those are filtered out by the length check.
        df["area_fips"] = df["area_fips"].astype(str).str.zfill(5)
        df = df[df["area_fips"].str.len() == 5]
        df = df[~df["area_fips"].str.startswith(("US", "C", "ST"))]

        # Coerce numerics and drop rows missing the columns we'll actually use.
        df["annual_avg_emplvl"] = pd.to_numeric(df["annual_avg_emplvl"], errors="coerce")
        df["total_annual_wages"] = pd.to_numeric(df["total_annual_wages"], errors="coerce")
        df = df.dropna(subset=["year", "annual_avg_emplvl", "total_annual_wages"])

        out = pd.DataFrame({
            "area_fips": df["area_fips"].astype(str).str.zfill(5),
            "year": df["year"].astype(int),
            "quarter": df["qtr"].fillna(0).astype(int),
            "industry_code": df["industry_code"].astype(str),
            "own_code": df["own_code"].fillna(0).astype(int),
            "employment": df["annual_avg_emplvl"].astype("int64"),
            "total_wages": df["total_annual_wages"].astype("int64"),
        })
        out["snapshot_date"] = date.today()

        con.register("_qcew_stage", out)
        con.execute("""
            INSERT OR REPLACE INTO raw_bls_qcew
            SELECT area_fips, year, quarter, industry_code, own_code,
                   employment, total_wages, snapshot_date
            FROM _qcew_stage
        """)
        con.unregister("_qcew_stage")
        return len(out)
