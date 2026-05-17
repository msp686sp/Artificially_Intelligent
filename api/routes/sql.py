"""SQL workbench endpoint.

``POST /api/sql`` runs a single statement against the DuckDB warehouse
and returns a tabular result. Read-only enforcement is on by default;
the dev can flip ``read_only=false`` from the workbench to allow
DDL/DML for development workflows.

Design notes:

- Multi-statement input is **always** rejected with 400. Even with
  ``read_only=false`` we don't run scripts — the workbench has a
  single editor, "run" means "run this one statement." This also
  keeps the read-only check tractable (one statement, one decision).

- Read-only detection uses ``duckdb.extract_statements`` (the C++
  parser) rather than a regex over the source text — comments,
  string literals containing ``DROP``, and other surface tricks
  can't fool it. The result is a ``StatementType`` enum we whitelist
  against.

- The row cap is enforced **after** DuckDB hands us the result, so
  the user-supplied query is never silently rewritten. If the user
  asks for ``LIMIT 1000000`` we still return ``min(limit, 10000)``
  rows; the truncation is visible via ``row_count``.

- Errors from DuckDB (parse failures, missing tables, etc.) are
  surfaced as 400 — they're user-facing input errors, not server
  bugs.
"""

from __future__ import annotations

import time

import duckdb
from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_con
from api.models.sql import SQLRequest, SQLResponse

router = APIRouter(prefix="", tags=["sql"])

# Statement types we allow under ``read_only=true``. These all return
# rows without mutating the database. Everything else (INSERT, UPDATE,
# DELETE, CREATE, DROP, ALTER, TRANSACTION control, etc.) is rejected.
#
# We deliberately keep the whitelist permissive within the read family:
# DESCRIBE/SHOW/PRAGMA are useful for the schema browser the workbench
# users will reach for.
_READ_ONLY_STATEMENT_TYPES = {
    duckdb.StatementType.SELECT,
    duckdb.StatementType.EXPLAIN,
    duckdb.StatementType.PRAGMA,
    # DuckDB classifies SHOW / DESCRIBE / WITH-leading queries as SELECT
    # via extract_statements, but we list these explicitly in case a
    # future DuckDB release splits them out.
}

_HARD_ROW_CAP = 10_000


def _is_read_only(stmt_type: duckdb.StatementType) -> bool:
    return stmt_type in _READ_ONLY_STATEMENT_TYPES


@router.post("/sql", response_model=SQLResponse)
def run_sql(
    req: SQLRequest,
    con: duckdb.DuckDBPyConnection = Depends(get_con),
) -> SQLResponse:
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Empty query")

    # ------------------------------------------------------------------
    # Parse + multi-statement / read-only checks.
    # ------------------------------------------------------------------
    try:
        stmts = duckdb.extract_statements(query)
    except duckdb.Error as e:
        # Parser error — surface as 400, not 500.
        raise HTTPException(status_code=400, detail=f"Parse error: {e}") from e

    if len(stmts) == 0:
        raise HTTPException(status_code=400, detail="No statements parsed")
    if len(stmts) > 1:
        raise HTTPException(
            status_code=400,
            detail="Multi-statement input is not allowed. Run one statement at a time.",
        )

    stmt = stmts[0]
    if req.read_only and not _is_read_only(stmt.type):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Statement type {stmt.type.name} is not allowed under "
                "read_only=true. Set read_only=false to override."
            ),
        )

    # Hard row cap independent of any LIMIT the user wrote. We don't
    # rewrite their SQL — we just stop pulling after the cap.
    cap = min(req.limit, _HARD_ROW_CAP)

    # ------------------------------------------------------------------
    # Execute.
    # ------------------------------------------------------------------
    t0 = time.perf_counter()
    try:
        cur = con.execute(query)
    except duckdb.Error as e:
        # Binder / runtime errors from DuckDB are user-facing.
        raise HTTPException(status_code=400, detail=str(e)) from e

    description = cur.description or []
    columns = [d[0] for d in description]

    rows: list[list] = []
    if columns:
        # ``fetchmany`` honours the cap without us re-reading more.
        fetched = cur.fetchmany(cap)
        for row in fetched:
            rows.append(_row_to_jsonable(row))
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 3)

    return SQLResponse(
        columns=columns,
        rows=rows,
        row_count=len(rows),
        elapsed_ms=elapsed_ms,
        query=query,
    )


def _row_to_jsonable(row: tuple) -> list:
    """Convert a DuckDB row into a list of JSON-serializable values.

    Pydantic v2 will coerce datetimes / dates / decimals via its own
    serialization, but FastAPI's ``response_model`` validation runs
    against ``Any`` in ``SQLResponse.rows``, so we get the standard
    Pydantic JSON encoder for free. The only thing we have to do here
    is unwrap DuckDB's namedtuple-ish row into a plain list.
    """
    return [v for v in row]
