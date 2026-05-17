"""Tests for /api/sources, /api/sources/{name}, .../preview, .../schema, .../refresh."""

from __future__ import annotations

import time
from pathlib import Path

from rental.sources import REGISTRY


def test_list_sources_returns_full_registry(client):
    resp = client.get("/api/sources")
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    # Plan-mandated: 12 entries matching REGISTRY.
    assert len(items) == len(REGISTRY) == 12
    names = {item["name"] for item in items}
    assert names == set(REGISTRY)


def test_list_sources_carries_metadata(client):
    items = client.get("/api/sources").json()
    by_name = {item["name"]: item for item in items}
    zhvi = by_name["zillow_zhvi"]
    assert zhvi["status"] == "ok"
    assert zhvi["rows_loaded"] is not None and zhvi["rows_loaded"] > 0
    assert zhvi["warehouse_rows"] is not None and zhvi["warehouse_rows"] > 0
    assert zhvi["source_url"] and zhvi["source_url"].startswith("http")
    assert zhvi["cadence"]


def test_get_source_detail_ok(client):
    resp = client.get("/api/sources/zillow_zhvi")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "zillow_zhvi"
    assert body["status"] == "ok"


def test_get_source_unknown_returns_404(client):
    resp = client.get("/api/sources/does_not_exist")
    assert resp.status_code == 404


def test_source_schema_ok(client):
    resp = client.get("/api/sources/zillow_zhvi/schema")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "zillow_zhvi"
    assert body["table"] == "raw_zillow_zhvi"
    col_names = {c["name"] for c in body["columns"]}
    assert {"zcta5", "observation_date", "zhvi"}.issubset(col_names)


def test_source_schema_unknown_returns_404(client):
    resp = client.get("/api/sources/does_not_exist/schema")
    assert resp.status_code == 404


def test_source_preview_pagination(client):
    resp = client.get("/api/sources/zillow_zhvi/preview?limit=2&offset=0")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "zillow_zhvi"
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert body["row_count"] > 0
    assert len(body["rows"]) <= 2
    if body["rows"]:
        row = body["rows"][0]
        assert "zcta5" in row


def test_source_preview_limit_validation(client):
    # Negative offset rejected.
    resp = client.get("/api/sources/zillow_zhvi/preview?offset=-1")
    assert resp.status_code == 422
    # Limit too large rejected.
    resp = client.get("/api/sources/zillow_zhvi/preview?limit=10000")
    assert resp.status_code == 422


def test_refresh_kickoff_returns_job_id(client, tmp_path):
    # Use a different bundled fixture path to avoid network: route through
    # the existing zhvi sample.
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "zhvi_sample.csv"
    resp = client.post(
        "/api/sources/zillow_zhvi/refresh",
        json={"from_fixture": str(fixture)},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert "job_id" in body and body["job_id"]
    assert body["source"] == "zillow_zhvi"
    assert body["from_fixture"] == str(fixture)


def test_refresh_bad_fixture_path_returns_400(client):
    resp = client.post(
        "/api/sources/zillow_zhvi/refresh",
        json={"from_fixture": "/no/such/file.csv"},
    )
    assert resp.status_code == 400


def test_refresh_unknown_source_returns_404(client):
    resp = client.post("/api/sources/does_not_exist/refresh", json={})
    assert resp.status_code == 404


def test_refresh_publishes_events(client):
    """Refresh must publish events to api.progress.bus."""
    from api.progress import bus

    received: list[dict] = []
    queue = bus.subscribe()

    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "zhvi_sample.csv"
    resp = client.post(
        "/api/sources/zillow_zhvi/refresh",
        json={"from_fixture": str(fixture)},
    )
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    # Drain the queue with a short timeout — the refresh runs on a thread
    # so we may need to poll briefly for events to arrive.
    deadline = time.time() + 5.0
    seen_types: set[str] = set()
    while time.time() < deadline and "refresh.completed" not in seen_types:
        try:
            event = queue.get_nowait()
        except Exception:
            time.sleep(0.05)
            continue
        if event.job_id == job_id:
            received.append(event.to_dict())
            seen_types.add(event.type)

    bus.unsubscribe(queue)
    assert "refresh.started" in seen_types
    assert "refresh.completed" in seen_types or "refresh.failed" in seen_types
