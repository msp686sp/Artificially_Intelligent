"""Tests for the ``/api/charts/*`` endpoints.

Coverage:
- ``score-distribution`` returns the requested number of bins (or
  fewer with sparse data) and rejects unknown ``dim``.
- ``feature-vs-score`` returns scatter points; invalid feature/score
  → 400.
- ``zhvi`` / ``zori`` / ``redfin`` return time-series payloads for
  known zips and empty arrays for unknown zips.
- ``since`` query param restricts ZHVI/ZORI/Redfin.
"""

from __future__ import annotations


def test_score_distribution_default(client):
    r = client.get("/api/charts/score-distribution")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["dim"] == "market_score"
    assert isinstance(body["bins"], list)
    # With 5 fixture rows and 20 bins, some bins will be empty but the
    # bin count should still be 20.
    assert len(body["bins"]) == 20
    # Counts sum to <= the number of finite scores (≤ 5 fixture rows).
    total = sum(b["count"] for b in body["bins"])
    assert 0 < total <= 5


def test_score_distribution_custom_bins(client):
    r = client.get("/api/charts/score-distribution?dim=yield_score&bins=5")
    assert r.status_code == 200
    body = r.json()
    assert body["dim"] == "yield_score"
    assert len(body["bins"]) == 5


def test_score_distribution_invalid_dim(client):
    r = client.get("/api/charts/score-distribution?dim=foo")
    assert r.status_code == 400


def test_feature_vs_score_happy_path(client):
    r = client.get(
        "/api/charts/feature-vs-score"
        "?feature=gross_yield_monthly_pct&score=market_score"
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["feature"] == "gross_yield_monthly_pct"
    assert body["score"] == "market_score"
    assert isinstance(body["points"], list)
    # At least one point in the seeded fixture (every fixture zip has
    # both ZHVI + ZORI so the yield feature is defined for all 5).
    assert len(body["points"]) >= 1
    p = body["points"][0]
    assert {"zcta5", "x", "y"}.issubset(p.keys())


def test_feature_vs_score_invalid_feature(client):
    r = client.get("/api/charts/feature-vs-score?feature=foo&score=market_score")
    assert r.status_code == 400


def test_feature_vs_score_invalid_score(client):
    r = client.get(
        "/api/charts/feature-vs-score"
        "?feature=gross_yield_monthly_pct&score=bogus"
    )
    assert r.status_code == 400


def test_zhvi_known_zip(client):
    r = client.get("/api/charts/zhvi/10025")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    assert {"date", "value"}.issubset(body[0].keys())


def test_zori_known_zip(client):
    r = client.get("/api/charts/zori/10025")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) >= 1


def test_redfin_known_zip(client):
    r = client.get("/api/charts/redfin/10025")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    p = body[0]
    assert {"period_end", "median_dom", "median_sale_to_list", "inventory"}.issubset(
        p.keys()
    )


def test_zhvi_unknown_zip_empty(client):
    r = client.get("/api/charts/zhvi/00000")
    assert r.status_code == 200
    assert r.json() == []


def test_redfin_unknown_zip_empty(client):
    r = client.get("/api/charts/redfin/00000")
    assert r.status_code == 200
    assert r.json() == []


def test_zhvi_since_filter(client):
    """Restricting ``since`` to the future returns an empty array."""
    r = client.get("/api/charts/zhvi/10025?since=2099-01-01")
    assert r.status_code == 200
    assert r.json() == []


def test_redfin_since_filter(client):
    r = client.get("/api/charts/redfin/10025?since=2099-01-01")
    assert r.status_code == 200
    assert r.json() == []


def test_score_distribution_empty_warehouse(empty_client):
    r = empty_client.get("/api/charts/score-distribution")
    assert r.status_code == 200
    assert r.json()["bins"] == []
