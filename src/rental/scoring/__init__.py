"""Sub-score modules per dimension, plus the composite.

Phases:
  1  YieldScore        (yield_features  -> yield_score)
  2  DemandScore       (demand_features -> demand_score)
  3  SupplyScore       (supply_features -> compute_supply_score)
  4  OperabilityScore  (operability_features -> operability_score)
     RiskScore         (risk_features        -> risk_score)
  5  MarketScore       (composite: compute_market_score)
"""

from pathlib import Path

import duckdb

from rental.scoring.composite import compute_market_score, load_market_weights
from rental.scoring.demand_score import demand_score
from rental.scoring.normalize import zscore_within_state
from rental.scoring.operability_score import operability_score
from rental.scoring.risk_score import risk_score
from rental.scoring.supply_score import compute_supply_score
from rental.scoring.yield_score import yield_score

VIEW_SQL_PATH = Path(__file__).parent / "zip_view.sql"


def init_composite_views(con: duckdb.DuckDBPyConnection) -> None:
    """Create/refresh the composite-layer views. Idempotent."""
    con.execute(VIEW_SQL_PATH.read_text())


__all__ = [
    "compute_market_score",
    "compute_supply_score",
    "demand_score",
    "init_composite_views",
    "load_market_weights",
    "operability_score",
    "risk_score",
    "yield_score",
    "zscore_within_state",
]
