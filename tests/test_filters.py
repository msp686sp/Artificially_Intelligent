from pathlib import Path

import pandas as pd
import pytest
import yaml

from rental.filters import apply_filters, load_filter_config

SCORES_FIXTURE = Path(__file__).parent / "fixtures" / "zip_scores_stub.csv"
FEATURES_FIXTURE = Path(__file__).parent / "fixtures" / "zip_features_stub.csv"


def _scores() -> pd.DataFrame:
    df = pd.read_csv(SCORES_FIXTURE, dtype={"zcta5": str})
    # Synthesize a market_score column the way `rank` would.
    df["market_score"] = (
        0.25 * df["yield_score"]
        + 0.30 * df["demand_score"]
        + 0.20 * df["supply_score"]
        + 0.20 * df["operability_score"]
        + -0.05 * df["risk_score"]
    )
    return df[["zcta5", "state", "metro", "county_name", "market_score"]]


def _features() -> pd.DataFrame:
    return pd.read_csv(FEATURES_FIXTURE, dtype={"zcta5": str})


def test_default_filters_apply_price_band_and_zori_coverage(tmp_path):
    # Default config: price band 80k-250k ON; zori_coverage 24mo ON;
    # all others OFF.
    out, audit = apply_filters(_scores(), _features(), filters_path="config/filters.yaml")
    # 10025 (1.47M) and 60614 (618k) excluded by price band.
    # 44102 ($91k passes price band) excluded by zori_coverage < 24mo (12mo).
    keep = set(out["zcta5"])
    assert keep == {"46220", "38104"}
    assert audit.rows_in == 5
    assert audit.rows_out == 2
    # Audit should record the kills.
    assert audit.per_filter.get("median_home_price", 0) >= 2
    assert audit.per_filter.get("zori_coverage", 0) >= 1
    # The opt-in filters are skipped, not applied.
    assert "gross_yield_monthly_pct" in audit.skipped


def test_disabled_filters_are_not_applied(tmp_path):
    # Write a config where every filter is disabled — nothing should drop.
    cfg = {
        "filters": {
            "median_home_price": {"enabled": False, "min": 80000, "max": 250000},
            "zori_coverage": {"enabled": False, "min_months": 24},
            "gross_yield_monthly_pct": {"enabled": False, "min": 0.8},
            "exclude_rent_controlled": {"enabled": False},
            "exclude_high_climate_risk": {"enabled": False},
            "exclude_shrinking_metros": {"enabled": False, "population_cagr_min": -0.0025},
        }
    }
    p = tmp_path / "filters.yaml"
    p.write_text(yaml.safe_dump(cfg))
    out, audit = apply_filters(_scores(), _features(), filters_path=p)
    assert len(out) == 5
    assert audit.rows_out == 5
    assert len(audit.skipped) == 6
    assert audit.per_filter == {}


def test_opt_in_yield_filter_when_enabled(tmp_path):
    cfg = {"filters": {
        "gross_yield_monthly_pct": {"enabled": True, "min": 1.0},
    }}
    p = tmp_path / "filters.yaml"
    p.write_text(yaml.safe_dump(cfg))
    out, audit = apply_filters(_scores(), _features(), filters_path=p)
    # Yields >= 1.0%: 38104 (1.10) and 44102 (1.25) only.
    assert set(out["zcta5"]) == {"38104", "44102"}
    assert audit.per_filter["gross_yield_monthly_pct"] == 3


def test_zori_coverage_excludes_thin_data(tmp_path):
    cfg = {"filters": {
        "zori_coverage": {"enabled": True, "min_months": 24},
    }}
    p = tmp_path / "filters.yaml"
    p.write_text(yaml.safe_dump(cfg))
    out, audit = apply_filters(_scores(), _features(), filters_path=p)
    # 44102 has 12 months of coverage; rest have >= 36.
    assert "44102" not in set(out["zcta5"])
    assert audit.per_filter["zori_coverage"] == 1


def test_zori_coverage_excludes_missing_data(tmp_path):
    cfg = {"filters": {
        "zori_coverage": {"enabled": True, "min_months": 24},
    }}
    p = tmp_path / "filters.yaml"
    p.write_text(yaml.safe_dump(cfg))
    scores = _scores().head(2).copy()
    # Strip the feature column for one zip to simulate missing data.
    features = _features().copy()
    features.loc[features["zcta5"] == "10025", "zori_coverage_months"] = None
    out, _ = apply_filters(scores, features, filters_path=p)
    # 10025 had no coverage data → excluded.
    assert "10025" not in set(out["zcta5"])


def test_exclude_rent_controlled_when_enabled(tmp_path):
    cfg = {"filters": {
        "exclude_rent_controlled": {"enabled": True},
    }}
    p = tmp_path / "filters.yaml"
    p.write_text(yaml.safe_dump(cfg))
    out, audit = apply_filters(_scores(), _features(), filters_path=p)
    # 10025 is rent-controlled in the fixture.
    assert "10025" not in set(out["zcta5"])
    assert audit.per_filter["exclude_rent_controlled"] == 1


def test_exclude_shrinking_metros_when_enabled(tmp_path):
    cfg = {"filters": {
        "exclude_shrinking_metros": {"enabled": True, "population_cagr_min": -0.0025},
    }}
    p = tmp_path / "filters.yaml"
    p.write_text(yaml.safe_dump(cfg))
    out, _ = apply_filters(_scores(), _features(), filters_path=p)
    # 38104 (-0.4%) and 44102 (-0.7%) fall below the floor.
    keep = set(out["zcta5"])
    assert "38104" not in keep
    assert "44102" not in keep


def test_missing_feature_column_skips_filter_gracefully(tmp_path):
    # Filter enabled, but the underlying feature column isn't in the
    # frame at all — should be reported as skipped, not crash.
    cfg = {"filters": {
        "exclude_high_climate_risk": {"enabled": True},
    }}
    p = tmp_path / "filters.yaml"
    p.write_text(yaml.safe_dump(cfg))
    out, audit = apply_filters(
        _scores(),
        _features().drop(columns=["high_climate_risk"]),
        filters_path=p,
    )
    assert len(out) == 5
    assert "exclude_high_climate_risk" in audit.skipped


def test_empty_input_returns_empty():
    df = pd.DataFrame(columns=["zcta5", "market_score"])
    out, audit = apply_filters(df, pd.DataFrame(), filters_path="config/filters.yaml")
    assert out.empty
    assert audit.rows_in == 0
    assert audit.rows_out == 0


def test_load_filter_config_reads_yaml():
    cfg = load_filter_config("config/filters.yaml")
    assert "median_home_price" in cfg
    assert cfg["median_home_price"]["enabled"] is True
    assert cfg["median_home_price"]["min"] == pytest.approx(80000)
