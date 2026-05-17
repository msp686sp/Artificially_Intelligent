"""YieldScore + yield_features tests.

Covers:
  - feature math (gross_yield + 5yr CAGR) against the bundled ZHVI/ZORI fixtures
  - within-state z-score normalization (single-state = score == 0; multi-state isolates)
  - graceful degradation when tax/insurance columns are absent
  - weight renormalization when a feature is dropped
"""

from pathlib import Path

import duckdb
import pandas as pd
import pytest
import yaml

from rental.db import init_schema
from rental.features import yield_features
from rental.scoring import yield_score
from rental.sources import ZillowZHVISource, ZillowZORISource

ZHVI_FIXTURE = Path(__file__).parent / "fixtures" / "zhvi_sample.csv"
ZORI_FIXTURE = Path(__file__).parent / "fixtures" / "zori_sample.csv"


def _con_with_zhvi_and_zori():
    con = duckdb.connect(":memory:")
    init_schema(con)
    ZillowZHVISource().load(con, ZHVI_FIXTURE)
    ZillowZORISource().load(con, ZORI_FIXTURE)
    return con


# ---------- yield_features ------------------------------------------------


def test_yield_features_row_per_zip():
    con = _con_with_zhvi_and_zori()
    df = yield_features(con)
    # 5 zips in the intersection.
    assert len(df) == 5
    assert set(df.columns) >= {
        "zcta5", "state", "latest_zhvi", "latest_zori",
        "gross_yield_monthly_pct", "rent_growth_5yr_cagr",
        "zori_coverage_months",
    }


def test_gross_yield_formula_matches_spec():
    con = _con_with_zhvi_and_zori()
    df = yield_features(con).set_index("zcta5")
    # Per locked plan, gross_yield_monthly_pct = (rent / price) × 100.
    # Cleveland 44102: ZORI=960, ZHVI=91500 → 960/91500*100 = ~1.0492%/mo.
    row = df.loc["44102"]
    expected = (row["latest_zori"] / row["latest_zhvi"]) * 100.0
    assert row["gross_yield_monthly_pct"] == pytest.approx(expected, rel=1e-9)
    assert row["gross_yield_monthly_pct"] == pytest.approx(1.0492, rel=1e-3)


def test_rent_growth_5yr_cagr_uses_fallback_for_short_history():
    """Fixture has ZORI from 2019-02 → 2024-02, ~60 months; CAGR should be
    a reasonable positive number for all zips (rents went up)."""
    con = _con_with_zhvi_and_zori()
    df = yield_features(con).set_index("zcta5")
    for z in ("10025", "60614", "46220", "38104", "44102"):
        cagr = df.loc[z, "rent_growth_5yr_cagr"]
        assert cagr is not None and not pd.isna(cagr)
        # All fixture zips show ~6–10%/yr rent growth — sanity-check the band.
        assert 0.02 < cagr < 0.20


# ---------- yield_score: within-state z ------------------------------------


def _two_state_features() -> pd.DataFrame:
    # Two states × three zips each, gross_yield rising within each state.
    # The middle value in each state should land near z=0 by median+MAD.
    return pd.DataFrame({
        "zcta5":              ["10001", "10002", "10003", "60601", "60602", "60603"],
        "state":              ["NY",    "NY",    "NY",    "IL",    "IL",    "IL"],
        "gross_yield":        [4.0,     6.0,     10.0,    8.0,     10.0,    14.0],
        "effective_tax_rate": [0.012,   0.013,   0.014,   0.020,   0.022,   0.025],
        "insurance_rate":     [0.005,   0.0055,  0.006,   0.008,   0.0085,  0.009],
    })


def test_yield_score_within_state_normalization():
    df = _two_state_features()
    out = yield_score(df).set_index("zcta5")
    # The median zip in each state should be near zero on the gross-yield z.
    assert out.loc["10002", "z_gross_yield"] == pytest.approx(0.0, abs=1e-9)
    assert out.loc["60602", "z_gross_yield"] == pytest.approx(0.0, abs=1e-9)
    # Highest-yield zip in each state should outrank the lowest within that state.
    assert out.loc["10003", "yield_score"] > out.loc["10001", "yield_score"]
    assert out.loc["60603", "yield_score"] > out.loc["60601", "yield_score"]


def test_yield_score_tax_and_insurance_are_negatively_signed():
    df = _two_state_features()
    out = yield_score(df).set_index("zcta5")
    # In NY, 10003 has the *highest* tax → its z_effective_tax_rate
    # should be the most negative (we negate; higher tax = worse).
    ny = out.loc[["10001", "10002", "10003"]]
    assert ny.loc["10003", "z_effective_tax_rate"] < ny.loc["10001", "z_effective_tax_rate"]
    assert ny.loc["10003", "z_insurance_rate"] < ny.loc["10001", "z_insurance_rate"]


def test_yield_score_handles_missing_tax_and_insurance(caplog):
    df = _two_state_features().drop(columns=["effective_tax_rate", "insurance_rate"])
    with caplog.at_level("WARNING"):
        out = yield_score(df).set_index("zcta5")
    # Score still produced, derived only from gross_yield.
    assert "yield_score" in out.columns
    assert "z_gross_yield" in out.columns
    assert "z_effective_tax_rate" not in out.columns
    # Warning logged for each skipped feature.
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    msgs = " ".join(r.getMessage() for r in warnings)
    assert "effective_tax_rate" in msgs
    assert "insurance_rate" in msgs


def test_yield_score_renormalizes_when_features_missing():
    df = _two_state_features().drop(columns=["effective_tax_rate", "insurance_rate"])
    out = yield_score(df).set_index("zcta5")
    # With only gross_yield (weight 0.5), the renormalized weight is 1.0,
    # so yield_score == sign * z_gross_yield exactly.
    for zcta in out.index:
        assert out.loc[zcta, "yield_score"] == pytest.approx(
            out.loc[zcta, "z_gross_yield"], abs=1e-9
        )


def test_yield_score_constant_state_yields_zero():
    """A state with all-equal yields should produce z=0 (MAD=0 guard)."""
    df = pd.DataFrame({
        "zcta5": ["00001", "00002", "00003"],
        "state": ["WY", "WY", "WY"],
        "gross_yield": [5.0, 5.0, 5.0],
    })
    out = yield_score(df)
    assert (out["yield_score"] == 0.0).all()


def test_yield_score_reads_custom_weights_file(tmp_path):
    df = _two_state_features()
    weights_path = tmp_path / "w.yaml"
    weights_path.write_text(yaml.safe_dump({
        "yield_score": {"gross_yield": 1.0}  # ignore tax/insurance entirely
    }))
    out = yield_score(df, weights_path=weights_path).set_index("zcta5")
    # Score == z_gross_yield exactly.
    for zcta in out.index:
        assert out.loc[zcta, "yield_score"] == pytest.approx(
            out.loc[zcta, "z_gross_yield"], abs=1e-9
        )


def test_yield_score_end_to_end_from_features():
    con = _con_with_zhvi_and_zori()
    feats = yield_features(con)
    out = yield_score(feats)
    # 5 zips, 5 distinct states → all z's are zero (single-zip-per-state).
    assert len(out) == 5
    assert (out["yield_score"] == 0.0).all()
