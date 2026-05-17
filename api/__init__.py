"""FastAPI backend for the rental market analysis GUI.

See ``docs/gooey-plan.md`` for the build plan. Backend is partitioned
across 3 agents: api-core (skeleton + sources/manifest/schema),
api-sql-rankings (SQL + rankings + zips + charts), and
api-config-backtest (config + backtest + WebSocket events).
"""

__version__ = "0.1.0"
