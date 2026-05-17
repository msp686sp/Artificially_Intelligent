"""Curated reference tables. These are versioned in-repo CSVs, not refreshed
from a live source — small, stable enough to commit, and read at warehouse
init time rather than via the Source / fetch interface."""

from rental.refdata.state_insurance import (
    STATE_INSURANCE_CSV,
    load_state_insurance,
    read_state_insurance_csv,
)

__all__ = [
    "STATE_INSURANCE_CSV",
    "load_state_insurance",
    "read_state_insurance_csv",
]
