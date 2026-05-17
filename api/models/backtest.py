"""Pydantic models for the ``/api/backtest/*`` endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BacktestRunRequest(BaseModel):
    """Body for ``POST /api/backtest/run``."""

    start_year: int = Field(ge=2000, le=2100)
    end_year: int = Field(ge=2000, le=2100)


class BacktestTuneRequest(BaseModel):
    """Body for ``POST /api/backtest/tune``."""

    train_start: int = Field(ge=2000, le=2100)
    train_end: int = Field(ge=2000, le=2100)
    validate_start: int = Field(ge=2000, le=2100)
    validate_end: int = Field(ge=2000, le=2100)


class BacktestJobAck(BaseModel):
    """Response for the run/tune kick-off endpoints."""

    job_id: str
    run_id: str


class BacktestRunSummary(BaseModel):
    """One row in ``GET /api/backtest/runs``."""

    id: str
    mode: str
    started_at: str
    finished_at: str | None
    status: str
    weights: dict[str, float] = Field(default_factory=dict)
    primary_metric: float | None = None
    report_path: str | None = None


class BacktestRunDetail(BaseModel):
    """Detail for ``GET /api/backtest/runs/{id}``."""

    id: str
    mode: str
    started_at: str
    finished_at: str | None
    status: str
    weights: dict[str, float] = Field(default_factory=dict)
    primary_metric: float | None = None
    report_path: str | None = None
    snapshots: list[dict[str, Any]] = Field(default_factory=list)
    quintile_bins: list[list[float]] = Field(default_factory=list)
    error: str | None = None
