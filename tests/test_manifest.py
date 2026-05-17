"""Refresh manifest unit tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb

from rental.db import init_schema
from rental.manifest import (
    ManifestEntry,
    load_manifest,
    staleness_days,
    update_manifest,
)
from rental.sources import ZillowZHVISource

FIXTURE = Path(__file__).parent / "fixtures" / "zhvi_sample.csv"


def test_load_manifest_missing_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("RENTAL_MANIFEST_PATH", str(tmp_path / "manifest.json"))
    assert load_manifest() == {}


def test_load_manifest_malformed_returns_empty(tmp_path, monkeypatch):
    target = tmp_path / "manifest.json"
    target.write_text("{not json")
    monkeypatch.setenv("RENTAL_MANIFEST_PATH", str(target))
    assert load_manifest() == {}


def test_update_manifest_writes_and_reloads(tmp_path, monkeypatch):
    target = tmp_path / "manifest.json"
    monkeypatch.setenv("RENTAL_MANIFEST_PATH", str(target))

    entry = update_manifest("zillow_zhvi", rows_loaded=42, status="ok")
    assert entry.rows_loaded == 42
    assert target.exists()

    on_disk = json.loads(target.read_text())
    assert "zillow_zhvi" in on_disk
    assert on_disk["zillow_zhvi"]["rows_loaded"] == 42
    assert on_disk["zillow_zhvi"]["status"] == "ok"

    reloaded = load_manifest()
    assert set(reloaded) == {"zillow_zhvi"}
    assert reloaded["zillow_zhvi"].rows_loaded == 42


def test_update_manifest_upsert_preserves_other_sources(tmp_path, monkeypatch):
    target = tmp_path / "manifest.json"
    monkeypatch.setenv("RENTAL_MANIFEST_PATH", str(target))

    update_manifest("source_a", rows_loaded=1, status="ok")
    update_manifest("source_b", rows_loaded=2, status="ok")
    update_manifest("source_a", rows_loaded=10, status="ok")  # update

    loaded = load_manifest()
    assert set(loaded) == {"source_a", "source_b"}
    assert loaded["source_a"].rows_loaded == 10
    assert loaded["source_b"].rows_loaded == 2


def test_update_manifest_records_error_status(tmp_path, monkeypatch):
    target = tmp_path / "manifest.json"
    monkeypatch.setenv("RENTAL_MANIFEST_PATH", str(target))

    update_manifest("zillow_zhvi", rows_loaded=0, status="error", error="boom")
    loaded = load_manifest()
    assert loaded["zillow_zhvi"].status == "error"
    assert loaded["zillow_zhvi"].error == "boom"


def test_staleness_days_uses_utc():
    past = datetime.now(UTC) - timedelta(days=10)
    entry = ManifestEntry("x", past, rows_loaded=1, status="ok")
    assert 9.99 <= staleness_days(entry) <= 10.01


def test_staleness_days_naive_datetime_treated_as_utc():
    naive = datetime.utcnow() - timedelta(days=3)
    entry = ManifestEntry("x", naive, rows_loaded=1, status="ok")
    assert 2.99 <= staleness_days(entry) <= 3.01


def test_source_refresh_updates_manifest(tmp_path, monkeypatch):
    """Hook test: the base-class extension must populate the manifest."""
    target = tmp_path / "manifest.json"
    monkeypatch.setenv("RENTAL_MANIFEST_PATH", str(target))

    con = duckdb.connect(":memory:")
    init_schema(con)
    result = ZillowZHVISource().refresh(con, raw_dir=tmp_path / "raw", from_fixture=FIXTURE)
    assert result.status == "ok"

    loaded = load_manifest()
    assert "zillow_zhvi" in loaded
    assert loaded["zillow_zhvi"].rows_loaded == 15
    assert loaded["zillow_zhvi"].status == "ok"


def test_source_refresh_records_failure_in_manifest(tmp_path, monkeypatch):
    target = tmp_path / "manifest.json"
    monkeypatch.setenv("RENTAL_MANIFEST_PATH", str(target))

    con = duckdb.connect(":memory:")
    init_schema(con)

    class _Boom(ZillowZHVISource):
        name = "zillow_zhvi_boom"

        def load(self, con, raw_path):  # type: ignore[override]
            raise RuntimeError("kaboom")

    result = _Boom().refresh(con, raw_dir=tmp_path / "raw", from_fixture=FIXTURE)
    assert result.status == "error"

    loaded = load_manifest()
    assert loaded["zillow_zhvi_boom"].status == "error"
    assert "kaboom" in (loaded["zillow_zhvi_boom"].error or "")
