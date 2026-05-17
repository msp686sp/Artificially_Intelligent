"""Shared fixtures for API tests.

Combines agent-1's source-detail seeding, agent-2's seeded-vs-empty
client split, and agent-3's config/backtest tmpdir + progress isolation.

Fixtures:
- ``warehouse``        — tmp DuckDB warehouse, schema + composite views,
                         ZHVI + ZORI + Redfin fixtures loaded via
                         ``Source.refresh`` so manifest entries exist
- ``warehouse_path``   — alias of ``warehouse`` for older tests
- ``empty_warehouse``  — initialized but unseeded
- ``tmp_config_dir``   — empty config dir pointed at via ``RENTAL_CONFIG_DIR``
- ``tmp_runs_dir``     — empty backtest runs dir via ``RENTAL_BACKTEST_RUNS_DIR``
- ``client``           — TestClient bound to the seeded warehouse + tmp dirs
- ``empty_client``     — TestClient bound to the empty warehouse + tmp dirs
- ``app`` / ``empty_app`` — the FastAPI app instances behind those clients
- ``env_isolation``    — strips stray env state (autouse-able)

The ``RENTAL_MANIFEST_PATH`` env-isolation is inherited from the
repo-root ``tests/conftest.py``. Settings singleton is reset between
tests so env-var changes propagate.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import progress
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
def tmp_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the config route at an empty tmp dir.

    Most tests only need this set; ``test_config.py`` populates it with
    YAML files explicitly.
    """
    d = tmp_path / "config"
    d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("RENTAL_CONFIG_DIR", str(d))
    return d


@pytest.fixture
def tmp_runs_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the backtest route at an empty tmp runs dir."""
    d = tmp_path / "runs"
    d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("RENTAL_BACKTEST_RUNS_DIR", str(d))
    return d


@pytest.fixture
def warehouse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_config_dir: Path,  # noqa: ARG001 — pulls env-var setup
    tmp_runs_dir: Path,    # noqa: ARG001
) -> Path:
    """A fresh DuckDB warehouse seeded with the canonical fixture trio.

    Uses ``Source.refresh(..., from_fixture=)`` so the manifest is
    populated as a side-effect.
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


@pytest.fixture
def warehouse_path(warehouse: Path) -> Path:
    """Back-compat alias."""
    return warehouse


@pytest.fixture
def empty_warehouse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_config_dir: Path,  # noqa: ARG001
    tmp_runs_dir: Path,    # noqa: ARG001
) -> Path:
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
def app(warehouse: Path) -> FastAPI:  # noqa: ARG001 — env vars set by deps
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


@pytest.fixture(autouse=True)
def _reset_progress_subscribers() -> Iterator[None]:
    """Clear the pub/sub set between tests so events don't leak across."""
    yield
    try:
        asyncio.run(progress._reset_for_tests())
    except RuntimeError:
        # An event loop is still running (unlikely here); ignore.
        pass


@pytest.fixture
def env_isolation(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Strip stray env state that could leak between modules."""
    for var in ("RENTAL_CONFIG_DIR", "RENTAL_BACKTEST_RUNS_DIR"):
        monkeypatch.delenv(var, raising=False)
    yield
    for var in ("RENTAL_CONFIG_DIR", "RENTAL_BACKTEST_RUNS_DIR"):
        os.environ.pop(var, None)
