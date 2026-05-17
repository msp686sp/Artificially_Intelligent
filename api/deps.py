"""Shared FastAPI dependencies — settings + DuckDB connection factories.

Connections are per-request (cheap to open, no shared mutable state).
Three flavors are exported:

- ``get_db_ro``    — read-only handle, used by query endpoints
- ``get_db_rw``    — writable handle, used by refresh endpoints
- ``get_con``      — writable handle that ALSO bootstraps the schema and
                     composite views (used by SQL/rankings/zips routes
                     so they're self-healing on a fresh warehouse)
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import duckdb
from pydantic_settings import BaseSettings, SettingsConfigDict

from rental import config as rental_config
from rental.db import init_schema
from rental.scoring import init_composite_views


class Settings(BaseSettings):
    """API settings.

    Honors the same env vars as the CLI so a developer can run the API in
    the same shell they ran ``rental refresh`` and see the same warehouse.
    """

    model_config = SettingsConfigDict(env_prefix="RENTAL_API_", extra="ignore")

    api_title: str = "Rental Market Analysis API"
    api_version: str = "0.1.0"
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",  # Vite default
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    )

    @property
    def warehouse_path(self) -> Path:
        # Re-resolve every read so tests that set ``RENTAL_WAREHOUSE_PATH``
        # via monkeypatch are honored without restarting the app.
        return rental_config._resolve_warehouse_path()

    @property
    def manifest_path(self) -> Path:
        return rental_config._resolve_manifest_path()


_settings: Settings | None = None


def get_settings() -> Settings:
    """Cached settings accessor (process-lifetime singleton)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# Process start time — used by /health for uptime_s.
START_TIME: float = time.monotonic()


def _open_connection(*, read_only: bool) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection at the configured warehouse path.

    Falls back to a writable connection if read-only open fails (e.g. the
    warehouse file does not exist yet — DuckDB cannot create files in
    ``read_only`` mode).
    """
    target = get_settings().warehouse_path
    target.parent.mkdir(parents=True, exist_ok=True)
    if read_only and target.exists():
        try:
            return duckdb.connect(str(target), read_only=True)
        except duckdb.Error:
            pass
    return duckdb.connect(str(target))


def get_db_ro() -> Iterator[duckdb.DuckDBPyConnection]:
    """Yield a read-only DuckDB connection scoped to a single request."""
    con = _open_connection(read_only=True)
    try:
        yield con
    finally:
        con.close()


def get_db_rw() -> Iterator[duckdb.DuckDBPyConnection]:
    """Yield a writable DuckDB connection scoped to a single request."""
    con = _open_connection(read_only=False)
    try:
        yield con
    finally:
        con.close()


def get_con() -> Iterator[duckdb.DuckDBPyConnection]:
    """Yield a writable connection with schema + composite views applied.

    Used by SQL / rankings / zips / charts routes so they work against
    a fresh warehouse without a separate setup step.
    """
    con = _open_connection(read_only=False)
    try:
        init_schema(con)
        init_composite_views(con)
        yield con
    finally:
        con.close()
