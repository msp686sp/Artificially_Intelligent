"""Tests for /api/manifest and /api/manifest/{source}."""

from __future__ import annotations


def test_manifest_lists_entries(client):
    resp = client.get("/api/manifest")
    assert resp.status_code == 200
    body = resp.json()
    assert "entries" in body
    # The conftest's refresh of zillow_zhvi must have created an entry.
    sources = {e["source"] for e in body["entries"]}
    assert "zillow_zhvi" in sources


def test_manifest_entry_ok(client):
    resp = client.get("/api/manifest/zillow_zhvi")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "zillow_zhvi"
    assert body["status"] in {"ok", "error"}
    assert body["rows_loaded"] >= 0


def test_manifest_entry_unknown_returns_404(client):
    resp = client.get("/api/manifest/does_not_exist")
    assert resp.status_code == 404
