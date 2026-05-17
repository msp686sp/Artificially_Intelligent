"""Redfin Data Center weekly/monthly market tracker, by ZIP.

Public gzipped TSV at:
  https://redfin-public-data.s3.us-west-2.amazonaws.com/
    redfin_market_tracker/zip_code_market_tracker.tsv000.gz

Cadence: Redfin Data Center refreshes weekly; the zip-code-level file is
the broadest free zip grain for days-on-market, sale-to-list ratio,
inventory, new listings, median sale price, and homes sold.

License: Redfin Data Center data is published free for personal and
non-commercial research use under Redfin's terms at
https://www.redfin.com/news/data-center/. Attribution required for any
publication. We treat this as a read-only feed and never republish raw
rows from this loader.

Source columns we keep (TSV has many more; we select the ones our
features actually need and document the contract here):

    region          — formatted "Zip Code: NNNNN" (string, padded)
    period_begin    — period start date (YYYY-MM-DD)
    period_end      — period end date (YYYY-MM-DD)
    median_dom              -> median_dom         (number of days)
    median_sale_to_list_ratio -> median_sale_to_list (e.g., 0.985)
    inventory                                       (active listings)
    new_listings
    median_sale_price
    homes_sold

The fetch path streams the gzipped TSV from Redfin's S3 bucket and
parses with pandas. In this repo's sandboxed CI, outbound to that
bucket is blocked (host_not_allowed). Tests therefore drive ``load``
against a small uncompressed TSV fixture; ``refresh(from_fixture=...)``
is the entry point in test mode.

Schema mirrored into ``raw_redfin_market`` (defined in schema.sql):
    zcta5, period_begin, period_end, median_dom,
    median_sale_to_list, inventory, new_listings,
    median_sale_price, homes_sold, snapshot_date
"""

from datetime import date
from pathlib import Path

import duckdb
import httpx
import pandas as pd

from rental.sources.base import Source

REDFIN_ZIP_URL = (
    "https://redfin-public-data.s3.us-west-2.amazonaws.com/"
    "redfin_market_tracker/zip_code_market_tracker.tsv000.gz"
)

# Columns we keep from the source TSV. Redfin ships many more (off-market
# variants, YoY deltas, etc.); we recompute the deltas we need from the
# raw level series so any future schema drift in those derived columns
# won't silently break our features.
_SOURCE_COLS = [
    "region",
    "period_begin",
    "period_end",
    "median_dom",
    "median_sale_to_list",
    "inventory",
    "new_listings",
    "median_sale_price",
    "homes_sold",
]


def _extract_zcta5(region: str) -> str | None:
    """Pull the 5-digit zip out of Redfin's ``"Zip Code: 10025"`` format.

    Returns None when the value doesn't parse — caller drops those rows.
    Defensive against trailing whitespace and bare integer fixtures.
    """
    if region is None:
        return None
    text = str(region).strip()
    if not text:
        return None
    # The canonical Redfin shape is "Zip Code: NNNNN"; fixtures may also
    # ship a bare integer/string for compactness.
    if ":" in text:
        text = text.split(":", 1)[1].strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return None
    return digits.zfill(5)[:5]


class RedfinMarketSource(Source):
    """Zip-code-level Redfin Data Center market tracker."""

    name = "redfin_market"

    def fetch(self, raw_dir: Path) -> Path:
        """Stream and persist the gzipped zip-code TSV to ``raw_dir``.

        Redfin's S3 endpoint serves a large (~hundreds of MB) gzipped
        file. We stream chunks to disk; the load step lets pandas
        handle gunzip + TSV parsing in one shot.
        """
        raw_dir.mkdir(parents=True, exist_ok=True)
        target = raw_dir / f"redfin_zip_{date.today().isoformat()}.tsv.gz"
        with httpx.stream("GET", REDFIN_ZIP_URL, timeout=600, follow_redirects=True) as r:
            r.raise_for_status()
            with target.open("wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
        return target

    def load(self, con: duckdb.DuckDBPyConnection, raw_path: Path) -> int:
        # pandas auto-detects gzip from the .gz suffix; uncompressed
        # fixtures (no suffix) round-trip the same code path.
        compression = "gzip" if str(raw_path).endswith(".gz") else None
        df = pd.read_csv(
            raw_path,
            sep="\t",
            compression=compression,
            dtype={"region": str},
            low_memory=False,
        )

        missing = [c for c in _SOURCE_COLS if c not in df.columns]
        if missing:
            raise ValueError(
                f"redfin_market fixture is missing required columns: {missing}"
            )

        df = df[_SOURCE_COLS].copy()
        df["zcta5"] = df["region"].map(_extract_zcta5)
        df = df.dropna(subset=["zcta5"])
        df = df.drop(columns=["region"])

        df["period_begin"] = pd.to_datetime(df["period_begin"], errors="coerce").dt.date
        df["period_end"] = pd.to_datetime(df["period_end"], errors="coerce").dt.date
        df = df.dropna(subset=["period_begin", "period_end"])

        for col in [
            "median_dom",
            "median_sale_to_list",
            "inventory",
            "new_listings",
            "median_sale_price",
            "homes_sold",
        ]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df["snapshot_date"] = date.today()

        con.register("_redfin_stage", df)
        con.execute("""
            INSERT OR REPLACE INTO raw_redfin_market
            SELECT zcta5, period_begin, period_end,
                   median_dom, median_sale_to_list, inventory,
                   new_listings, median_sale_price, homes_sold,
                   snapshot_date
            FROM _redfin_stage
        """)
        con.unregister("_redfin_stage")
        return len(df)
