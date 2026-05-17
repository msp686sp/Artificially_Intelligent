"""Minimal FastAPI app factory.

Agent 1 (``api-core``) owns the production scaffolding (CORS, settings,
lifespan hooks, etc). This shim exists so the agent-3 worktree can be
tested in isolation: ``api.main.create_app()`` mounts the routes this
agent owns. When agent 1's version lands it supersedes this file — the
test fixtures import ``create_app`` so updating the implementation
behind it is sufficient.
"""

from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Return a FastAPI application with the owned routes mounted."""
    app = FastAPI(title="Rental GUI API", version="0.0.1")

    from api.routes import register_routes

    register_routes(app)
    return app
