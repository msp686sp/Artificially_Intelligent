"""Shared fixtures for API tests.

Combines agent-1's source-detail-friendly seeding with agent-2's
seeded-vs-empty client split. Provides:

- ``warehouse``        — tmp DuckDB warehouse, schema + composite views
                         initialized, ZHVI + ZORI + Redfin fixtures loaded
                         (matches agent-1's ``warehouse_path`` + agent-2's
                         ``warehouse``)
- ``warehouse_path``   — alias of ``warehouse`` for older tests
- ``empty_warehouse``  — initialized but unseeded, for "degrades to empty"
                         tests
- ``client``           — TestClient bound to the seeded warehouse
- ``empty_client``     — TestClient bound to the empty warehouse
- ``app`` / ``empty_app`` — the FastAPI app instances behind those clients

``RENTAL_MANIFEST_PATH`` env-isolation is inherited from
``tests/conftest.py``. We reset the cached Settings between tests so
env-var changes propagate.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rental.db import init_schema
from rental.scoring import init_composite_views
from rental.sources import RedfinMarketSource, ZillowZHVISource
from rental.sources.zori import ZillowZORISource

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"


def _reset_settings_cache() -> None:
    """Drop the Settings singleton so env-var changes are visible."""
    from api import deps as api_deps

    api_deps._settings = None  # type: ignore[attr-defined]


def _make_app() -> FastAPI:
    """Build a FastAPI app with the full registered route set."""
    _reset_settings_cache()
    from api.main import create_app

    return create_app()


@pytest.fixture
def warehouse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fresh DuckDB warehouse seeded with the canonical fixture trio.

    Uses ``Source.refresh(..., from_fixture=)`` so the manifest is
    populated as a side-effect — agent-1's manifest tests rely on real
    manifest entries existing for the seeded sources.
    """
    target = tmp_path / "warehouse.duckdb"
    monkeypatch.setenv("RENTAL_WAREHOUSE_PATH", str(target))

    con = duckdb.connect(str(target))
    try:
        init_schema(con)
        init_composite_views(con)
        raw_dir = tmp_path / "raw"
        ZillowZHVISource().refresh(
            con, raw_dir, from_fixture=FIXTURES_DIR / "zhvi_sample.csv"
        )
        ZillowZORISource().refresh(
            con, raw_dir, from_fixture=FIXTURES_DIR / "zori_sample.csv"
        )
        RedfinMarketSource().refresh(
            con, raw_dir, from_fixture=FIXTURES_DIR / "redfin_market_sample.tsv"
        )
    finally:
        con.close()
    return target


# Back-compat alias for tests that named the fixture warehouse_path.
@pytest.fixture
def warehouse_path(warehouse: Path) -> Path:
    return warehouse


@pytest.fixture
def empty_warehouse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Schema-only warehouse used to verify graceful empty-state behaviour."""
    target = tmp_path / "warehouse.duckdb"
    monkeypatch.setenv("RENTAL_WAREHOUSE_PATH", str(target))
    con = duckdb.connect(str(target))
    try:
        init_schema(con)
        init_composite_views(con)
    finally:
        con.close()
    return target


@pytest.fixture
def app(warehouse: Path) -> FastAPI:  # noqa: ARG001 — env var set by warehouse
    return _make_app()


@pytest.fixture
def empty_app(empty_warehouse: Path) -> FastAPI:  # noqa: ARG001
    return _make_app()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def empty_client(empty_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(empty_app) as c:
        yield c
