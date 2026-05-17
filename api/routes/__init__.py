"""Route registration helper.

Each agent owns a top-level labeled block here that wires its routers
onto a FastAPI app. The orchestrator concatenates blocks at merge
time. Until other agents land we register only the routes this
worktree owns.
"""

from __future__ import annotations

from fastapi import FastAPI


def register_routes(app: FastAPI) -> None:
    """Mount every owned router. Agents append to the labeled block."""

    # Agent 3 — config + backtest + events
    from api.routes import backtest as _backtest
    from api.routes import config as _config
    from api.routes import events as _events

    app.include_router(_config.router)
    app.include_router(_backtest.router)
    app.include_router(_events.router)


__all__ = ["register_routes"]
