"""Walk-forward weight tuning.

Train on a set of snapshot dates (e.g., 2013-2017), validate on a
disjoint forward window (2018-2022). Search a small named grid of
composite-score weights; pick the weight vector with the best mean
in-sample Spearman, then report its out-of-sample performance.

The composite logic itself lives in another agent's module. We accept
a :class:`ScoreFactory` callable: given a weight vector, return a
``score_fn`` that the backtest harness can use. That keeps this module
agnostic to whether the composite uses z-scores, ranks, or raw values.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

import duckdb
import numpy as np
import pandas as pd

from rental.backtest.assumptions import Assumptions, WeightGrid
from rental.backtest.pit import snapshot_features
from rental.backtest.returns import realized_returns_for_universe
from rental.backtest.run import (
    BacktestResult,
    ScoreFn,
    SnapshotResult,
    _quintile_means,
    run_backtest,
    spearman_rho,
)

WeightVector = dict[str, float]
"""Mapping of dimension name -> weight; the composite agent decides keys."""

ScoreFactory = Callable[[WeightVector], ScoreFn]
"""Closes over a weight vector to produce a backtest-compatible scoring fn."""


@dataclass
class WeightTuneResult:
    best_weights: WeightVector
    train_mean_spearman: float
    validate_mean_spearman: float
    train_result: BacktestResult
    validate_result: BacktestResult
    grid_size: int
    all_train_scores: list[tuple[WeightVector, float]] = field(default_factory=list)


def _grid_iterator(grid: WeightGrid) -> list[WeightVector]:
    """Enumerate the full 5-dimension grid as weight vectors.

    Composite key names mirror config/weights.yaml so the output drops
    straight into the live config when the user accepts a tune.
    """
    out: list[WeightVector] = []
    for yld, dem, sup, op_, rsk in itertools.product(
        grid.yield_, grid.demand, grid.supply, grid.operability, grid.risk
    ):
        out.append({
            "yield": yld,
            "demand": dem,
            "supply": sup,
            "operability": op_,
            "risk": rsk,
        })
    return out


def _mean_spearman(result: BacktestResult) -> float:
    rhos = [s.spearman for s in result.snapshots if not np.isnan(s.spearman)]
    if not rhos:
        return float("nan")
    return float(np.mean(rhos))


def _precompute_panel(
    con: duckdb.DuckDBPyConnection,
    dates: list[date],
    assumptions: Assumptions,
) -> list[tuple[date, pd.DataFrame, pd.DataFrame]]:
    """For each snapshot date, return (features, realized) once.

    Tuning iterates over weight vectors but the features and realized
    returns are weight-invariant. Caching them turns the inner loop into
    a cheap scoring step.
    """
    panel: list[tuple[date, pd.DataFrame, pd.DataFrame]] = []
    for d in dates:
        features = snapshot_features(con, d, assumptions)
        if features.empty:
            continue
        tax_by_zip = dict(zip(features["zcta5"], features["effective_tax_rate"], strict=False))
        ins_by_zip = dict(zip(features["zcta5"], features["insurance_rate"], strict=False))
        realized = realized_returns_for_universe(
            con, d, list(features["zcta5"]), assumptions,
            tax_by_zip=tax_by_zip, insurance_by_zip=ins_by_zip,
        )
        if realized.empty:
            continue
        panel.append((d, features, realized))
    return panel


def _score_panel(
    panel: list[tuple[date, pd.DataFrame, pd.DataFrame]],
    score_fn: ScoreFn,
) -> BacktestResult:
    """Apply ``score_fn`` to a cached panel; return a BacktestResult.

    Same shape as run_backtest but skips the expensive realized-return
    computation. Baselines and the rest are reused.
    """
    out = BacktestResult()
    for d, features, realized in panel:
        scores = score_fn(features)
        if "zcta5" not in scores.columns or "score" not in scores.columns:
            raise ValueError(
                "score_fn must return a DataFrame with 'zcta5' and 'score' columns"
            )
        universe = scores.merge(
            realized[["zcta5", "levered_total_return_5yr"]],
            on="zcta5", how="inner",
        ).rename(columns={"levered_total_return_5yr": "realized"})
        if len(universe) < 3:
            continue
        rho = spearman_rho(universe["score"], universe["realized"])
        means = _quintile_means(universe["score"], universe["realized"])
        top, bottom = means[-1], means[0]
        tmb = float("nan")
        if not np.isnan(top) and not np.isnan(bottom):
            tmb = top - bottom
        out.snapshots.append(SnapshotResult(
            snapshot_date=d, n_zips=len(universe), spearman=rho,
            quintile_means=means, top_minus_bottom=tmb,
            universe=universe, baselines={},
        ))
    return out


def tune_weights(
    con: duckdb.DuckDBPyConnection,
    train_dates: list[date],
    validate_dates: list[date],
    score_factory: ScoreFactory,
    grid: WeightGrid | None = None,
    assumptions: Assumptions | None = None,
) -> WeightTuneResult:
    """Search the weight grid; return best in-sample plus its OOS perf.

    Selection criterion is mean Spearman on the training snapshots.

    Realized returns are weight-invariant, so we precompute them per
    snapshot once and only rerun the score function inside the loop.
    The final out-of-sample number still uses :func:`run_backtest` so
    the validation result carries baselines for the report.
    """
    grid = grid or WeightGrid()
    assumptions = assumptions or Assumptions()

    candidates = _grid_iterator(grid)
    train_panel = _precompute_panel(con, train_dates, assumptions)
    if not train_panel:
        return WeightTuneResult(
            best_weights={},
            train_mean_spearman=float("nan"),
            validate_mean_spearman=float("nan"),
            train_result=BacktestResult(),
            validate_result=BacktestResult(),
            grid_size=len(candidates),
            all_train_scores=[],
        )

    best_weights: WeightVector | None = None
    best_mean = -float("inf")
    best_train_result: BacktestResult | None = None
    all_scores: list[tuple[WeightVector, float]] = []

    for w in candidates:
        score_fn = score_factory(w)
        train_result = _score_panel(train_panel, score_fn)
        m = _mean_spearman(train_result)
        all_scores.append((w, m))
        if not np.isnan(m) and m > best_mean:
            best_mean = m
            best_weights = w
            best_train_result = train_result

    if best_weights is None:
        return WeightTuneResult(
            best_weights={},
            train_mean_spearman=float("nan"),
            validate_mean_spearman=float("nan"),
            train_result=BacktestResult(),
            validate_result=BacktestResult(),
            grid_size=len(candidates),
            all_train_scores=all_scores,
        )

    validate_fn = score_factory(best_weights)
    validate_result = run_backtest(con, validate_dates, validate_fn, assumptions)
    val_mean = _mean_spearman(validate_result)

    return WeightTuneResult(
        best_weights=best_weights,
        train_mean_spearman=best_mean,
        validate_mean_spearman=val_mean,
        train_result=best_train_result or BacktestResult(),
        validate_result=validate_result,
        grid_size=len(candidates),
        all_train_scores=all_scores,
    )


def default_snapshot_dates() -> tuple[list[date], list[date]]:
    """The locked plan's walk-forward windows.

    Train: 2013-01-01 .. 2017-01-01 (5 snapshots).
    Validate: 2018-01-01 .. 2022-01-01 (5 snapshots).
    """
    train = [date(y, 1, 1) for y in range(2013, 2018)]
    validate = [date(y, 1, 1) for y in range(2018, 2023)]
    return train, validate
