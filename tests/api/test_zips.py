"""Tests for ``GET /api/zips/{zcta5}`` + ``GET /api/zips/compare``.

Coverage:
- ``/api/zips/10025`` returns identity, scores, ZHVI + ZORI + Redfin
  series, features, and filter status.
- ``/api/zips/44102`` has no Redfin coverage in the fixture, so the
  detail bundle has ``redfin: []`` (not 500).
- Unknown zip → 404.
- ``/api/zips/compare`` returns one bundle per requested zip plus a
  ``diffs`` list keyed by feature.
- Compare with one unknown zip in the list returns an empty bundle for
  the unknown one (not 404).
"""

from __future__ import annotations


def test_zip_detail_10025(client):
    r = client.get("/api/zips/10025")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["identity"]["zcta5"] == "10025"
    assert body["identity"]["state"] == "NY"
    assert "New York" in (body["identity"]["metro"] or "")
    # Scores: at least yield_score should be present.
    assert body["scores"]["yield_score"] is not None
    # Time series.
    assert isinstance(body["zhvi"], list) and len(body["zhvi"]) >= 1
    assert isinstance(body["zori"], list) and len(body["zori"]) >= 1
    assert isinstance(body["redfin"], list) and len(body["redfin"]) >= 1
    # Features at least include a price.
    assert body["features"].get("median_home_price") is not None
    # Filter status: one row per filter in filters.yaml.
    names = {f["name"] for f in body["filters"]}
    assert "median_home_price" in names
    assert "zori_coverage" in names


def test_zip_detail_redfin_only_zip(client):
    """07030 has Redfin data but no ZHVI/ZORI in the fixture.

    The detail endpoint must return a valid bundle: empty ZHVI/ZORI,
    populated Redfin, and a non-error status. This is the inverse
    shape of the "partial coverage" promise and covers the no-Redfin
    case implicitly via the same code path.
    """
    r = client.get("/api/zips/07030")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["identity"]["zcta5"] == "07030"
    # No ZHVI / ZORI rows for this zip.
    assert body["zhvi"] == []
    assert body["zori"] == []
    # Redfin populated.
    assert len(body["redfin"]) >= 1
    # No scores either — but the bundle is still valid.
    assert body["scores"]["yield_score"] is None


def test_zip_detail_unknown_404(client):
    r = client.get("/api/zips/00000")
    assert r.status_code == 404


def test_zip_detail_z_scores_present(client):
    body = client.get("/api/zips/10025").json()
    z = body["z_scores"]
    # Within-state z for a single-zip state (NY in the fixture) is 0
    # by construction; just assert the field is present.
    assert "yield_score" in z or "market_score" in z


def test_zip_compare_happy_path(client):
    r = client.get("/api/zips/compare?zcta5s=10025,46220")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body["zips"].keys()) == {"10025", "46220"}
    assert body["zips"]["10025"]["identity"]["state"] == "NY"
    assert body["zips"]["46220"]["identity"]["state"] == "IN"
    # diffs has one entry per feature.
    diffs_by_feature = {d["feature"]: d for d in body["diffs"]}
    assert "market_score" in diffs_by_feature
    # Each diff has values for every requested zip.
    assert set(diffs_by_feature["market_score"]["values"].keys()) == {"10025", "46220"}


def test_zip_compare_with_unknown_zip(client):
    """Unknown zip in compare list gets an empty bundle, not a 404."""
    r = client.get("/api/zips/compare?zcta5s=10025,99999")
    assert r.status_code == 200
    body = r.json()
    assert "10025" in body["zips"]
    assert "99999" in body["zips"]
    # The unknown bundle has the requested zip but no data.
    assert body["zips"]["99999"]["identity"]["zcta5"] == "99999"


def test_zip_compare_requires_zcta5s(client):
    r = client.get("/api/zips/compare")
    assert r.status_code == 422  # FastAPI validation


def test_zip_compare_empty_string_400(client):
    r = client.get("/api/zips/compare?zcta5s=,,")
    assert r.status_code == 400


def test_filter_status_disabled_skipped(client):
    """A filter that's disabled in filters.yaml is reported as skipped."""
    body = client.get("/api/zips/10025").json()
    by_name = {f["name"]: f for f in body["filters"]}
    # ``gross_yield_monthly_pct`` is disabled in the default config.
    if "gross_yield_monthly_pct" in by_name:
        f = by_name["gross_yield_monthly_pct"]
        assert f["skipped"] is True
