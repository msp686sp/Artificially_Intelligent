"""Rental CLI: init, refresh, score, rank, digest (stub)."""

from pathlib import Path

import click
import duckdb

from rental.config import CONFIG_DIR, DATA_DIR, RAW_DIR, WAREHOUSE_PATH
from rental.db import connect, init_schema
from rental.features import latest_zhvi_per_zip
from rental.filters import apply_filters
from rental.scoring import compute_market_score, init_composite_views
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
    """Compute MarketScore, apply hard filters, write a ranked CSV."""
    con = connect()
    init_schema(con)
    init_composite_views(con)

    scores = compute_market_score(con, weights_path=weights)
    if scores.empty:
        click.echo(
            "No sub-scores available yet (zip_scores is empty). "
            "Run the sub-score producers first.",
            err=True,
        )
        # Still emit an empty CSV so downstream consumers have something
        # to read; signal non-zero on stderr only.
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


def _load_features(con) -> "object":  # narrow type avoids pandas import-at-top noise
    import pandas as pd

    try:
        return con.execute("SELECT * FROM zip_features").df()
    except duckdb.CatalogException:
        return pd.DataFrame()


if __name__ == "__main__":
    cli()
