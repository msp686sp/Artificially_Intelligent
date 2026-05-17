"""Route registry.

Agents 1, 2, and 3 each contribute disjoint route slices. To avoid a
serial conflict on this file at merge time, every agent registers its
routers in a labeled block; the orchestrator concatenates the blocks
into a single ``register_routes`` call when merging.

Agent 1 (api-core) owns the canonical ``register_routes(app)`` factory
that ``api/main.py`` calls at startup. Until Agent 1's block lands,
this module exposes the same factory in a minimal form so the GUI
backend is still runnable end-to-end.
"""

from __future__ import annotations

from fastapi import FastAPI

# Agent 2 — SQL + rankings + zips + charts
from api.routes import charts as charts_routes
from api.routes import rankings as rankings_routes
from api.routes import sql as sql_routes
from api.routes import zips as zips_routes

# TODO(agent-1): replace this minimal registry with the canonical one
# that also wires health, sources, manifest, schema. Agent 1's edits
# go above this comment as a labeled "# Agent 1 — core" block. Other
# agents append their own labeled blocks below.


def register_routes(app: FastAPI) -> None:
    """Mount every route module on the given FastAPI app.

    Idempotent in the sense that calling it twice on the same app will
    register duplicate routes — don't do that. ``api/main.py`` should
    call it exactly once at startup.
    """
    # Agent 2 — SQL + rankings + zips + charts
    app.include_router(sql_routes.router)
    app.include_router(rankings_routes.router)
    app.include_router(zips_routes.router)
    app.include_router(charts_routes.router)


__all__ = ["register_routes"]
