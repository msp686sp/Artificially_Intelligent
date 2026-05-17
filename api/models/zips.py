"""Models for the zip-detail and zip-compare endpoints."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class ZipScores(BaseModel):
    """Five sub-scores + the composite for a single zip."""

    market_score: float | None = None
    yield_score: float | None = None
    demand_score: float | None = None
    supply_score: float | None = None
    operability_score: float | None = None
    risk_score: float | None = None


class ZipIdentity(BaseModel):
    zcta5: str
    state: str | None = None
    metro: str | None = None
    county_name: str | None = None


class ZHVIPoint(BaseModel):
    date: date
    value: float | None = None


class ZORIPoint(BaseModel):
    date: date
    value: float | None = None


class RedfinPoint(BaseModel):
    """One Redfin market-tracker observation.

    Field names mirror the raw_redfin_market table so the SQL workbench
    and the chart endpoint speak the same dialect.
    """

    period_end: date
    median_dom: float | None = None
    median_sale_to_list: float | None = None
    inventory: float | None = None


class FilterStatus(BaseModel):
    """Per-filter outcome for a single zip.

    ``passes`` is True when the filter is enabled AND the zip's feature
    value satisfies the threshold. ``skipped`` is True when the filter
    is disabled in ``filters.yaml`` or the underlying feature column is
    NULL (data not available — the filter engine treats this as
    "can't decide" rather than "fails").
    """

    name: str
    passes: bool
    skipped: bool
    reason: str | None = None


class ZipDetail(BaseModel):
    """The full detail bundle for ``GET /api/zips/{zcta5}``.

    Returns empty arrays / None where data is unavailable rather than
    erroring out — the warehouse can be partially populated at any
    given time and the GUI must still render a sensible page.
    """

    identity: ZipIdentity
    scores: ZipScores
    z_scores: dict[str, float | None] = {}
    features: dict[str, float | bool | str | None] = {}
    zhvi: list[ZHVIPoint] = []
    zori: list[ZORIPoint] = []
    redfin: list[RedfinPoint] = []
    filters: list[FilterStatus] = []


class FeatureDiff(BaseModel):
    """One row in the compare-view diff matrix.

    ``values`` maps each zip in the compare set to its value for the
    feature so the frontend can render side-by-side without iterating
    over the full detail bundles.
    """

    feature: str
    values: dict[str, float | bool | str | None]


class ZipCompareResponse(BaseModel):
    zips: dict[str, ZipDetail]
    diffs: list[FeatureDiff]
