"""Rental CLI: init, refresh, score, digest (stub)."""

from datetime import date
from pathlib import Path

import click

from rental.config import DATA_DIR, RAW_DIR, WAREHOUSE_PATH
from rental.db import connect, init_schema
from rental.features import latest_zhvi_per_zip
from rental.sources import REGISTRY


@click.group()
def cli():
    """Rental market analysis."""


@cli.command()
def init():
    """Initialize the warehouse schema."""
    con = connect()
    init_schema(con)
    click.echo(f"Initialized {WAREHOUSE_PATH}")


@cli.command()
@click.option("--source", required=True, type=click.Choice(sorted(REGISTRY)))
@click.option(
    "--from-fixture",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Load a local file instead of fetching from the network.",
)
def refresh(source: str, from_fixture: Path | None):
    """Refresh a single data source into the warehouse."""
    con = connect()
    init_schema(con)
    result = REGISTRY[source]().refresh(con, RAW_DIR, from_fixture=from_fixture)
    if result.status == "ok":
        click.echo(f"[{source}] loaded {result.rows_loaded:,} rows")
    else:
        click.echo(f"[{source}] FAILED: {result.error}", err=True)
        raise SystemExit(1)


@cli.command()
@click.option("--output", required=True, type=click.Path(path_type=Path))
def score(output: Path):
    """Phase 0 smoke output: zips ranked by latest ZHVI."""
    con = connect()
    df = latest_zhvi_per_zip(con)
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)
    click.echo(f"Wrote {len(df):,} rows to {output}")


@cli.command()
def digest():
    """Weekly email digest. Lands in Phase 7."""
    click.echo("Not yet implemented (Phase 7).")


@cli.group()
def backtest():
    """Phase 6 backtest harness: validation gate for the scorecard."""


def _default_snapshot_dates(start: int, end: int) -> list[date]:
    return [date(y, 1, 1) for y in range(start, end + 1)]


def _yield_only_score_fn():
    """Default score function for `rental backtest run` when no composite
    module is wired in yet. Ranks zips by gross_yield_monthly_pct so the
    CLI is usable end-to-end on a thin warehouse.
    """
    import pandas as pd

    def fn(features: pd.DataFrame) -> pd.DataFrame:
        out = features[["zcta5"]].copy()
        out["score"] = features.get("gross_yield_monthly_pct", 0.0).fillna(0.0)
        return out
    return fn


@backtest.command("run")
@click.option("--start-year", default=2013, show_default=True, type=int)
@click.option("--end-year", default=2019, show_default=True, type=int)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=DATA_DIR / "backtest" / "backtest_report.html",
    show_default=True,
)
def backtest_run(start_year: int, end_year: int, output: Path):
    """Run the backtest over [start-year, end-year] annual snapshots."""
    from rental.backtest import run_backtest
    from rental.backtest.report import render_report

    con = connect()
    init_schema(con)
    dates = _default_snapshot_dates(start_year, end_year)
    result = run_backtest(con, dates, _yield_only_score_fn())
    render_report(result, output)
    click.echo(f"Backtest wrote {len(result.snapshots)} snapshots → {output}")


@backtest.command("tune")
@click.option("--train-start", default=2013, show_default=True, type=int)
@click.option("--train-end", default=2017, show_default=True, type=int)
@click.option("--validate-start", default=2018, show_default=True, type=int)
@click.option("--validate-end", default=2022, show_default=True, type=int)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=DATA_DIR / "backtest" / "tune_report.html",
    show_default=True,
)
def backtest_tune(train_start: int, train_end: int,
                  validate_start: int, validate_end: int,
                  output: Path):
    """Walk-forward weight tuning.

    Without the composite agent's ScoreFactory wired in, this CLI uses a
    minimal stub factory that emits a yield-weighted score, exercising
    the harness end-to-end. Swap in the real factory once Phase 5 lands.
    """
    import pandas as pd

    from rental.backtest import run_backtest, tune_weights
    from rental.backtest.report import render_report

    def stub_factory(weights):
        yw = weights.get("yield", 1.0)

        def fn(features: pd.DataFrame) -> pd.DataFrame:
            out = features[["zcta5"]].copy()
            out["score"] = yw * features.get(
                "gross_yield_monthly_pct", 0.0
            ).fillna(0.0)
            return out
        return fn

    con = connect()
    init_schema(con)
    train_dates = _default_snapshot_dates(train_start, train_end)
    val_dates = _default_snapshot_dates(validate_start, validate_end)
    tune = tune_weights(con, train_dates, val_dates, stub_factory)
    # Also produce a backtest result over validate dates using best weights,
    # so the report has snapshot rows to render.
    result = run_backtest(con, val_dates, stub_factory(tune.best_weights))
    render_report(result, output, tune=tune)
    click.echo(
        f"Tuned over {tune.grid_size} grid points. "
        f"Best train rho={tune.train_mean_spearman:.4f}, "
        f"validate rho={tune.validate_mean_spearman:.4f} → {output}"
    )


if __name__ == "__main__":
    cli()
