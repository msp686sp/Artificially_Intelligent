"""Score blocks. Each subscore is a small module returning a per-zip DataFrame."""

from rental.scoring.demand_score import demand_score

__all__ = ["demand_score"]
