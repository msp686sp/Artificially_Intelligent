"""Tests for /api/schema (warehouse tree)."""

from __future__ import annotations


def test_schema_lists_tables(client):
    resp = client.get("/api/schema")
    assert resp.status_code == 200
    body = resp.json()
    assert "tables" in body
    names = {t["name"] for t in body["tables"]}
    # Schema.sql creates these tables; init_schema in the fixture ensures
    # they exist.
    assert "raw_zillow_zhvi" in names
    assert "refresh_log" in names
    assert "geo_zcta" in names


def test_schema_table_has_columns_and_row_count(client):
    body = client.get("/api/schema").json()
    by_name = {t["name"]: t for t in body["tables"]}
    zhvi = by_name["raw_zillow_zhvi"]
    assert zhvi["kind"] == "table"
    col_names = {c["name"] for c in zhvi["columns"]}
    assert "zcta5" in col_names and "zhvi" in col_names
    # Fixture-loaded — row count should be positive.
    assert zhvi["row_count"] is not None and zhvi["row_count"] > 0
