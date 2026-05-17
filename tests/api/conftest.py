"""Shared fixtures for the agent-3 API tests.

We point the config + backtest routes at temporary directories via
the env vars they already honour (``RENTAL_CONFIG_DIR``,
``RENTAL_BACKTEST_RUNS_DIR``) so the test runs are hermetic.

These fixtures are scoped to ``tests/api/``; agent 1's broader app
fixtures will land separately and are not assumed here.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import progress
from api.main import create_app


@pytest.fixture
def tmp_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the config route at an empty tmp dir."""
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
def app(tmp_config_dir: Path, tmp_runs_dir: Path):  # noqa: ARG001 - side-effect deps
    """A fresh FastAPI app per test."""
    return create_app()


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_progress_subscribers() -> Iterator[None]:
    """Clear the pub/sub set between tests."""
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
