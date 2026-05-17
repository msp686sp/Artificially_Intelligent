"""FEMA National Risk Index (NRI), county-level.

Public CSV at:
  https://hazards.fema.gov/nri/Content/StaticDocuments/DataDownload/
    NRI_Table_Counties.csv

The NRI CSV is wide: one row per county with state-level FIPS + many
per-hazard sub-scores. We keep the composite ``RISK_SCORE`` plus four
hazard-specific scores most relevant to SFR cash flow risk:
  - flood (CFLD_RISKS / RFLD_RISKS, we pick coastal+riverine combined via
    RISK_SCORE for "FLOOD" composite when present, else the riverine score)
  - wildfire (WFIR_RISKS)
  - hurricane (HRCN_RISKS)
  - heatwave (HWAV_RISKS)

License: FEMA NRI is public domain; attribution requested.
Cadence: roughly annual major releases; FEMA updates the static CSV in
place. Refresh once a year.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import httpx
import pandas as pd

from rental.sources.base import Source

NRI_URL = (
    "https://hazards.fema.gov/nri/Content/StaticDocuments/"
    "DataDownload/NRI_Table_Counties.csv"
)

# Column aliases. NRI release versions have flip-flopped between *_RISKS and
# *_RISKR over the years; we accept both.
_HAZARD_COLS = {
    "flood_score": ("RFLD_RISKS", "CFLD_RISKS", "RFLD_RISKR"),
    "wildfire_score": ("WFIR_RISKS", "WFIR_RISKR"),
    "hurricane_score": ("HRCN_RISKS", "HRCN_RISKR"),
    "heatwave_score": ("HWAV_RISKS", "HWAV_RISKR"),
}
_COMPOSITE_COLS = ("RISK_SCORE", "RISK_SCOR")


def _first_present(df: pd.DataFrame, candidates: tuple[str, ...]) -> pd.Series | None:
    for c in candidates:
        if c in df.columns:
            return pd.to_numeric(df[c], errors="coerce")
    return None


def _county_fips_from_row(df: pd.DataFrame) -> pd.Series:
    if "STCOFIPS" in df.columns:
        return df["STCOFIPS"].astype(str).str.zfill(5)
    # Fall back to state + county sub-parts.
    state = df["STATEFIPS"].astype(str).str.zfill(2)
    county = df["COUNTYFIPS"].astype(str).str.zfill(3)
    return state + county


class FemaNriSource(Source):
    name = "fema_nri"

    def fetch(self, raw_dir: Path) -> Path:
        raw_dir.mkdir(parents=True, exist_ok=True)
        target = raw_dir / f"fema_nri_{date.today().isoformat()}.csv"
        with httpx.stream("GET", NRI_URL, timeout=300, follow_redirects=True) as r:
            r.raise_for_status()
            with target.open("wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
        return target

    def load(self, con: duckdb.DuckDBPyConnection, raw_path: Path) -> int:
        df = pd.read_csv(raw_path, dtype=str, low_memory=False)

        out = pd.DataFrame({"county_fips": _county_fips_from_row(df)})
        composite = _first_present(df, _COMPOSITE_COLS)
        out["risk_index_score"] = composite if composite is not None else pd.NA
        for col, candidates in _HAZARD_COLS.items():
            series = _first_present(df, candidates)
            out[col] = series if series is not None else pd.NA

        out["snapshot_date"] = date.today()
        # Drop rows with no scores at all (e.g., empty trailing rows).
        score_cols = ["risk_index_score", "flood_score", "wildfire_score",
                      "hurricane_score", "heatwave_score"]
        out = out.dropna(subset=score_cols, how="all")

        con.register("_fema_nri_stage", out)
        con.execute(
            """
            INSERT OR REPLACE INTO raw_fema_nri
            SELECT county_fips, risk_index_score, flood_score, wildfire_score,
                   hurricane_score, heatwave_score, snapshot_date
            FROM _fema_nri_stage
            """
        )
        con.unregister("_fema_nri_stage")
        return len(out)
