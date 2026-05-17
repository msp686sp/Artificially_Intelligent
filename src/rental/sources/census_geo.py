"""Census geographic spine: ZCTA gazetteer, ZCTA-to-county crosswalk, CBSA delineation.

This single source populates four geo tables in one refresh:
  - geo_zcta                (one row per ZCTA: state, population, land area)
  - geo_zcta_county_xwalk   (residential-population share per ZCTA × county)
  - geo_county              (county FIPS, state, name, CBSA membership)
  - geo_cbsa                (CBSA code, name, type)

Public URLs (free, no license restrictions; refresh annually):

  Gazetteer (ZCTAs, tab-separated text inside zip):
    https://www2.census.gov/geo/docs/maps-data/data/gazetteer/
      2023_Gazetteer/2023_Gaz_zcta_national.zip

  ZCTA-to-county relationship file (2020 vintage, tab-separated text):
    https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/
      tab20_zcta520_county20_natl.txt

  CBSA delineation list (Excel, vintage Mar 2023):
    https://www2.census.gov/programs-surveys/metro-micro/geographies/
      reference-files/2023/delineation-files/list1_2023.xlsx

`fetch()` downloads all three into a fresh dated subdirectory of raw_dir
and returns the directory path. `load()` accepts either that directory
(real refresh) or a fixture directory bundled in tests/fixtures/.

In tests we substitute CSV/TSV fixtures for the CBSA xlsx because
openpyxl is not in the default dependency set; the loader auto-detects
`.csv` and `.xlsx` in the CBSA filename slot.
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

GAZETTEER_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
    "2023_Gazetteer/2023_Gaz_zcta_national.zip"
)
ZCTA_COUNTY_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/"
    "tab20_zcta520_county20_natl.txt"
)
CBSA_URL = (
    "https://www2.census.gov/programs-surveys/metro-micro/geographies/"
    "reference-files/2023/delineation-files/list1_2023.xlsx"
)

# Bundle filenames used by both the live fetch and the fixture loader.
GAZETTEER_NAME = "gaz_zcta.tsv"        # extracted from the gazetteer zip
ZCTA_COUNTY_NAME = "zcta_county.tsv"
CBSA_NAME_CSV = "cbsa.csv"             # fixture form
CBSA_NAME_XLSX = "cbsa.xlsx"           # real download form


class CensusGeoSource(Source):
    name = "census_geo"

    def fetch(self, raw_dir: Path) -> Path:
        out = raw_dir / f"census_geo_{date.today().isoformat()}"
        out.mkdir(parents=True, exist_ok=True)

        # Gazetteer: zipped TSV. Extract the single .txt inside.
        with httpx.stream("GET", GAZETTEER_URL, timeout=180, follow_redirects=True) as r:
            r.raise_for_status()
            buf = io.BytesIO()
            for chunk in r.iter_bytes():
                buf.write(chunk)
        with zipfile.ZipFile(buf) as zf:
            inner = next(n for n in zf.namelist() if n.lower().endswith(".txt"))
            (out / GAZETTEER_NAME).write_bytes(zf.read(inner))

        # ZCTA-county relationship file: plain TSV.
        with httpx.stream(
            "GET", ZCTA_COUNTY_URL, timeout=180, follow_redirects=True
        ) as r:
            r.raise_for_status()
            with (out / ZCTA_COUNTY_NAME).open("wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)

        # CBSA delineation: Excel.
        with httpx.stream("GET", CBSA_URL, timeout=180, follow_redirects=True) as r:
            r.raise_for_status()
            with (out / CBSA_NAME_XLSX).open("wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
        return out

    def load(self, con: duckdb.DuckDBPyConnection, raw_path: Path) -> int:
        if not raw_path.is_dir():
            raise ValueError(
                f"CensusGeoSource expects a directory of three files, got {raw_path}"
            )

        rows = 0
        rows += self._load_gazetteer(con, raw_path / GAZETTEER_NAME)
        rows += self._load_zcta_county(con, raw_path / ZCTA_COUNTY_NAME)
        rows += self._load_cbsa(con, raw_path)
        return rows

    # ----- per-file loaders -------------------------------------------------

    @staticmethod
    def _load_gazetteer(con: duckdb.DuckDBPyConnection, path: Path) -> int:
        # The Census gazetteer is tab-separated, UTF-8, with a header row.
        # Real columns: GEOID, ALAND, AWATER, ALAND_SQMI, AWATER_SQMI,
        # INTPTLAT, INTPTLONG (no state, no population — they're tract-level
        # joins elsewhere). The fixture mirrors a minimal superset that
        # also includes state + population so we can populate geo_zcta in
        # one shot without a separate ACS pull.
        df = pd.read_csv(path, sep="\t", dtype={"GEOID": str})
        df.columns = [c.strip() for c in df.columns]
        df["zcta5"] = df["GEOID"].astype(str).str.zfill(5)
        # Optional columns with safe fallbacks so the loader works against
        # both the bare census file and our enriched fixture.
        df["state"] = df.get("STATE", pd.Series([None] * len(df)))
        df["population"] = pd.to_numeric(
            df.get("POPULATION", pd.Series([None] * len(df))), errors="coerce"
        )
        df["aland_sqmi"] = pd.to_numeric(
            df.get("ALAND_SQMI", pd.Series([None] * len(df))), errors="coerce"
        )
        stage = df[["zcta5", "state", "population", "aland_sqmi"]]

        con.register("_gaz_stage", stage)
        con.execute("""
            INSERT OR REPLACE INTO geo_zcta
            SELECT zcta5, state, CAST(population AS INTEGER), aland_sqmi
            FROM _gaz_stage
        """)
        con.unregister("_gaz_stage")
        return len(stage)

    @staticmethod
    def _load_zcta_county(con: duckdb.DuckDBPyConnection, path: Path) -> int:
        # Real file columns include GEOID_ZCTA5_20, GEOID_COUNTY_20,
        # AREALAND_PART, POPPT, plus population/area totals used to
        # compute res_ratio = POPPT / total ZCTA pop.
        df = pd.read_csv(path, sep="\t", dtype=str)
        df.columns = [c.strip() for c in df.columns]

        zcta_col = _first_present(df, ["GEOID_ZCTA5_20", "ZCTA5", "zcta5"])
        county_col = _first_present(df, ["GEOID_COUNTY_20", "COUNTY", "county_fips"])
        # Population in the ZCTA × county intersection.
        poppt_col = _first_present(
            df, ["POPPT", "POP_COU", "POPULATION_PART", "poppt"]
        )
        # Population in the whole ZCTA (the denominator).
        popz_col = _first_present(df, ["POP_2020", "POPZCTA", "POP_ZCTA", "popz"])

        df["zcta5"] = df[zcta_col].astype(str).str.zfill(5)
        df["county_fips"] = df[county_col].astype(str).str.zfill(5)
        df["_poppt"] = pd.to_numeric(df[poppt_col], errors="coerce").fillna(0)
        df["_popz"] = pd.to_numeric(df[popz_col], errors="coerce").fillna(0)
        df["res_ratio"] = (df["_poppt"] / df["_popz"]).where(df["_popz"] > 0, 0.0)

        stage = df[["zcta5", "county_fips", "res_ratio"]]
        con.register("_xwalk_stage", stage)
        con.execute("""
            INSERT OR REPLACE INTO geo_zcta_county_xwalk
            SELECT zcta5, county_fips, res_ratio FROM _xwalk_stage
        """)
        con.unregister("_xwalk_stage")
        return len(stage)

    @staticmethod
    def _load_cbsa(con: duckdb.DuckDBPyConnection, raw_dir: Path) -> int:
        # Accept either an xlsx (live download) or a csv (fixture).
        xlsx_path = raw_dir / CBSA_NAME_XLSX
        csv_path = raw_dir / CBSA_NAME_CSV
        if xlsx_path.exists():
            # Real list1 has 2 header rows of preamble; pandas with header=2.
            df = pd.read_excel(xlsx_path, header=2, dtype=str)
        elif csv_path.exists():
            df = pd.read_csv(csv_path, dtype=str)
        else:
            raise FileNotFoundError(
                f"No CBSA file found in {raw_dir} (looked for "
                f"{CBSA_NAME_XLSX} or {CBSA_NAME_CSV})"
            )
        df.columns = [c.strip() for c in df.columns]

        cbsa_code_col = _first_present(df, ["CBSA Code", "cbsa_code", "CBSA"])
        cbsa_name_col = _first_present(
            df, ["CBSA Title", "cbsa_name", "CBSA_NAME"]
        )
        cbsa_type_col = _first_present(
            df, ["Metropolitan/Micropolitan Statistical Area", "cbsa_type"]
        )
        state_col = _first_present(df, ["FIPS State Code", "state_fips", "STATEFP"])
        county_col = _first_present(df, ["FIPS County Code", "county_fips_3", "COUNTYFP"])
        county_name_col = _first_present(
            df, ["County/County Equivalent", "county_name", "COUNTY_NAME"]
        )
        state_abbr_col = _first_present(
            df, ["State Name", "state", "STATE_NAME"], required=False
        )

        # geo_cbsa: dedupe on cbsa_code.
        cbsa_df = df[[cbsa_code_col, cbsa_name_col, cbsa_type_col]].dropna(
            subset=[cbsa_code_col]
        )
        cbsa_df = cbsa_df.drop_duplicates(subset=[cbsa_code_col])
        cbsa_df = cbsa_df.rename(columns={
            cbsa_code_col: "cbsa_code",
            cbsa_name_col: "cbsa_name",
            cbsa_type_col: "cbsa_type",
        })
        con.register("_cbsa_stage", cbsa_df)
        con.execute("""
            INSERT OR REPLACE INTO geo_cbsa
            SELECT cbsa_code, cbsa_name, cbsa_type FROM _cbsa_stage
        """)
        con.unregister("_cbsa_stage")

        # geo_county: build 5-digit FIPS by concatenating state + county codes.
        county_df = df.copy()
        county_df["county_fips"] = (
            county_df[state_col].astype(str).str.zfill(2)
            + county_df[county_col].astype(str).str.zfill(3)
        )
        county_df["state"] = (
            county_df[state_abbr_col] if state_abbr_col else None
        )
        county_df = county_df.rename(columns={
            county_name_col: "county_name",
            cbsa_code_col: "cbsa_code",
        })
        # population not in this file; left NULL.
        county_df["population"] = None
        county_df = county_df[
            ["county_fips", "state", "county_name", "cbsa_code", "population"]
        ].drop_duplicates(subset=["county_fips"])
        con.register("_county_stage", county_df)
        con.execute("""
            INSERT OR REPLACE INTO geo_county
            SELECT county_fips, state, county_name, cbsa_code,
                   CAST(population AS INTEGER)
            FROM _county_stage
        """)
        con.unregister("_county_stage")

        return len(cbsa_df) + len(county_df)


def _first_present(
    df: pd.DataFrame, candidates: list[str], required: bool = True
) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    if required:
        raise KeyError(
            f"None of expected columns {candidates} present in {list(df.columns)}"
        )
    return None
