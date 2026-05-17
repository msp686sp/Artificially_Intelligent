"""Shared fixtures for the agent-2 API tests.

This is the **minimal** version of the fixture set. Agent 1 (api-core)
owns the canonical conftest; once it lands the orchestrator merges the
two by taking the union of fixtures (they're disjoint by name).

What this provides:

- ``warehouse``: a tmpfile DuckDB warehouse, populated with the bundled
  ZHVI + ZORI + Redfin fixtures (so the rankings / zips / charts
  endpoints have real data to chew on).
- ``app``: a FastAPI app with just Agent 2's routes mounted. We build
  the app directly from the route registry so the tests are
  independent of merge order with agents 1 / 3.
- ``client``: ``fastapi.testclient.TestClient`` (sync, fine for these
  tests).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import register_routes
from rental.db import init_schema
from rental.scoring import init_composite_views
from rental.sources import RedfinMarketSource, ZillowZHVISource
from rental.sources.zori import ZillowZORISource

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def warehouse(tmp_path, monkeypatch) -> Iterator[Path]:
    """A seeded warehouse for the duration of one test.

    Sets ``RENTAL_WAREHOUSE_PATH`` so ``api.deps.get_con`` picks it up.
    Loads the three bundled fixtures the rankings / zips routes
    expect; other agents' raw tables remain empty (which the routes
    must tolerate).
    """
    wh = tmp_path / "warehouse.duckdb"
    monkeypatch.setenv("RENTAL_WAREHOUSE_PATH", str(wh))

    con = duckdb.connect(str(wh))
    init_schema(con)
    init_composite_views(con)
    ZillowZHVISource().load(con, FIXTURES_DIR / "zhvi_sample.csv")
    ZillowZORISource().load(con, FIXTURES_DIR / "zori_sample.csv")
    RedfinMarketSource().load(con, FIXTURES_DIR / "redfin_market_sample.tsv")
    con.close()
    yield wh


@pytest.fixture
def empty_warehouse(tmp_path, monkeypatch) -> Iterator[Path]:
    """An initialised but un-seeded warehouse.

    Used to confirm the routes degrade gracefully when no data has
    landed yet (empty arrays, not 500s).
    """
    wh = tmp_path / "warehouse.duckdb"
    monkeypatch.setenv("RENTAL_WAREHOUSE_PATH", str(wh))
    con = duckdb.connect(str(wh))
    init_schema(con)
    init_composite_views(con)
    con.close()
    yield wh


@pytest.fixture
def app(warehouse) -> FastAPI:  # noqa: ARG001 — warehouse sets the env var
    a = FastAPI()
    register_routes(a)
    return a


@pytest.fixture
def empty_app(empty_warehouse) -> FastAPI:  # noqa: ARG001
    a = FastAPI()
    register_routes(a)
    return a


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def empty_client(empty_app) -> Iterator[TestClient]:
    with TestClient(empty_app) as c:
        yield c
