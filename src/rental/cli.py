"""Rental CLI: init, refresh, score, digest (stub)."""

from pathlib import Path

import click

from rental.config import RAW_DIR, WAREHOUSE_PATH
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


if __name__ == "__main__":
    cli()
