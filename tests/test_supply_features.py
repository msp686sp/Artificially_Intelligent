"""Supply feature tests.

We construct a small county-grain warehouse from the BPS + ACS fixtures
and a minimal ZCTA-county crosswalk, then assert the engineered
features match hand-computed expectations.
"""

from pathlib import Path

import duckdb
import pytest

from rental.db import init_schema
from rental.features import county_supply_features, zcta_supply_features
from rental.sources import ACSHousingStockSource, CensusBPSSource

BPS_FIXTURE = Path(__file__).parent / "fixtures" / "census_bps_sample.csv"
ACS_FIXTURE = Path(__file__).parent / "fixtures" / "acs_housing_stock_sample.json"


def _warehouse_with_supply():
    con = duckdb.connect(":memory:")
    init_schema(con)
    CensusBPSSource().load(con, BPS_FIXTURE)
    ACSHousingStockSource(year=2022).load(con, ACS_FIXTURE)
    return con


def _seed_xwalk(con, rows):
    """rows: list of (zcta5, county_fips, res_ratio) tuples."""
    con.executemany(
        "INSERT INTO geo_zcta_county_xwalk VALUES (?, ?, ?)", rows
    )


def test_county_features_one_row_per_county():
    con = _warehouse_with_supply()
    df = county_supply_features(con)
    assert len(df) == 5  # five counties in the fixture
    assert set(df["county_fips"]) == {"36061", "17031", "18097", "47157", "39035"}


def test_permits_per_1000_units_5yr_avg_matches_hand_calc():
    con = _warehouse_with_supply()
    df = county_supply_features(con).set_index("county_fips")

    # New York County: total permits over 5yr = 600+600+720+820+860 = 3600.
    # Avg/year = 720. ACS housing stock = 874321.
    # 720 / 874321 * 1000 ≈ 0.8235
    val = df.loc["36061", "permits_per_1000_units_5yr_avg"]
    assert val == pytest.approx(720 / 874321 * 1000, rel=1e-6)

    # Marion IN (18097): 1230+1310+1500+1650+1800 = 7490, avg 1498.
    # Housing stock 417890 → ≈ 3.584
    val = df.loc["18097", "permits_per_1000_units_5yr_avg"]
    assert val == pytest.approx(7490 / 5 / 417890 * 1000, rel=1e-6)


def test_multifamily_share_uses_latest_year():
    con = _warehouse_with_supply()
    df = county_supply_features(con).set_index("county_fips")

    # New York 2023: mf=720, total=860 → 0.8372
    assert df.loc["36061", "multifamily_share_permits"] == pytest.approx(720 / 860, rel=1e-6)
    # Marion IN 2023: mf=280, total=1800 → 0.1556 (SF-dominated, opposite end)
    assert df.loc["18097", "multifamily_share_permits"] == pytest.approx(280 / 1800, rel=1e-6)


def test_supply_pressure_index_is_finite_and_ranks_correctly():
    con = _warehouse_with_supply()
    df = county_supply_features(con).set_index("county_fips")

    # Pressure values are finite for all five counties (all have full data).
    pressures = df["supply_pressure_index"].astype(float)
    assert pressures.notna().all()
    # The z-composite is centered: sum should be near 0 across the small set.
    assert abs(pressures.sum()) < 1e-6 or abs(pressures.mean()) < 1e-6
    # Marion IN has by far the highest permits-per-1k and a moderate MF share,
    # while Cuyahoga (39035) is small and slow — pressure(Marion) > pressure(Cuyahoga).
    assert pressures["18097"] > pressures["39035"]


def test_zcta_apportionment_weights_by_res_ratio():
    con = _warehouse_with_supply()
    # Build a tiny crosswalk: one ZCTA spans two counties 60/40.
    _seed_xwalk(
        con,
        [
            ("10025", "36061", 1.0),  # pure NY county
            ("99001", "18097", 0.6),  # 60% Marion
            ("99001", "47157", 0.4),  # 40% Shelby
            ("44102", "39035", 1.0),  # pure Cuyahoga
        ],
    )

    zcta = zcta_supply_features(con).set_index("zcta5")
    assert bool(zcta.loc["10025", "is_interpolated"]) is True

    # Single-county ZCTAs equal the underlying county value.
    county_df = county_supply_features(con).set_index("county_fips")
    assert zcta.loc["10025", "multifamily_share_permits"] == pytest.approx(
        county_df.loc["36061", "multifamily_share_permits"], rel=1e-9
    )

    # Blended ZCTA matches 0.6 * Marion + 0.4 * Shelby for MF share.
    expected = (
        0.6 * county_df.loc["18097", "multifamily_share_permits"]
        + 0.4 * county_df.loc["47157", "multifamily_share_permits"]
    )
    assert zcta.loc["99001", "multifamily_share_permits"] == pytest.approx(
        expected, rel=1e-9
    )


def test_zcta_features_empty_when_no_xwalk():
    con = _warehouse_with_supply()
    # No crosswalk rows seeded: the result is an empty frame, not an error.
    out = zcta_supply_features(con)
    assert out.empty
    assert list(out.columns) == [
        "zcta5",
        "permits_per_1000_units_5yr_avg",
        "multifamily_share_permits",
        "supply_pressure_index",
        "is_interpolated",
    ]
