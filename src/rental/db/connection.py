"""DuckDB connection + schema bootstrap."""

from pathlib import Path

import duckdb

from rental import config

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def connect(path: Path | None = None) -> duckdb.DuckDBPyConnection:
    # Re-resolve at call time so RENTAL_WAREHOUSE_PATH env-var overrides set
    # after module import (e.g. by tests) take effect.
    target = path or config._resolve_warehouse_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(target))


def init_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(SCHEMA_PATH.read_text())
