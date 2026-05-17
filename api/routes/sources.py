"""Sources endpoints.

Joins ``rental.sources.REGISTRY`` (the canonical list of sources) with
the manifest (freshness state) and the warehouse (row counts). Refresh
kicks off a background task that publishes progress events via
``api.progress.bus``.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from pathlib import Path

import duckdb
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query

from api.deps import _open_connection, get_db_ro
from api.models import (
    RefreshAccepted,
    RefreshRequest,
    SourceColumn,
    SourceDetail,
    SourcePreview,
    SourceSchema,
    SourceSummary,
)
from api.progress import ProgressEvent, bus, new_job_id
from rental.config import RAW_DIR
from rental.db import init_schema
from rental.manifest import ManifestEntry, load_manifest
from rental.sources import REGISTRY

router = APIRouter(tags=["sources"])


# ---------------------------------------------------------------------------
# Static source metadata. The plan calls out source_url/license/cadence in
# /api/sources; the Source classes don't yet carry these, so we keep a
# small table here. Extending it is additive when a new source lands.
# ---------------------------------------------------------------------------
SOURCE_META: dict[str, dict[str, str]] = {
    "zillow_zhvi": {
        "source_url": "https://www.zillow.com/research/data/",
        "license": "Zillow Research — free for non-commercial use",
        "cadence": "monthly",
    },
    "zillow_zori": {
        "source_url": "https://www.zillow.com/research/data/",
        "license": "Zillow Research — free for non-commercial use",
        "cadence": "monthly",
    },
    "redfin_market": {
        "source_url": "https://www.redfin.com/news/data-center/",
        "license": "Redfin Data Center — free",
        "cadence": "weekly",
    },
    "census_geo": {
        "source_url": "https://www.census.gov/geographies/reference-files.html",
        "license": "U.S. Government work, public domain",
        "cadence": "annual",
    },
    "bls_qcew": {
        "source_url": "https://data.bls.gov/cew/",
        "license": "U.S. Government work, public domain",
        "cadence": "quarterly",
    },
    "irs_migration": {
        "source_url": "https://www.irs.gov/statistics/soi-tax-stats-migration-data",
        "license": "U.S. Government work, public domain",
        "cadence": "annual",
    },
    "acs_demographics": {
        "source_url": "https://api.census.gov/data/",
        "license": "U.S. Government work, public domain",
        "cadence": "annual",
    },
    "census_bps": {
        "source_url": "https://www.census.gov/construction/bps/",
        "license": "U.S. Government work, public domain",
        "cadence": "monthly",
    },
    "acs_housing_stock": {
        "source_url": "https://api.census.gov/data/",
        "license": "U.S. Government work, public domain",
        "cadence": "annual",
    },
    "county_tax_rate": {
        "source_url": "https://api.census.gov/data/",
        "license": "U.S. Government work, public domain (derived from ACS)",
        "cadence": "annual",
    },
    "eviction_lab": {
        "source_url": "https://evictionlab.org/",
        "license": "Eviction Lab — research use",
        "cadence": "annual",
    },
    "fema_nri": {
        "source_url": "https://hazards.fema.gov/nri/",
        "license": "U.S. Government work, public domain",
        "cadence": "annual",
    },
}

# Warehouse table backing each source — mirrors ``cli._WAREHOUSE_ROW_QUERIES``
# but keyed for direct table access (preview/schema endpoints).
SOURCE_TABLE: dict[str, str] = {
    "zillow_zhvi": "raw_zillow_zhvi",
    "zillow_zori": "raw_zillow_zori",
    "redfin_market": "raw_redfin_market",
    "bls_qcew": "raw_bls_qcew",
    "irs_migration": "raw_irs_migration",
    "acs_demographics": "raw_acs_demographics",
    "census_bps": "raw_census_bps",
    "acs_housing_stock": "raw_acs_housing_stock",
    "county_tax_rate": "raw_county_tax_rate",
    "eviction_lab": "raw_eviction_lab",
    "fema_nri": "raw_fema_nri",
    # census_geo populates multiple tables; pick the canonical one for preview.
    "census_geo": "geo_zcta",
}


def _summary_for(
    name: str,
    manifest: dict[str, ManifestEntry],
    con: duckdb.DuckDBPyConnection | None,
) -> SourceSummary:
    entry = manifest.get(name)
    meta = SOURCE_META.get(name, {})
    table = SOURCE_TABLE.get(name)
    warehouse_rows: int | None = None
    if con is not None and table is not None:
        try:
            row = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()
            warehouse_rows = int(row[0]) if row else 0
        except duckdb.Error:
            warehouse_rows = None
    return SourceSummary(
        name=name,
        status=entry.status if entry else "never",
        last_refresh=entry.last_refresh if entry else None,
        rows_loaded=entry.rows_loaded if entry else None,
        warehouse_rows=warehouse_rows,
        error=entry.error if entry else None,
        source_url=meta.get("source_url"),
        license=meta.get("license"),
        cadence=meta.get("cadence"),
    )


@router.get("/sources", response_model=list[SourceSummary])
def list_sources(
    con: duckdb.DuckDBPyConnection = Depends(get_db_ro),
) -> list[SourceSummary]:
    """List every registered source with manifest + warehouse status."""
    manifest = load_manifest()
    return [_summary_for(name, manifest, con) for name in sorted(REGISTRY)]


@router.get("/sources/{name}", response_model=SourceDetail)
def get_source(
    name: str,
    con: duckdb.DuckDBPyConnection = Depends(get_db_ro),
) -> SourceDetail:
    """Detail view for a single source."""
    if name not in REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown source '{name}'")
    manifest = load_manifest()
    summary = _summary_for(name, manifest, con)
    return SourceDetail(**summary.model_dump())


@router.get("/sources/{name}/schema", response_model=SourceSchema)
def get_source_schema(
    name: str,
    con: duckdb.DuckDBPyConnection = Depends(get_db_ro),
) -> SourceSchema:
    """Column info for the warehouse table backing this source."""
    if name not in REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown source '{name}'")
    table = SOURCE_TABLE.get(name)
    if table is None:
        raise HTTPException(
            status_code=404,
            detail=f"No warehouse table mapped for source '{name}'",
        )
    rows = con.execute(
        """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'main' AND table_name = ?
        ORDER BY ordinal_position
        """,
        [table],
    ).fetchall()
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"Table '{table}' is not present in the warehouse",
        )
    columns = [
        SourceColumn(
            name=col_name,
            type=str(dtype),
            nullable=(str(nullable).upper() != "NO"),
        )
        for col_name, dtype, nullable in rows
    ]
    return SourceSchema(source=name, table=table, columns=columns)


@router.get("/sources/{name}/preview", response_model=SourcePreview)
def preview_source(
    name: str,
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    con: duckdb.DuckDBPyConnection = Depends(get_db_ro),
) -> SourcePreview:
    """Paginated peek at the underlying warehouse table."""
    if name not in REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown source '{name}'")
    table = SOURCE_TABLE.get(name)
    if table is None:
        raise HTTPException(
            status_code=404,
            detail=f"No warehouse table mapped for source '{name}'",
        )
    try:
        total_row = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()
    except duckdb.Error as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Table '{table}' not available: {exc}",
        ) from exc
    total = int(total_row[0]) if total_row else 0

    cursor = con.execute(
        f'SELECT * FROM "{table}" LIMIT ? OFFSET ?',
        [limit, offset],
    )
    rows = cursor.fetchall()
    columns = [d[0] for d in cursor.description] if cursor.description else []
    dict_rows = [dict(zip(columns, r, strict=False)) for r in rows]

    return SourcePreview(
        source=name,
        table=table,
        columns=columns,
        rows=dict_rows,
        limit=limit,
        offset=offset,
        row_count=total,
    )


# ---------------------------------------------------------------------------
# Refresh — fire-and-forget background task that publishes progress events.
# ---------------------------------------------------------------------------


def _run_refresh(
    source_name: str,
    job_id: str,
    from_fixture: Path | None,
) -> None:
    """Run the refresh in a worker thread, publishing progress along the way.

    Lives outside the request lifecycle: opens its own DuckDB connection
    (writable), since BackgroundTasks runs after the response is sent.
    """
    bus.publish_threadsafe(
        ProgressEvent(
            job_id=job_id,
            type="refresh.started",
            payload={
                "source": source_name,
                "from_fixture": str(from_fixture) if from_fixture else None,
                "started_at": datetime.now(UTC).isoformat(),
            },
        )
    )
    con: duckdb.DuckDBPyConnection | None = None
    try:
        con = _open_connection(read_only=False)
        init_schema(con)
        bus.publish_threadsafe(
            ProgressEvent(
                job_id=job_id,
                type="refresh.progress",
                payload={"source": source_name, "step": "loading"},
            )
        )
        result = REGISTRY[source_name]().refresh(
            con, RAW_DIR, from_fixture=from_fixture
        )
        bus.publish_threadsafe(
            ProgressEvent(
                job_id=job_id,
                type=(
                    "refresh.completed" if result.status == "ok" else "refresh.failed"
                ),
                payload={
                    "source": source_name,
                    "status": result.status,
                    "rows_loaded": result.rows_loaded,
                    "error": result.error,
                    "finished_at": datetime.now(UTC).isoformat(),
                },
            )
        )
    except Exception as exc:  # pragma: no cover — defensive
        bus.publish_threadsafe(
            ProgressEvent(
                job_id=job_id,
                type="refresh.failed",
                payload={
                    "source": source_name,
                    "status": "error",
                    "error": str(exc),
                    "finished_at": datetime.now(UTC).isoformat(),
                },
            )
        )
    finally:
        if con is not None:
            con.close()


@router.post(
    "/sources/{name}/refresh",
    response_model=RefreshAccepted,
    status_code=202,
)
def refresh_source(
    name: str,
    background_tasks: BackgroundTasks,
    payload: RefreshRequest | None = Body(default=None),
) -> RefreshAccepted:
    """Kick off a refresh in the background. Returns a job_id immediately."""
    if name not in REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown source '{name}'")

    body = payload or RefreshRequest()
    from_fixture: Path | None = None
    if body.from_fixture:
        candidate = Path(body.from_fixture)
        if not candidate.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Fixture path '{body.from_fixture}' does not exist",
            )
        from_fixture = candidate

    job_id = new_job_id()

    # Use a real thread (not just BackgroundTasks) because TestClient runs
    # background tasks synchronously *after* the response — that's fine
    # for prod, but tests asserting "fire and forget" semantics also work
    # because the event publishing happens on the same loop. We use
    # BackgroundTasks here for FastAPI's standard story.
    def _kick() -> None:
        # Run in a daemon thread so the response is fully released before
        # the long-running refresh proceeds.
        t = threading.Thread(
            target=_run_refresh,
            args=(name, job_id, from_fixture),
            daemon=True,
            name=f"refresh-{name}-{job_id}",
        )
        t.start()

    background_tasks.add_task(_kick)
    return RefreshAccepted(
        job_id=job_id,
        source=name,
        from_fixture=str(from_fixture) if from_fixture else None,
    )
