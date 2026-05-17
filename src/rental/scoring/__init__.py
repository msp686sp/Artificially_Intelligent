"""Scoring layer: per-dimension sub-scores combined into MarketScore.

Phase 3 ships the SupplyScore. Other sub-scores land in their own phases.
"""

from rental.scoring.supply_score import compute_supply_score

__all__ = ["compute_supply_score"]
