"""Pydantic v2 response/request models shared across routes.

Each route module may declare its own models locally; the ones here are
re-used in more than one place or returned by the core (agent-1) routes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ----------------------------------------------------------------------
# health / version
# ----------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])
    version: str
    uptime_s: float


class VersionResponse(BaseModel):
    api: str
    app: str
    python: str


# ----------------------------------------------------------------------
# sources
# ----------------------------------------------------------------------


class SourceSummary(BaseModel):
    """One row of ``GET /api/sources``."""

    name: str
    status: str = Field(
        ...,
        description='Manifest status: "ok", "error", or "never" if no refresh recorded.',
    )
    last_refresh: datetime | None = None
    rows_loaded: int | None = Field(
        default=None,
        description="Rows reported by the most recent refresh (manifest).",
    )
    warehouse_rows: int | None = Field(
        default=None,
        description="Row count in the warehouse table; None if the table is missing.",
    )
    error: str | None = None
    source_url: str | None = None
    license: str | None = None
    cadence: str | None = None


class SourceDetail(SourceSummary):
    """``GET /api/sources/{name}`` — currently the same shape as the summary."""


class SourceColumn(BaseModel):
    name: str
    type: str
    nullable: bool = True


class SourceSchema(BaseModel):
    """``GET /api/sources/{name}/schema``."""

    source: str
    table: str
    columns: list[SourceColumn]


class SourcePreview(BaseModel):
    """``GET /api/sources/{name}/preview``."""

    source: str
    table: str
    columns: list[str]
    rows: list[dict[str, Any]]
    limit: int
    offset: int
    row_count: int = Field(..., description="Total rows in the warehouse table.")


class RefreshAccepted(BaseModel):
    """``POST /api/sources/{name}/refresh`` — async kickoff."""

    job_id: str
    source: str
    from_fixture: str | None = None


class RefreshRequest(BaseModel):
    from_fixture: str | None = Field(
        default=None,
        description="Optional path to a local fixture file to load instead of fetching.",
    )


# ----------------------------------------------------------------------
# manifest
# ----------------------------------------------------------------------


class ManifestEntryModel(BaseModel):
    source: str
    last_refresh: datetime
    rows_loaded: int
    status: str
    error: str | None = None


class ManifestResponse(BaseModel):
    entries: list[ManifestEntryModel]


# ----------------------------------------------------------------------
# schema (warehouse tree)
# ----------------------------------------------------------------------


class SchemaColumn(BaseModel):
    name: str
    type: str
    nullable: bool = True


class SchemaTable(BaseModel):
    kind: str  # "table" or "view"
    name: str
    columns: list[SchemaColumn]
    row_count: int | None = None


class SchemaResponse(BaseModel):
    tables: list[SchemaTable]


# Re-exports for convenience.
__all__ = [
    "HealthResponse",
    "ManifestEntryModel",
    "ManifestResponse",
    "RefreshAccepted",
    "RefreshRequest",
    "SchemaColumn",
    "SchemaResponse",
    "SchemaTable",
    "SourceColumn",
    "SourceDetail",
    "SourcePreview",
    "SourceSchema",
    "SourceSummary",
    "VersionResponse",
]
