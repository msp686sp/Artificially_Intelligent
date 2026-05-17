"""Rental CLI: init, refresh, score, rank, backtest, status, digest (stub)."""

from datetime import UTC, date, datetime
from pathlib import Path

import click
import duckdb

from rental.config import CONFIG_DIR, DATA_DIR, RAW_DIR, WAREHOUSE_PATH
from rental.db import connect, init_schema
from rental.features import latest_zhvi_per_zip
from rental.filters import apply_filters
from rental.manifest import load_manifest, staleness_days
from rental.scoring import (
    compute_market_score,
    init_composite_views,
    populate_zip_features,
    populate_zip_scores,
)
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


# ============================================================
# Phase 5 — composite MarketScore + hard filters
# ============================================================


@cli.command()
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=DATA_DIR / "rankings" / "market_score.csv",
    show_default=True,
    help="Where to write the ranked CSV.",
)
@click.option(
    "--weights",
    type=click.Path(path_type=Path),
    default=CONFIG_DIR / "weights.yaml",
    show_default=True,
)
@click.option(
    "--filters",
    "filters_path",
    type=click.Path(path_type=Path),
    default=CONFIG_DIR / "filters.yaml",
    show_default=True,
)
def rank(output: Path, weights: Path, filters_path: Path):
    """Compute MarketScore, apply hard filters, write a ranked CSV.

    Pipeline: populate features + sub-scores → composite → filters → CSV.
    Safe to run against an empty warehouse — every step degrades to an
    empty result rather than crashing.
    """
    con = connect()
    init_schema(con)
    init_composite_views(con)
    feature_rows = populate_zip_features(con)
    score_rows = populate_zip_scores(con)
    if not feature_rows and not score_rows:
        click.echo(
            "No source data in warehouse. Run `rental refresh --source <name>` first.",
            err=True,
        )

    scores = compute_market_score(con, weights_path=weights)
    features = _load_features(con)
    filtered, audit = apply_filters(scores, features, filters_path=filters_path)

    output.parent.mkdir(parents=True, exist_ok=True)
    filtered.to_csv(output, index=False)

    click.echo(f"Wrote {len(filtered):,} ranked zips to {output}")
    for line in audit.summary_lines():
        click.echo(line)
    if not filtered.empty:
        head = filtered.head(5)[["zcta5", "state", "market_score"]].to_string(index=False)
        click.echo("Top 5:")
        click.echo(head)


def _load_features(con) -> "object":
    import pandas as pd

    try:
        return con.execute("SELECT * FROM zip_features").df()
    except duckdb.CatalogException:
        return pd.DataFrame()


# ============================================================
# Phase 6 — backtest harness
# ============================================================


@cli.group()
def backtest():
    """Phase 6 backtest harness: validation gate for the scorecard."""


def _default_snapshot_dates(start: int, end: int) -> list[date]:
    return [date(y, 1, 1) for y in range(start, end + 1)]


def _yield_only_score_fn():
    """Stub scoring function for `rental backtest run` when the composite
    scorer isn't wired into the backtest entrypoint yet. Ranks zips by
    gross_yield_monthly_pct so the CLI is usable end-to-end on a thin
    warehouse. Swap in the real composite score_fn once integrated.
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
    """Walk-forward weight tuning."""
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
    result = run_backtest(con, val_dates, stub_factory(tune.best_weights))
    render_report(result, output, tune=tune)
    click.echo(
        f"Tuned over {tune.grid_size} grid points. "
        f"Best train rho={tune.train_mean_spearman:.4f}, "
        f"validate rho={tune.validate_mean_spearman:.4f} → {output}"
    )


# ============================================================
# Source freshness / status
# ============================================================

# Per-source warehouse row counts. Extend when adding new sources.
_WAREHOUSE_ROW_QUERIES: dict[str, str] = {
    "zillow_zhvi": "SELECT COUNT(*) FROM raw_zillow_zhvi",
    "zillow_zori": "SELECT COUNT(*) FROM raw_zillow_zori",
    "redfin_market": "SELECT COUNT(*) FROM raw_redfin_market",
    "bls_qcew": "SELECT COUNT(*) FROM raw_bls_qcew",
    "irs_migration": "SELECT COUNT(*) FROM raw_irs_migration",
    "acs_demographics": "SELECT COUNT(*) FROM raw_acs_demographics",
    "census_bps": "SELECT COUNT(*) FROM raw_census_bps",
    "acs_housing_stock": "SELECT COUNT(*) FROM raw_acs_housing_stock",
    "county_tax_rate": "SELECT COUNT(*) FROM raw_county_tax_rate",
    "eviction_lab": "SELECT COUNT(*) FROM raw_eviction_lab",
    "fema_nri": "SELECT COUNT(*) FROM raw_fema_nri",
}


def _warehouse_row_count(con, source: str) -> int | None:
    """Best-effort row count for a source; ``None`` if the table is missing."""
    sql = _WAREHOUSE_ROW_QUERIES.get(source)
    if sql is None:
        return None
    try:
        row = con.execute(sql).fetchone()
    except Exception:
        return None
    return int(row[0]) if row else 0


@cli.command()
@click.option(
    "--stale-days",
    type=int,
    default=45,
    show_default=True,
    help="Warn (exit-1 in --strict mode) when a source is older than this.",
)
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    help="Exit non-zero if any source is stale or in error state.",
)
def status(stale_days: int, strict: bool):
    """Pretty-print refresh manifest + warehouse row counts."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    manifest = load_manifest()

    if not manifest and not REGISTRY:
        console.print("[yellow]No refreshes recorded.[/yellow]")
        return

    sources = sorted(set(REGISTRY) | set(manifest))

    if not sources:
        console.print("[yellow]No refreshes recorded.[/yellow]")
        return

    table = Table(title="Rental refresh status", show_lines=False)
    table.add_column("source", style="bold")
    table.add_column("last refresh (UTC)")
    table.add_column("age (d)", justify="right")
    table.add_column("manifest rows", justify="right")
    table.add_column("warehouse rows", justify="right")
    table.add_column("status")

    con = None
    if WAREHOUSE_PATH.exists():
        try:
            con = connect()
        except Exception:
            con = None

    any_stale = False
    any_error = False
    now = datetime.now(UTC)
    for source in sources:
        entry = manifest.get(source)
        wh_rows = _warehouse_row_count(con, source) if con is not None else None
        wh_cell = "-" if wh_rows is None else f"{wh_rows:,}"

        if entry is None:
            table.add_row(
                source, "[dim]never[/dim]", "-", "-", wh_cell,
                "[yellow]no refresh[/yellow]",
            )
            continue

        age = staleness_days(entry, now=now)
        stale = age > stale_days
        if stale:
            any_stale = True
        if entry.status != "ok":
            any_error = True

        status_label = (
            "[green]ok[/green]" if entry.status == "ok"
            else f"[red]{entry.status}[/red]"
        )
        if stale:
            status_label = f"{status_label} [yellow](stale)[/yellow]"

        table.add_row(
            source,
            entry.last_refresh.strftime("%Y-%m-%d %H:%M"),
            f"{age:.1f}",
            f"{entry.rows_loaded:,}",
            wh_cell,
            status_label,
        )

    console.print(table)

    if con is None and WAREHOUSE_PATH.exists() is False:
        console.print(
            f"[dim]warehouse not initialized ({WAREHOUSE_PATH}); "
            "run `rental init`[/dim]"
        )

    if strict and (any_stale or any_error):
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
