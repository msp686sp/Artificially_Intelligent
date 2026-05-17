"""Tests for ``POST /api/sql``.

Coverage:
- Happy path: SELECT returns rows + columns + row_count + elapsed_ms.
- WITH / CTE-leading queries pass the read-only check.
- DROP / INSERT / UPDATE / DELETE / CREATE / ALTER are rejected with 400.
- ``read_only=false`` lets a CREATE pass through.
- Multi-statement input is rejected with 400.
- Empty / whitespace-only input is rejected with 400.
- Hard row cap kicks in for large results (synthetic range table).
- Unparseable input → 400 (not 500).
"""

from __future__ import annotations


def test_select_returns_rows(client):
    r = client.post(
        "/api/sql",
        json={"query": "SELECT 1 AS one, 'a' AS letter"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["columns"] == ["one", "letter"]
    assert body["rows"] == [[1, "a"]]
    assert body["row_count"] == 1
    assert body["elapsed_ms"] >= 0
    assert body["query"] == "SELECT 1 AS one, 'a' AS letter"


def test_select_with_cte_passes_read_only(client):
    r = client.post(
        "/api/sql",
        json={"query": "WITH x AS (SELECT 42 AS v) SELECT v FROM x"},
    )
    assert r.status_code == 200
    assert r.json()["rows"] == [[42]]


def test_drop_table_rejected(client):
    r = client.post("/api/sql", json={"query": "DROP TABLE zip_scores"})
    assert r.status_code == 400
    assert "not allowed" in r.json()["detail"].lower()


def test_insert_rejected(client):
    r = client.post(
        "/api/sql",
        json={"query": "INSERT INTO zip_scores (zcta5) VALUES ('99999')"},
    )
    assert r.status_code == 400


def test_update_rejected(client):
    r = client.post(
        "/api/sql",
        json={"query": "UPDATE zip_scores SET market_score = 1.0 WHERE zcta5 = '10025'"},
    )
    assert r.status_code == 400


def test_delete_rejected(client):
    r = client.post(
        "/api/sql",
        json={"query": "DELETE FROM zip_scores WHERE zcta5 = '10025'"},
    )
    assert r.status_code == 400


def test_create_rejected(client):
    r = client.post("/api/sql", json={"query": "CREATE TABLE foo (a INT)"})
    assert r.status_code == 400


def test_alter_rejected(client):
    r = client.post("/api/sql", json={"query": "ALTER TABLE zip_scores ADD COLUMN x INT"})
    assert r.status_code == 400


def test_read_only_false_allows_create(client):
    r = client.post(
        "/api/sql",
        json={
            "query": "CREATE TABLE _scratch (a INT)",
            "read_only": False,
        },
    )
    # CREATE returns no rows but should not be 4xx.
    assert r.status_code == 200, r.text


def test_multi_statement_rejected(client):
    r = client.post("/api/sql", json={"query": "SELECT 1; SELECT 2"})
    assert r.status_code == 400
    assert "multi-statement" in r.json()["detail"].lower()


def test_empty_query_rejected(client):
    r = client.post("/api/sql", json={"query": "   "})
    assert r.status_code == 400


def test_parse_error_is_400(client):
    r = client.post("/api/sql", json={"query": "SELECT FROM WHERE"})
    assert r.status_code == 400


def test_explain_is_allowed(client):
    r = client.post("/api/sql", json={"query": "EXPLAIN SELECT 1"})
    assert r.status_code == 200


def test_row_cap_truncates(client):
    """A query that yields >limit rows should return exactly ``limit``."""
    r = client.post(
        "/api/sql",
        json={
            "query": "SELECT * FROM range(0, 50)",
            "limit": 10,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["row_count"] == 10
    assert len(body["rows"]) == 10


def test_default_limit_caps_at_1000(client):
    """A query yielding >1000 rows with default limit returns 1000."""
    r = client.post(
        "/api/sql",
        json={"query": "SELECT * FROM range(0, 5000)"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["row_count"] == 1000


def test_hard_cap_at_10000(client):
    """Even requesting a limit above the cap clamps to 10,000."""
    # Pydantic validates limit<=10000 so we expect 422, not 200 with cap.
    r = client.post(
        "/api/sql",
        json={"query": "SELECT * FROM range(0, 20000)", "limit": 50_000},
    )
    assert r.status_code == 422


def test_query_against_seeded_zhvi(client):
    """End-to-end: the bundled fixture is queryable from the workbench."""
    r = client.post(
        "/api/sql",
        json={
            "query": "SELECT count(*) AS n FROM raw_zillow_zhvi WHERE zcta5 = '10025'",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["columns"] == ["n"]
    # ZHVI fixture has 3 monthly rows for 10025 (Dec 2023, Jan/Feb 2024).
    assert body["rows"][0][0] >= 1


def test_pragma_is_allowed(client):
    """PRAGMA queries should be read-only-safe (e.g. schema introspection)."""
    r = client.post("/api/sql", json={"query": "PRAGMA database_list"})
    assert r.status_code == 200
