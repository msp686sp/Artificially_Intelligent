"""Tests for ``/api/backtest/*``.

We do NOT trigger a real backtest. A synthetic runner produces a fixed
result (mirroring the shape of the default runner's output). The route
plumbing is what's under test here: job/run id generation,
background-task execution, persisted JSON record, persisted HTML
report file, list/detail/report endpoints.

One end-to-end style test (``test_run_with_synthetic_data``) builds a
DuckDB with the bundled synthetic ZHVI/ZORI fixtures and exercises the
*real* ``rental.backtest.run_backtest`` via a runner that bypasses the
default ``WAREHOUSE_PATH`` resolution — that validates the plumbing
also works against a real ``BacktestResult`` -> report flow.
"""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.routes import backtest as backtest_route

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"


# --------------------------------------------------------------------- helpers


def _fake_runner(_params: dict[str, Any], _job_id: str) -> dict[str, Any]:
    """Synthetic runner that mimics ``_default_runner``'s output."""
    return {
        "mode": _params["mode"],
        "weights": {"yield": 0.25, "demand": 0.30},
        "primary_metric": 0.42,
        "snapshots": [
            {
                "snapshot_date": "2013-01-01",
                "n_zips": 5,
                "spearman": 0.5,
                "top_minus_bottom": 0.1,
                "baselines": {"yield_only_spearman": 0.3},
            }
        ],
        "quintile_bins": [[0.05, 0.06, 0.07, 0.08, 0.09]],
        "report_html": "<html><body>Rental Backtest Report (synthetic)</body></html>",
    }


@pytest.fixture
def fake_runner(monkeypatch: pytest.MonkeyPatch):
    """Install ``_fake_runner`` as the module-level runner hook."""
    monkeypatch.setattr(backtest_route, "CURRENT_RUNNER", _fake_runner)
    yield
    monkeypatch.setattr(backtest_route, "CURRENT_RUNNER", None)


def _wait_for_finished_record(
    runs_dir: Path, run_id: str, timeout: float = 5.0
) -> dict:
    """Poll the JSON record until status is terminal (ok/error)."""
    import json as _json

    path = runs_dir / f"{run_id}.json"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists():
            try:
                data = _json.loads(path.read_text())
            except _json.JSONDecodeError:
                data = None
            if data and data.get("status") in {"ok", "error"}:
                return data
        time.sleep(0.05)
    raise AssertionError(f"run {run_id} did not finish within {timeout}s")


# --------------------------------------------------------------------- post /run


