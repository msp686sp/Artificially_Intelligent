"""FastAPI app entrypoint.

Run with::

    uvicorn api.main:app --reload --port 8000

OpenAPI docs at ``/docs`` (Swagger) and ``/redoc``. Routes live under
``/api`` and are registered by ``api.routes.include_all``.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import __version__
from api.deps import get_settings
from api.progress import bus
from api.routes import include_all


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Bind the progress bus to the running asyncio loop on startup."""
    bus.attach_loop(asyncio.get_running_loop())
    yield


def create_app() -> FastAPI:
    """Application factory.

    Kept as a factory (rather than module-level ``app =``) so tests can
    spin up isolated instances. ``api.main:app`` is still exported for
    ``uvicorn`` to import.
    """
    settings = get_settings()
    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        description=(
            "Local-first API for the rental market analysis platform. "
            "See ``docs/gooey-plan.md`` for the GUI build plan."
        ),
        openapi_url="/api/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount every router (agents 1-3 contribute via api/routes/__init__.py).
    include_all(app)

    return app


app = create_app()


__all__ = ["app", "create_app", "__version__"]
