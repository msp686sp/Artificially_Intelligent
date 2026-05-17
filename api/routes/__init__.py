"""Route registry.

Each route module exports a top-level ``router: fastapi.APIRouter`` and is
imported below in a labeled block owned by a single agent. ``main.py``
calls ``include_all`` to attach every router to the app under ``/api``.
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI

# Agent 3 — config / backtest / events
from api.routes import backtest as _backtest

# Agent 2 — sql / rankings / zips / charts
from api.routes import charts as _charts
from api.routes import config as _config
from api.routes import events as _events

# Agent 1 — core
from api.routes import health as _health
from api.routes import manifest as _manifest
from api.routes import rankings as _rankings
from api.routes import schema as _schema
from api.routes import sources as _sources
from api.routes import sql as _sql
from api.routes import zips as _zips

_ROUTERS: list[APIRouter] = [
    # Agent 1 — core
    _health.router,
    _sources.router,
    _manifest.router,
    _schema.router,
    # Agent 2 — sql / rankings / zips / charts
    _sql.router,
    _rankings.router,
    _zips.router,
    _charts.router,
    # Agent 3 — config / backtest / events
    _config.router,
    _backtest.router,
    _events.router,
]


def include_all(app: FastAPI) -> None:
    """Attach every registered router to ``app`` under the ``/api`` prefix."""
    for router in _ROUTERS:
        app.include_router(router, prefix="/api")


# Back-compat alias for code expecting ``register_routes``.
register_routes = include_all


__all__ = ["include_all", "register_routes"]
