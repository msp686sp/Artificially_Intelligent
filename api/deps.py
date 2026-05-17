"""Shared FastAPI dependencies (connection factory, settings).

Agent 1 (api-core) owns the canonical version. This file is the minimal
seam Agent 2 (api-sql-rankings) needs so its routes can declare a
DuckDB connection dependency without colliding with Agent 1.

Resolution order at merge time:
- If Agent 1 ships a richer ``get_con`` that returns a pooled / cached
  connection, this file is replaced wholesale.
- Until then, ``get_con`` opens (and tears down) one DuckDB connection
  per request against the warehouse path resolved from
  ``rental.config._resolve_warehouse_path``. That keeps tests
  trivially isolatable: set ``RENTAL_WAREHOUSE_PATH`` to a tmpfile and
  the route picks it up on the next request.
"""

from __future__ import annotations

from collections.abc import Iterator

import duckdb

from rental.config import _resolve_warehouse_path
from rental.db import init_schema
from rental.scoring import init_composite_views


def get_con() -> Iterator[duckdb.DuckDBPyConnection]:
    """Open a DuckDB connection bootstrapped with the project schema.

    Schema init is idempotent (``CREATE TABLE IF NOT EXISTS`` for every
    table and ``CREATE OR REPLACE VIEW`` for every composite view), so
    calling it on every request is cheap and means the route layer
    works against fresh warehouses without a separate setup step.
    """
    target = _resolve_warehouse_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(target))
    try:
        init_schema(con)
        init_composite_views(con)
        yield con
    finally:
        con.close()
