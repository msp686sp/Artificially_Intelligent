"""Warehouse schema endpoint — exposes DuckDB ``information_schema``."""

from __future__ import annotations

import duckdb
from fastapi import APIRouter, Depends

from api.deps import get_db_ro
from api.models import SchemaColumn, SchemaResponse, SchemaTable

router = APIRouter(tags=["schema"])


def _safe_row_count(con: duckdb.DuckDBPyConnection, table: str) -> int | None:
    try:
        # Quote with double-quotes — DuckDB identifier quoting.
        row = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()
    except duckdb.Error:
        return None
    return int(row[0]) if row else 0


@router.get("/schema", response_model=SchemaResponse)
def get_schema(
    con: duckdb.DuckDBPyConnection = Depends(get_db_ro),
) -> SchemaResponse:
    """Return the warehouse tree: tables + views with column info + row counts.

    Filters to the ``main`` schema (DuckDB's default) and excludes
    information_schema/system entries.
    """
    # information_schema.tables gives kind via ``table_type``.
    tables_rows = con.execute(
        """
        SELECT table_name, table_type
        FROM information_schema.tables
        WHERE table_schema = 'main'
        ORDER BY table_name
        """
    ).fetchall()

    out: list[SchemaTable] = []
    for table_name, table_type in tables_rows:
        cols_rows = con.execute(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'main' AND table_name = ?
            ORDER BY ordinal_position
            """,
            [table_name],
        ).fetchall()
        columns = [
            SchemaColumn(
                name=name,
                type=str(dtype),
                nullable=(str(nullable).upper() != "NO"),
            )
            for name, dtype, nullable in cols_rows
        ]
        kind = "view" if str(table_type).upper() == "VIEW" else "table"
        row_count = _safe_row_count(con, table_name) if kind == "table" else None
        out.append(
            SchemaTable(
                kind=kind,
                name=table_name,
                columns=columns,
                row_count=row_count,
            )
        )
    return SchemaResponse(tables=out)
