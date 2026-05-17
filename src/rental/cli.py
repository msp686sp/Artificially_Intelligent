"""Rental CLI: init, refresh, score, digest (stub), status."""

from datetime import UTC, datetime
from pathlib import Path

import click

from rental.config import RAW_DIR, WAREHOUSE_PATH
from rental.db import connect, init_schema
from rental.features import latest_zhvi_per_zip
from rental.manifest import load_manifest, staleness_days
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


# --- Source freshness ----------------------------------------------------
# Per-source warehouse row counts. Phase 0 only has zillow_zhvi; add a
# row here when a new source lands so `rental status` reflects it.
_WAREHOUSE_ROW_QUERIES: dict[str, str] = {
    "zillow_zhvi": "SELECT COUNT(*) FROM raw_zillow_zhvi",
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
    """Pretty-print refresh manifest + warehouse row counts.

    Output is a single ``rich`` table covering every known source. Sources
    with no manifest entry are reported as "never refreshed". The
    warehouse is opened read-only so an empty/missing one still renders.
    """
    from rich.console import Console
    from rich.table import Table

    console = Console()
    manifest = load_manifest()

    if not manifest and not REGISTRY:
        console.print("[yellow]No refreshes recorded.[/yellow]")
        return

    # Union of registered sources and manifest-known sources so newly
    # registered sources show up before their first refresh, and historic
    # entries don't silently disappear if a source is unregistered.
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