def test_post_run_returns_job_and_run_ids(
    client: TestClient, fake_runner, tmp_runs_dir: Path
) -> None:
    r = client.post(
        "/api/backtest/run", json={"start_year": 2013, "end_year": 2015}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["job_id"].startswith("job_")
    assert body["run_id"].startswith("run_")

    data = _wait_for_finished_record(tmp_runs_dir, body["run_id"])
    assert data["status"] == "ok"
    assert data["mode"] == "run"
    assert data["primary_metric"] == 0.42
    assert data["weights"] == {"yield": 0.25, "demand": 0.30}
    assert data["report_relpath"] == f"{body['run_id']}.html"


def test_post_run_rejects_inverted_years(
    client: TestClient, fake_runner
) -> None:
    r = client.post(
        "/api/backtest/run", json={"start_year": 2020, "end_year": 2015}
    )
    assert r.status_code == 400


def test_post_tune_returns_job_and_run_ids(
    client: TestClient, fake_runner, tmp_runs_dir: Path
) -> None:
    r = client.post(
        "/api/backtest/tune",
        json={
            "train_start": 2013,
            "train_end": 2017,
            "validate_start": 2018,
            "validate_end": 2019,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["job_id"].startswith("job_")
    assert body["run_id"].startswith("run_")
    data = _wait_for_finished_record(tmp_runs_dir, body["run_id"])
    assert data["mode"] == "tune"
    assert data["status"] == "ok"


def test_post_tune_rejects_inverted_train_window(
    client: TestClient, fake_runner
) -> None:
    r = client.post(
        "/api/backtest/tune",
        json={
            "train_start": 2020,
            "train_end": 2017,
            "validate_start": 2018,
            "validate_end": 2019,
        },
    )
    assert r.status_code == 400


# --------------------------------------------------------------------- listing


def test_runs_listing_returns_persisted_records(
    client: TestClient, fake_runner, tmp_runs_dir: Path
) -> None:
    r1 = client.post(
        "/api/backtest/run", json={"start_year": 2013, "end_year": 2014}
    ).json()
    r2 = client.post(
        "/api/backtest/run", json={"start_year": 2015, "end_year": 2016}
    ).json()
    _wait_for_finished_record(tmp_runs_dir, r1["run_id"])
    _wait_for_finished_record(tmp_runs_dir, r2["run_id"])

    out = client.get("/api/backtest/runs")
    assert out.status_code == 200
    runs = out.json()
    ids = {r["id"] for r in runs}
    assert {r1["run_id"], r2["run_id"]} <= ids
    for row in runs:
        assert row["status"] in {"ok", "error", "running"}
        assert "primary_metric" in row


def test_runs_listing_empty(client: TestClient) -> None:
    out = client.get("/api/backtest/runs")
    assert out.status_code == 200
    assert out.json() == []


# --------------------------------------------------------------------- detail


def test_run_detail_endpoint(
    client: TestClient, fake_runner, tmp_runs_dir: Path
) -> None:
    body = client.post(
        "/api/backtest/run", json={"start_year": 2013, "end_year": 2014}
    ).json()
    _wait_for_finished_record(tmp_runs_dir, body["run_id"])

    detail = client.get(f"/api/backtest/runs/{body['run_id']}")
    assert detail.status_code == 200
    data = detail.json()
    assert data["id"] == body["run_id"]
    assert data["snapshots"] and data["snapshots"][0]["n_zips"] == 5
    assert data["quintile_bins"] == [[0.05, 0.06, 0.07, 0.08, 0.09]]


def test_run_detail_404_when_missing(client: TestClient) -> None:
    r = client.get("/api/backtest/runs/does_not_exist")
    assert r.status_code == 404


def test_run_detail_rejects_path_traversal(client: TestClient) -> None:
    # FastAPI's path matching usually refuses ``/`` in path params; we
    # accept 400 or 404.
    r = client.get("/api/backtest/runs/..%2Fpasswd")
    assert r.status_code in {400, 404}


# --------------------------------------------------------------------- report


def test_report_endpoint_returns_html(
    client: TestClient, fake_runner, tmp_runs_dir: Path
) -> None:
    body = client.post(
        "/api/backtest/run", json={"start_year": 2013, "end_year": 2014}
    ).json()
    _wait_for_finished_record(tmp_runs_dir, body["run_id"])

    r = client.get(f"/api/backtest/runs/{body['run_id']}/report.html")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert b"Rental Backtest Report" in r.content


def test_report_404_when_missing(client: TestClient) -> None:
    r = client.get("/api/backtest/runs/missing_run/report.html")
    assert r.status_code == 404


# --------------------------------------------------------------------- progress events


def test_run_publishes_progress_events(
    client: TestClient, fake_runner, tmp_runs_dir: Path
) -> None:
    """A connected WebSocket sees ``backtest.started`` + ``finished``."""
    with client.websocket_connect("/api/events") as ws:
        time.sleep(0.1)
        body = client.post(
            "/api/backtest/run", json={"start_year": 2013, "end_year": 2014}
        ).json()
        _wait_for_finished_record(tmp_runs_dir, body["run_id"])

        types: list[str] = []
        for _ in range(2):
            msg = ws.receive_json()
            types.append(msg["type"])
            assert msg["job_id"] == body["job_id"]
        assert "backtest.started" in types
        assert "backtest.finished" in types


# --------------------------------------------------------------------- error path


def test_runner_error_recorded(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_runs_dir: Path
) -> None:
    """A runner that raises must persist ``status=error`` + traceback."""

    def boom(_params, _job_id):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(backtest_route, "CURRENT_RUNNER", boom)
    body = client.post(
        "/api/backtest/run", json={"start_year": 2013, "end_year": 2014}
    ).json()
    data = _wait_for_finished_record(tmp_runs_dir, body["run_id"])
    assert data["status"] == "error"
    assert "synthetic failure" in data["error"]


# --------------------------------------------------------------------- synthetic e2e


def _build_synthetic_con():
    """Replicate the warehouse setup the existing backtest tests use."""
    from rental.db import init_schema

    c = duckdb.connect(":memory:")
    init_schema(c)
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS raw_zillow_zori (
            zcta5 VARCHAR,
            observation_date DATE,
            zori DOUBLE,
            snapshot_date DATE,
            PRIMARY KEY (zcta5, observation_date, snapshot_date)
        )
        """
    )
    z = pd.read_csv(FIXTURE_DIR / "synthetic_zhvi_long.csv", dtype={"zcta5": str})
    z["observation_date"] = pd.to_datetime(z["observation_date"]).dt.date
    z["snapshot_date"] = date(2025, 1, 1)
    z["region_id"] = "0"
    z["state"] = "CA"
    z["metro"] = "Synthetic"
    z["county_name"] = "Test"
    c.register("_z", z)
    c.execute(
        """
        INSERT INTO raw_zillow_zhvi
        SELECT region_id, zcta5, state, metro, county_name,
               observation_date, zhvi, snapshot_date FROM _z
        """
    )
    c.unregister("_z")
    r = pd.read_csv(FIXTURE_DIR / "synthetic_zori_long.csv", dtype={"zcta5": str})
    r["observation_date"] = pd.to_datetime(r["observation_date"]).dt.date
    r["snapshot_date"] = date(2025, 1, 1)
    r["region_id"] = "0"
    r["state"] = "CA"
    r["metro"] = "Synthetic"
    r["county_name"] = "Test"
    c.register("_r", r)
    c.execute(
        """
        INSERT INTO raw_zillow_zori
        SELECT region_id, zcta5, state, metro, county_name,
               observation_date, zori, snapshot_date FROM _r
        """
    )
    c.unregister("_r")
    return c


def test_run_with_synthetic_data(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_runs_dir: Path,
) -> None:
    """Drive the real ``run_backtest`` + ``render_report`` against the
    synthetic DuckDB data, going through the route. We swap the
    connection factory inside the default runner — not the runner
    itself — so the rest of the plumbing is exercised end-to-end.
    """
    from rental.backtest import run_backtest
    from rental.backtest.report import render_report

    def synthetic_runner(params, _job_id):
        con = _build_synthetic_con()

        def yield_only(features):
            out = features[["zcta5"]].copy()
            out["score"] = features["gross_yield_monthly_pct"].fillna(0.0)
            return out

        dates = [
            date(y, 1, 31)
            for y in range(params["start_year"], params["end_year"] + 1)
        ]
        result = run_backtest(con, dates, yield_only)
        from tempfile import NamedTemporaryFile

        with NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        render_report(result, tmp_path)
        html = tmp_path.read_text()
        tmp_path.unlink(missing_ok=True)

        snapshots_payload = []
        bins = []
        rhos = []
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
            if s.spearman == s.spearman:
                rhos.append(float(s.spearman))

        return {
            "mode": "run",
            "weights": {},
            "primary_metric": sum(rhos) / len(rhos) if rhos else None,
            "snapshots": snapshots_payload,
            "quintile_bins": bins,
            "report_html": html,
        }

    monkeypatch.setattr(backtest_route, "CURRENT_RUNNER", synthetic_runner)
    body = client.post(
        "/api/backtest/run", json={"start_year": 2013, "end_year": 2014}
    ).json()
    data = _wait_for_finished_record(tmp_runs_dir, body["run_id"], timeout=20.0)
    assert data["status"] == "ok"
    assert (tmp_runs_dir / f"{body['run_id']}.html").exists()

    report = client.get(f"/api/backtest/runs/{body['run_id']}/report.html")
    assert report.status_code == 200
    assert b"Rental Backtest Report" in report.content
