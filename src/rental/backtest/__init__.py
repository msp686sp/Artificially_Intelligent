"""Phase 6 — backtest harness.

The validation gate for the platform. Reconstructs feature snapshots
point-in-time, computes realized 5yr levered total return per zip, and
correlates them against an injected scoring callable.

Public surface:

- :class:`Assumptions` — standard underwriting assumptions held constant
  across zips (down payment, mortgage rate, opex ratios, vacancy).
- :class:`PublicationLag` — per-source publication-lag constants used
  by the point-in-time feature snapshot to prevent lookahead bias.
- :func:`snapshot_features` — return the feature set as it was available
  at ``as_of``.
- :func:`realized_levered_return_5yr` — realized 5yr levered total return
  for one zip given a snapshot date.
- :func:`run_backtest` — orchestrator over a list of snapshot dates.
- :func:`tune_weights` — walk-forward weight search.
- :func:`render_report` — renders the HTML backtest report.
"""

from rental.backtest.assumptions import Assumptions, PublicationLag
from rental.backtest.pit import snapshot_features
from rental.backtest.report import render_report
from rental.backtest.returns import realized_levered_return_5yr
from rental.backtest.run import BacktestResult, run_backtest
from rental.backtest.tune import tune_weights

__all__ = [
    "Assumptions",
    "BacktestResult",
    "PublicationLag",
    "realized_levered_return_5yr",
    "render_report",
    "run_backtest",
    "snapshot_features",
    "tune_weights",
]
