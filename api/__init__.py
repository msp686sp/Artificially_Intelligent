"""FastAPI app package for the rental GUI.

This is the backend half of the GUI (see ``docs/gooey-plan.md``). It is
shared across agents 1-3, who contribute disjoint route slices. This
worktree (agent 3, ``api-config-backtest``) ships:

- ``api/routes/config.py`` — ``/api/config/*`` editor endpoints
- ``api/routes/backtest.py`` — ``/api/backtest/*`` run / tune / list
- ``api/routes/events.py`` — WebSocket ``/api/events`` progress stream
- ``api/progress.py`` — minimal async pub/sub used by both of the above

Agent 1 owns the canonical ``api/main.py`` + ``api/progress.py``; the
versions here are seam-compatible stand-ins so the slice can be tested
in isolation.
"""
