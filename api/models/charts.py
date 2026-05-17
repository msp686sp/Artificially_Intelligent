"""Models for the chart-payload endpoints.

Each chart endpoint returns a payload that the frontend's Recharts
wrappers can consume directly — no transformation on the client.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class HistogramBin(BaseModel):
    """One bar in a histogram chart.

    The frontend renders ``[bin_start, bin_end) x count`` bars; we name
    the boundary fields so it's unambiguous which side is inclusive.
    """

    bin_start: float
    bin_end: float
    count: int


class ScoreDistributionResponse(BaseModel):
    dim: str
    bins: list[HistogramBin]


class ScatterPoint(BaseModel):
    """One point in a feature-vs-score scatter."""

    zcta5: str
    x: float | None = None
    y: float | None = None


class ScatterResponse(BaseModel):
    feature: str
    score: str
    points: list[ScatterPoint]


class TimeSeriesPoint(BaseModel):
    date: date
    value: float | None = None


class RedfinSeriesPoint(BaseModel):
    period_end: date
    median_dom: float | None = None
    median_sale_to_list: float | None = None
    inventory: float | None = None
