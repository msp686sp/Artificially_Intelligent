"""Tests for /api/health and /api/version."""

from __future__ import annotations


def test_health_returns_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert isinstance(body["version"], str)
    assert isinstance(body["uptime_s"], (int, float))
    assert body["uptime_s"] >= 0


def test_version_payload_shape(client):
    resp = client.get("/api/version")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"api", "app", "python"}
    # Python version like "3.12.x"
    assert body["python"].count(".") >= 1


def test_openapi_advertises_routes(client):
    resp = client.get("/api/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert "/api/health" in paths
    assert "/api/sources" in paths
    assert "/api/manifest" in paths
    assert "/api/schema" in paths
