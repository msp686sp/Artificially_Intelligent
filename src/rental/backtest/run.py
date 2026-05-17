"""Backtest orchestrator.

For each snapshot date:
  1. Build a point-in-time feature snapshot (no lookahead).
  2. Score it via an injected `score_fn` (the composite agent owns the
     specific implementation; we just call it).
  3. Compute realized 5yr levered total returns for the same universe.
  4. Spearman-rank-correlate scores with realized returns.
  5. Bucket into score quintiles, report mean realized return per
     quintile.
  6. Compute baselines (yield-only, equal-weighted, random) for context.

The output is a :class:`BacktestResult` plus per-snapshot detail rows
that the report renderer turns into HTML.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

import duckdb
import numpy as np
import pandas as pd

from rental.backtest.assumptions import Assumptions
from rental.backtest.pit import snapshot_features
from rental.backtest.returns import realized_returns_for_universe

ScoreFn = Callable[[pd.DataFrame], pd.DataFrame]
"""Callable contract: ``features_df -> scores_df``.

Input must have a ``zcta5`` column. Output must have ``zcta5`` and
``score`` columns (extra columns are ignored).
"""


@dataclass
class SnapshotResult:
    snapshot_date: date
    n_zips: int
    spearman: float
    quintile_means: list[float]
    top_minus_bottom: float
    universe: pd.DataFrame  # zcta5, score, realized
    baselines: dict[str, float]


@dataclass
class BacktestResult:
    snapshots: list[SnapshotResult] = field(default_factory=list)

    def summary(self) -> pd.DataFrame:
        rows = []
        for s in self.snapshots:
            rows.append({
                "snapshot_date": s.snapshot_date,
                "n_zips": s.n_zips,
                "spearman": s.spearman,
                "top_minus_bottom": s.top_minus_bottom,
                **{f"q{i + 1}_mean": v for i, v in enumerate(s.quintile_means)},
                **{f"baseline_{k}": v for k, v in s.baselines.items()},
            })
        return pd.DataFrame(rows)


def spearman_rho(a: pd.Series, b: pd.Series) -> float:
    """Spearman rank correlation, implemented without scipy.

    Convert to ranks (average method for ties) then take Pearson r.
    Returns NaN when fewer than 3 paired observations.
    """
    paired = pd.concat([a.reset_index(drop=True), b.reset_index(drop=True)], axis=1)
    paired.columns = ["a", "b"]
    paired = paired.dropna()
    if len(paired) < 3:
        return float("nan")
    ra = paired["a"].rank(method="average")
    rb = paired["b"].rank(method="average")
    # If either rank vector is constant, correlation is undefined.
    if ra.nunique() < 2 or rb.nunique() < 2:
        return float("nan")
    return float(ra.corr(rb, method="pearson"))


def _quintile_means(scores: pd.Series, realized: pd.Series, n_buckets: int = 5) -> list[float]:
    df = pd.DataFrame({"score": scores, "realized": realized}).dropna()
    if df.empty:
        return [float("nan")] * n_buckets
    try:
        df["bucket"] = pd.qcut(
            df["score"].rank(method="first"),
            n_buckets,
            labels=list(range(n_buckets)),
        )
    except ValueError:
        # Not enough distinct ranks to bucket; bin uniformly.
        df["bucket"] = pd.cut(
            df["score"].rank(method="first"),
            bins=n_buckets,
            labels=list(range(n_buckets)),
            include_lowest=True,
        )
    means = df.groupby("bucket", observed=False)["realized"].mean()
    out: list[float] = []
    for i in range(n_buckets):
        v = means.get(i, float("nan"))
        out.append(float("nan") if pd.isna(v) else float(v))
    return out


def _yield_only_baseline(features: pd.DataFrame, realized: pd.DataFrame) -> float:
    if "gross_yield_monthly_pct" not in features.columns:
        return float("nan")
    merged = features[["zcta5", "gross_yield_monthly_pct"]].merge(
        realized[["zcta5", "levered_total_return_5yr"]], on="zcta5"
    )
    return spearman_rho(merged["gross_yield_monthly_pct"], merged["levered_total_return_5yr"])


def _equal_weighted_baseline(features: pd.DataFrame, realized: pd.DataFrame) -> float:
    """Z-score every numeric feature column and sum equally.

    A crude stand-in for "equal-weighted dimensions" when we don't have
    sub-scores at hand — but it gives the harness a comparison value
    that uses the same inputs as a real composite without weight tuning.
    """
    numeric = features.select_dtypes(include="number")
    if numeric.empty:
        return float("nan")
    z = (numeric - numeric.mean()) / numeric.std(ddof=0).replace(0, np.nan)
    score = z.fillna(0).sum(axis=1)
    score.index = features["zcta5"].values
    merged = pd.DataFrame({"score": score}).reset_index(names="zcta5").merge(
        realized[["zcta5", "levered_total_return_5yr"]], on="zcta5"
    )
    return spearman_rho(merged["score"], merged["levered_total_return_5yr"])


def _random_baseline(realized: pd.DataFrame, seed: int) -> float:
    rng = np.random.default_rng(seed)
    fake = pd.Series(rng.random(len(realized)), index=realized.index)
    return spearman_rho(fake, realized["levered_total_return_5yr"])


def run_backtest(
    con: duckdb.DuckDBPyConnection,
    snapshot_dates: list[date],
    score_fn: ScoreFn,
    assumptions: Assumptions | None = None,
    random_seed: int = 42,
) -> BacktestResult:
    """End-to-end backtest over the given snapshot dates.

    ``score_fn`` is injected so this harness has no coupling to the
    composite-scoring module the parallel agent is shipping.
    """
    a = assumptions or Assumptions()
    result = BacktestResult()

    for s_date in snapshot_dates:
        features = snapshot_features(con, s_date, a)
        if features.empty:
            continue

        scores = score_fn(features)
        if "zcta5" not in scores.columns or "score" not in scores.columns:
            raise ValueError(
                "score_fn must return a DataFrame with 'zcta5' and 'score' columns"
            )

        tax_by_zip = dict(zip(features["zcta5"], features["effective_tax_rate"], strict=False))
        ins_by_zip = dict(zip(features["zcta5"], features["insurance_rate"], strict=False))
        realized = realized_returns_for_universe(
            con, s_date, list(features["zcta5"]), a,
            tax_by_zip=tax_by_zip, insurance_by_zip=ins_by_zip,
        )
        if realized.empty:
            continue

        universe = scores.merge(
            realized[["zcta5", "levered_total_return_5yr"]],
            on="zcta5",
            how="inner",
        ).rename(columns={"levered_total_return_5yr": "realized"})

        if len(universe) < 3:
            continue

        rho = spearman_rho(universe["score"], universe["realized"])
        means = _quintile_means(universe["score"], universe["realized"])
        # Top - bottom on the realized return (raw, not z-scored).
        top, bottom = means[-1], means[0]
        tmb = (top - bottom) if (not math.isnan(top) and not math.isnan(bottom)) else float("nan")

        baselines = {
            "yield_only_spearman": _yield_only_baseline(features, realized),
            "equal_weighted_spearman": _equal_weighted_baseline(features, realized),
            "random_spearman": _random_baseline(
                realized, seed=random_seed + s_date.year,
            ),
        }

        result.snapshots.append(
            SnapshotResult(
                snapshot_date=s_date,
                n_zips=len(universe),
                spearman=rho,
                quintile_means=means,
                top_minus_bottom=tmb,
                universe=universe,
                baselines=baselines,
            )
        )

    return result


def bootstrap_top_minus_bottom_ci(
    universe: pd.DataFrame,
    n_bootstrap: int = 1000,
    seed: int = 0,
    alpha: float = 0.05,
) -> tuple[float, float, float]:
    """Bootstrap a (low, point, high) CI on quintile top-minus-bottom.

    Resamples rows with replacement; recomputes quintiles each draw.
    """
    rng = np.random.default_rng(seed)
    n = len(universe)
    if n < 5:
        return (float("nan"), float("nan"), float("nan"))
    draws = []
    for _ in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        sample = universe.iloc[idx]
        means = _quintile_means(sample["score"], sample["realized"])
        if math.isnan(means[0]) or math.isnan(means[-1]):
            continue
        draws.append(means[-1] - means[0])
    if not draws:
        return (float("nan"), float("nan"), float("nan"))
    arr = np.array(draws)
    return (
        float(np.quantile(arr, alpha / 2)),
        float(np.median(arr)),
        float(np.quantile(arr, 1 - alpha / 2)),
    )
