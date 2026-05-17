"""Route registry.

Each route module exports a top-level ``router: fastapi.APIRouter`` and is
imported below in a labeled block owned by a single agent. ``main.py``
calls ``include_all`` to attach every router to the app.

Conflict pattern: adding/removing a route module is a single-line edit
inside the owning agent's block.
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI

# Agent 1 — core
from api.routes import health as _health
from api.routes import manifest as _manifest
from api.routes import schema as _schema
from api.routes import sources as _sources

# Agent 2 — sql / rankings / zips / charts
#   (each module exports ``router``; add imports here)

# Agent 3 — config / backtest / events (WebSocket)
#   (each module exports ``router``; add imports here)


_ROUTERS: list[APIRouter] = [
    # Agent 1 — core
    _health.router,
    _sources.router,
    _manifest.router,
    _schema.router,
    # Agent 2 — sql / rankings / zips / charts
    # Agent 3 — config / backtest / events
]


def include_all(app: FastAPI) -> None:
    """Attach every registered router to ``app`` under the ``/api`` prefix."""
    for router in _ROUTERS:
        app.include_router(router, prefix="/api")


__all__ = ["include_all"]
