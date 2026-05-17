"""IRS SOI county-to-county migration — annual, ~2-year lag.

Source landing page (lists each year's files):
  https://www.irs.gov/statistics/soi-tax-stats-migration-data

Files are named ``countyinflow{YYYY}.csv`` and ``countyoutflow{YYYY}.csv``
where the 4-digit YYYY is the tax-year pair (e.g. ``countyinflow1920.csv``
covers filers who moved between TY2019 and TY2020 — we represent that
as ``year=2020``).

Inflow column shape (IRS publishes a consistent layout across years):
  y2_statefips, y2_countyfips, y1_statefips, y1_countyfips,
  y1_state, y1_countyname, n1, n2, AGI
where (y2_*) is the destination (current year) and (y1_*) is origin.
Outflow files swap origin/destination semantics.

License: U.S. Government work, public domain.
Cadence: annual, lands ~24 months after the second tax year ends.

Network note: in this repo's sandboxed CI, outbound to irs.gov is
blocked. ``fetch()`` is wired against the real public URL for local
refreshes; tests load a bundled CSV fixture matching this layout.
"""

from __future__ import annotations

import io
from datetime import date
from pathlib import Path

import duckdb
import httpx
import pandas as pd

from rental.sources.base import Source

# Files land in per-year subdirectories under the SOI Migration data page.
# Two patterns have been seen historically; we try them in order. Year-pair
# tokens look like ``1920`` for TY2019→TY2020.
IRS_URL_TEMPLATES = (
    "https://www.irs.gov/pub/irs-soi/county{direction}{pair}.csv",
    "https://www.irs.gov/pub/irs-soi/county{direction}{pair}all.csv",
)


def _pair_for_year(end_year: int) -> str:
    """Return the IRS file-name suffix for the migration end-year.

    end_year=2020 → "1920" (TY2019 → TY2020 transition).
    """
    return f"{(end_year - 1) % 100:02d}{end_year % 100:02d}"


class IRSMigrationSource(Source):
    """IRS SOI county inflow + outflow merged into a single tall table."""

    name = "irs_migration"

    def fetch(self, raw_dir: Path) -> Path:
        """Pull the most recent published inflow + outflow files and merge.

        Walks back from the current calendar year until both an inflow
        and outflow file are reachable. Writes a single merged CSV.
        """
        raw_dir.mkdir(parents=True, exist_ok=True)
        today = date.today()

        for end_year in range(today.year - 1, today.year - 6, -1):
            pair = _pair_for_year(end_year)
            frames: list[pd.DataFrame] = []
            ok = True
            for direction in ("inflow", "outflow"):
                df = self._download_one(direction, pair)
                if df is None:
                    ok = False
                    break
                df["year"] = end_year
                df["flow_direction"] = direction
                frames.append(df)
            if ok and frames:
                merged = pd.concat(frames, ignore_index=True)
                target = raw_dir / f"irs_migration_{end_year}_{today.isoformat()}.csv"
                merged.to_csv(target, index=False)
                return target

        raise RuntimeError(
            "Could not fetch IRS migration files for any of the last 5 end-years"
        )

    def _download_one(self, direction: str, pair: str) -> pd.DataFrame | None:
        for template in IRS_URL_TEMPLATES:
            url = template.format(direction=direction, pair=pair)
            try:
                r = httpx.get(url, timeout=180, follow_redirects=True)
            except httpx.HTTPError:
                continue
            if r.status_code == 200 and r.content:
                # IRS files are sometimes latin-1 encoded.
                try:
                    return pd.read_csv(io.BytesIO(r.content), dtype=str)
                except UnicodeDecodeError:
                    return pd.read_csv(
                        io.BytesIO(r.content), dtype=str, encoding="latin-1"
                    )
        return None

    def load(self, con: duckdb.DuckDBPyConnection, raw_path: Path) -> int:
        df = pd.read_csv(raw_path, dtype=str)

        required = {"year", "flow_direction", "n1", "n2", "AGI"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(
                f"irs_migration fixture is missing required columns: {sorted(missing)}"
            )

        # IRS Migration layout (both inflow and outflow files):
        #   y1_* = origin (prior-year residence)
        #   y2_* = destination (current-year residence)
        # The file name (inflow vs outflow) only changes which side is the
        # subject county; the column orientation is consistent.
        def _fips(state: pd.Series, county: pd.Series) -> pd.Series:
            return (
                state.fillna("").astype(str).str.zfill(2)
                + county.fillna("").astype(str).str.zfill(3)
            )

        origin_fips = _fips(
            df.get("y1_statefips", pd.Series(dtype=str)),
            df.get("y1_countyfips", pd.Series(dtype=str)),
        )
        dest_fips = _fips(
            df.get("y2_statefips", pd.Series(dtype=str)),
            df.get("y2_countyfips", pd.Series(dtype=str)),
        )

        out = pd.DataFrame({
            "year": pd.to_numeric(df["year"], errors="coerce").astype("Int64"),
            "flow_direction": df["flow_direction"].str.lower(),
            "origin_fips": origin_fips,
            "dest_fips": dest_fips,
            "returns": pd.to_numeric(df["n1"], errors="coerce").astype("Int64"),
            "exemptions": pd.to_numeric(df["n2"], errors="coerce").astype("Int64"),
            "agi": pd.to_numeric(df["AGI"], errors="coerce").astype("Int64"),
        })
        out = out.dropna(subset=["year", "returns"])
        out["year"] = out["year"].astype(int)
        out["returns"] = out["returns"].astype("int64")
        out["exemptions"] = out["exemptions"].fillna(0).astype("int64")
        out["agi"] = out["agi"].fillna(0).astype("int64")
        out["snapshot_date"] = date.today()

        con.register("_irs_stage", out)
        con.execute("""
            INSERT OR REPLACE INTO raw_irs_migration
            SELECT year, flow_direction, origin_fips, dest_fips,
                   returns, exemptions, agi, snapshot_date
            FROM _irs_stage
        """)
        con.unregister("_irs_stage")
        return len(out)


