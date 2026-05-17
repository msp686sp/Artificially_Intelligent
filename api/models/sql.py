"""Request / response models for the SQL workbench endpoint."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SQLRequest(BaseModel):
    """Body of ``POST /api/sql``.

    The frontend SQL workbench sends one of these per "Run" click. The
    backend hard-caps the row count at ``min(limit, 10000)`` regardless
    of what the client asks for, so the response is bounded.
    """

    query: str = Field(..., description="Single SQL statement")
    limit: int = Field(
        default=1000,
        ge=1,
        le=10_000,
        description="Maximum rows returned. Hard-capped at 10,000.",
    )
    read_only: bool = Field(
        default=True,
        description=(
            "When true (default), reject any statement that DuckDB "
            "parses to a write op (INSERT/UPDATE/DELETE/CREATE/DROP/"
            "ALTER). The dev can flip this off via the workbench's "
            "explicit toggle."
        ),
    )


class SQLResponse(BaseModel):
    """Successful response from ``POST /api/sql``.

    ``rows`` is a list of lists (not list-of-dicts) to keep the wire
    format tight for large result sets; the column order is given by
    ``columns``.
    """

    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    elapsed_ms: float
    query: str
