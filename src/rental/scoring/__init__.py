"""Scoring: sub-score normalization + composite MarketScore.

Phase 5 ships the composite layer. Individual sub-score producers
(yield, demand, supply, operability, risk) live in their own modules
and write to the `zip_scores` table; the composite reads from there.
"""

from pathlib import Path

import duckdb

from rental.scoring.composite import compute_market_score, load_market_weights
from rental.scoring.normalize import zscore_within_state

VIEW_SQL_PATH = Path(__file__).parent / "zip_view.sql"


def init_composite_views(con: duckdb.DuckDBPyConnection) -> None:
    """Create/refresh the composite-layer views.

    Idempotent (CREATE OR REPLACE VIEW). Safe to call after init_schema.
    """
    con.execute(VIEW_SQL_PATH.read_text())


__all__ = [
    "compute_market_score",
    "init_composite_views",
    "load_market_weights",
    "zscore_within_state",
]
