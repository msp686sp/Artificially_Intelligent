"""Loader for the bundled state-level homeowner insurance averages.

Source: NAIC "Dwelling Fire, Homeowners Owner-Occupied, and Homeowners
Tenant and Condominium / Cooperative Unit Owner's Insurance" reports
(``https://content.naic.org/cipr-topics/homeowners-insurance``). Published
annually with a ~2yr lag.

Why bundled, not refreshed: state-year HO-3 averages are a tiny table (50
rows / year) that changes slowly, and NAIC distributes them as PDFs rather
than a machine-readable feed. Re-running the ETL gains nothing; instead we
version the curated CSV in-repo (``config/state_insurance_rates.csv``) and
load it deterministically.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from rental.config import CONFIG_DIR

STATE_INSURANCE_CSV = CONFIG_DIR / "state_insurance_rates.csv"


def read_state_insurance_csv(path: Path | None = None) -> pd.DataFrame:
    """Read the bundled CSV into a DataFrame with normalized types."""
    target = path or STATE_INSURANCE_CSV
    df = pd.read_csv(target, dtype={"state": str, "policy_form": str, "source": str})
    df["state"] = df["state"].str.strip().str.upper()
    df["policy_form"] = df["policy_form"].str.strip()
    df["year"] = df["year"].astype(int)
    df["avg_annual_premium"] = df["avg_annual_premium"].astype(float)
    return df


def load_state_insurance(
    con: duckdb.DuckDBPyConnection,
    path: Path | None = None,
) -> int:
    """Load the bundled state insurance averages into ``ref_state_insurance``.

    Idempotent: uses INSERT OR REPLACE keyed on (state, year, policy_form).
    Returns the row count written.
    """
    df = read_state_insurance_csv(path)
    con.register("_state_insurance_stage", df)
    con.execute(
        """
        INSERT OR REPLACE INTO ref_state_insurance
        SELECT state, year, avg_annual_premium, policy_form, source
        FROM _state_insurance_stage
        """
    )
    con.unregister("_state_insurance_stage")
    return len(df)
