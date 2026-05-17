"""DuckDB connection + schema bootstrap."""

from pathlib import Path

import duckdb

from rental.config import WAREHOUSE_PATH

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def connect(path: Path | None = None) -> duckdb.DuckDBPyConnection:
    target = path or WAREHOUSE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(target))


def init_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(SCHEMA_PATH.read_text())
