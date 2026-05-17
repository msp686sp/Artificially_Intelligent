"""Models for the rankings endpoint."""

from __future__ import annotations

from pydantic import BaseModel


class RankingRow(BaseModel):
    """One row in the rankings response.

    ``market_score`` is the composite; the five sub-scores are surfaced
    so the frontend can render the breakdown without a second fetch.
    Identity columns (state/metro/county_name) come from the underlying
    ``zip_scores`` table.
    """

    zcta5: str
    state: str | None = None
    metro: str | None = None
    county_name: str | None = None
    market_score: float | None = None
    yield_score: float | None = None
    demand_score: float | None = None
    supply_score: float | None = None
    operability_score: float | None = None
    risk_score: float | None = None


class RankingsResponse(BaseModel):
    total: int
    rows: list[RankingRow]
