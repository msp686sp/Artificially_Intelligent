"""Shared fixtures for API tests.

Provides:
- ``warehouse_path`` — tmp DuckDB warehouse, schema initialized + ZHVI
  fixture loaded so source-detail / preview / schema tests have data.
- ``client`` — synchronous ``starlette.testclient.TestClient`` bound to
  the test warehouse via the ``RENTAL_WAREHOUSE_PATH`` env var.

The ``RENTAL_MANIFEST_PATH`` env-isolation is inherited from the
repo-root ``tests/conftest.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rental.db import connect, init_schema
from rental.sources import ZillowZHVISource

REPO_ROOT = Path(__file__).resolve().parents[2]
ZHVI_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "zhvi_sample.csv"


@pytest.fixture
def warehouse_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fresh DuckDB warehouse seeded with the bundled ZHVI fixture."""
    target = tmp_path / "warehouse.duckdb"
    monkeypatch.setenv("RENTAL_WAREHOUSE_PATH", str(target))

    con = connect(target)
    try:
        init_schema(con)
        # Seed one source so /sources/{name}/preview has rows to return.
        ZillowZHVISource().refresh(con, tmp_path / "raw", from_fixture=ZHVI_FIXTURE)
    finally:
        con.close()
    return target


@pytest.fixture
def client(warehouse_path: Path) -> TestClient:
    """TestClient against a freshly built app bound to the test warehouse.

    We rebuild the app per-test (via ``create_app``) so the cached
    settings + DuckDB connections always see the test env vars.
    """
    # Reset the module-level Settings singleton so the new env vars stick.
    from api import deps as api_deps

    api_deps._settings = None  # type: ignore[attr-defined]

    from api.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c
