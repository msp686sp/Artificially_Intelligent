"""``/api/backtest/*`` — kick off / list / inspect backtest runs.

Two write endpoints accept a request, allocate a job + run id, and
schedule the actual work on a FastAPI background task. The task
publishes progress events to :mod:`api.progress` and persists a JSON
run record alongside the HTML report under ``data/backtest/runs/``.

The list/detail endpoints scan that directory; the report endpoint
streams the HTML file. Tests inject a synthetic runner via the
module-level ``CURRENT_RUNNER`` hook so the route plumbing can be
exercised without spinning up an hour-long real backtest.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import threading
import traceback
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse

from api import progress
from api.models.backtest import (
    BacktestJobAck,
    BacktestRunDetail,
    BacktestRunRequest,
    BacktestRunSummary,
    BacktestTuneRequest,
)

router = APIRouter(prefix="/backtest", tags=["backtest"])


# --------------------------------------------------------------------- paths


def _runs_dir() -> Path:
    """Directory holding ``<run_id>.json`` + ``<run_id>.html`` files."""
    override = os.environ.get("RENTAL_BACKTEST_RUNS_DIR")
    if override:
        return Path(override).resolve()
    return (Path(__file__).resolve().parents[2] / "data" / "backtest" / "runs").resolve()


# --------------------------------------------------------------------- atomic IO


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str))
    os.replace(tmp, path)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(6)}"


# --------------------------------------------------------------------- runner hook
#
# Tests replace this with a fake that emits a fixed result. The default
# runner imports the real backtest harness and writes the report via
# ``rental.backtest.render_report``.

RunnerResult = dict[str, Any]
"""Shape:
{
  "mode": "run" | "tune",
  "weights": {dim: weight, ...},
  "primary_metric": float | None,
  "snapshots": [{...}, ...],
  "quintile_bins": [[...], ...],
  "report_html": str,           # the HTML to persist
}
"""

Runner = Callable[[dict[str, Any], str], RunnerResult]

CURRENT_RUNNER: Runner | None = None
"""Module-level injection hook for tests. ``None`` -> default runner."""


def _default_runner(params: dict[str, Any], job_id: str) -> RunnerResult:
    """Real backtest runner used in production.

    Imported lazily so module import is cheap when the routes are
    merely registered.
    """
    import duckdb

    from rental.backtest import run_backtest
    from rental.backtest.report import render_report
    from rental.backtest.run import BacktestResult
    from rental.backtest.tune import tune_weights
    from rental.config import WAREHOUSE_PATH
    from rental.db import init_schema

    con = duckdb.connect(str(WAREHOUSE_PATH))
    init_schema(con)

    mode = params["mode"]
    snapshots_payload: list[dict[str, Any]] = []
    bins: list[list[float]] = []
    weights: dict[str, float] = {}
    primary: float | None = None
    result: BacktestResult

    def _yield_only(features):  # type: ignore[no-untyped-def]
        out = features[["zcta5"]].copy()
        col = features.get("gross_yield_monthly_pct", 0.0)
        out["score"] = col.fillna(0.0) if hasattr(col, "fillna") else col
        return out

    if mode == "run":
        dates = [date(y, 1, 1) for y in range(params["start_year"], params["end_year"] + 1)]
        result = run_backtest(con, dates, _yield_only)
        from tempfile import NamedTemporaryFile

        with NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        render_report(result, tmp_path)
        html = tmp_path.read_text()
        tmp_path.unlink(missing_ok=True)
    else:
        train_dates = [
            date(y, 1, 1) for y in range(params["train_start"], params["train_end"] + 1)
        ]
        val_dates = [
            date(y, 1, 1)
            for y in range(params["validate_start"], params["validate_end"] + 1)
        ]
        tune = tune_weights(con, train_dates, val_dates, lambda _w: _yield_only)
        result = run_backtest(con, val_dates, _yield_only)
        weights = dict(tune.best_weights)
        from tempfile import NamedTemporaryFile

        with NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        render_report(result, tmp_path, tune=tune)
        html = tmp_path.read_text()
        tmp_path.unlink(missing_ok=True)

    rhos: list[float] = []
    for s in result.snapshots:
        snapshots_payload.append(
            {
                "snapshot_date": s.snapshot_date.isoformat(),
                "n_zips": s.n_zips,
                "spearman": s.spearman,
                "top_minus_bottom": s.top_minus_bottom,
                "baselines": s.baselines,
            }
        )
        bins.append([float(v) for v in s.quintile_means])
        if isinstance(s.spearman, (int, float)) and s.spearman == s.spearman:  # not NaN
            rhos.append(float(s.spearman))
    if rhos:
        primary = sum(rhos) / len(rhos)

    return {
        "mode": mode,
        "weights": weights,
        "primary_metric": primary,
        "snapshots": snapshots_payload,
        "quintile_bins": bins,
        "report_html": html,
    }


def _get_runner() -> Runner:
    return CURRENT_RUNNER or _default_runner


# --------------------------------------------------------------------- background job


async def _publish(event_type: str, job_id: str, payload: dict[str, Any]) -> None:
    await progress.publish(
        progress.ProgressEvent(type=event_type, job_id=job_id, payload=payload)
    )


def _record(run_id: str) -> Path:
    return _runs_dir() / f"{run_id}.json"


def _report_file(run_id: str) -> Path:
    return _runs_dir() / f"{run_id}.html"


async def _execute_job(
    *,
    job_id: str,
    run_id: str,
    params: dict[str, Any],
) -> None:
    """Run the backtest and persist results.

    Errors are caught and recorded on the run document with
    ``status = "error"`` plus a ``"backtest.error"`` event.
    """
    started = _now_iso()
    record_path = _record(run_id)
    base: dict[str, Any] = {
        "id": run_id,
        "mode": params["mode"],
        "started_at": started,
        "finished_at": None,
        "status": "running",
        "weights": {},
        "primary_metric": None,
        "report_relpath": None,
    }
    _atomic_write_json(record_path, base)
    await _publish("backtest.started", job_id, {"run_id": run_id, "mode": params["mode"]})

    runner = _get_runner()
    try:
        # Run the (potentially slow, blocking) work in a thread so the
        # event loop stays responsive. The default runner uses duckdb +
        # pandas which are happy on a worker thread.
        result: RunnerResult = await _run_in_thread(runner, params, job_id)
    except Exception as exc:  # noqa: BLE001 - we want to surface anything
        base.update(
            status="error",
            finished_at=_now_iso(),
            error=f"{type(exc).__name__}: {exc}",
            traceback=traceback.format_exc(),
        )
        _atomic_write_json(record_path, base)
        await _publish(
            "backtest.error",
            job_id,
            {"run_id": run_id, "error": str(exc)},
        )
        return

    report_path = _report_file(run_id)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(result["report_html"])

    base.update(
        status="ok",
        finished_at=_now_iso(),
        mode=result.get("mode", params["mode"]),
        weights=result.get("weights", {}),
        primary_metric=result.get("primary_metric"),
        snapshots=result.get("snapshots", []),
        quintile_bins=result.get("quintile_bins", []),
        report_relpath=report_path.name,
    )
    _atomic_write_json(record_path, base)
    await _publish(
        "backtest.finished",
        job_id,
        {
            "run_id": run_id,
            "primary_metric": base["primary_metric"],
            "mode": base["mode"],
        },
    )


async def _run_in_thread(fn, *args):
    """Tiny wrapper around ``asyncio.to_thread`` so unit tests can patch it."""
    import asyncio

    return await asyncio.to_thread(fn, *args)


# --------------------------------------------------------------------- routes


@router.post("/run", response_model=BacktestJobAck)
async def post_run(
    body: BacktestRunRequest, background_tasks: BackgroundTasks
) -> BacktestJobAck:
    if body.end_year < body.start_year:
        raise HTTPException(status_code=400, detail="end_year must be >= start_year")
    job_id = _new_id("job")
    run_id = _new_id("run")
    params = {
        "mode": "run",
        "start_year": body.start_year,
        "end_year": body.end_year,
    }
    background_tasks.add_task(_execute_job, job_id=job_id, run_id=run_id, params=params)
    return BacktestJobAck(job_id=job_id, run_id=run_id)


@router.post("/tune", response_model=BacktestJobAck)
async def post_tune(
    body: BacktestTuneRequest, background_tasks: BackgroundTasks
) -> BacktestJobAck:
    if body.train_end < body.train_start:
        raise HTTPException(status_code=400, detail="train_end must be >= train_start")
    if body.validate_end < body.validate_start:
        raise HTTPException(
            status_code=400, detail="validate_end must be >= validate_start"
        )
    job_id = _new_id("job")
    run_id = _new_id("run")
    params = {
        "mode": "tune",
        "train_start": body.train_start,
        "train_end": body.train_end,
        "validate_start": body.validate_start,
        "validate_end": body.validate_end,
    }
    background_tasks.add_task(_execute_job, job_id=job_id, run_id=run_id, params=params)
    return BacktestJobAck(job_id=job_id, run_id=run_id)


@router.get("/runs", response_model=list[BacktestRunSummary])
def list_runs() -> list[BacktestRunSummary]:
    root = _runs_dir()
    if not root.exists():
        return []
    out: list[BacktestRunSummary] = []
    for p in sorted(root.glob("*.json")):
        try:
            data = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        out.append(
            BacktestRunSummary(
                id=data.get("id", p.stem),
                mode=data.get("mode", "unknown"),
                started_at=data.get("started_at", ""),
                finished_at=data.get("finished_at"),
                status=data.get("status", "unknown"),
                weights=data.get("weights", {}) or {},
                primary_metric=data.get("primary_metric"),
                report_path=data.get("report_relpath"),
            )
        )
    # Newest first.
    out.sort(key=lambda r: r.started_at, reverse=True)
    return out


@router.get("/runs/{run_id}", response_model=BacktestRunDetail)
def get_run(run_id: str) -> BacktestRunDetail:
    _validate_run_id(run_id)
    path = _record(run_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="run not found")
    data = json.loads(path.read_text())
    return BacktestRunDetail(
        id=data.get("id", run_id),
        mode=data.get("mode", "unknown"),
        started_at=data.get("started_at", ""),
        finished_at=data.get("finished_at"),
        status=data.get("status", "unknown"),
        weights=data.get("weights", {}) or {},
        primary_metric=data.get("primary_metric"),
        report_path=data.get("report_relpath"),
        snapshots=data.get("snapshots", []) or [],
        quintile_bins=data.get("quintile_bins", []) or [],
        error=data.get("error"),
    )


@router.get("/runs/{run_id}/report.html")
def get_run_report(run_id: str) -> StreamingResponse:
    _validate_run_id(run_id)
    path = _report_file(run_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="report not found")

    def _iter():
        with path.open("rb") as f:
            chunk = f.read(64 * 1024)
            while chunk:
                yield chunk
                chunk = f.read(64 * 1024)

    return StreamingResponse(_iter(), media_type="text/html")


def _validate_run_id(run_id: str) -> None:
    """Reject obvious path-traversal attempts on the run id."""
    if not run_id or "/" in run_id or "\\" in run_id or ".." in run_id:
        raise HTTPException(status_code=400, detail="invalid run id")


# ----- helpers exposed for tests --------------------------------------------


def _sync_runner_hook(runner: Runner | None) -> None:
    """Thread-safe-enough setter used by tests."""
    global CURRENT_RUNNER
    with threading.Lock():
        CURRENT_RUNNER = runner


# Re-export for the test module
set_runner = _sync_runner_hook


def clear_runs_dir() -> None:
    """Wipe ``data/backtest/runs/`` (used between tests)."""
    shutil.rmtree(_runs_dir(), ignore_errors=True)
