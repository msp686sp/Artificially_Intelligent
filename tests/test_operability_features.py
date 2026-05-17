"""Tests for zip-level operability features.

Seed the geo + raw tables manually (no live ETL) so the joins are tested
deterministically.
"""

from pathlib import Path

import duckdb

from rental.db import init_schema
from rental.features.operability_features import (
    effective_tax_rate,
    eviction_filing_rate,
    insurance_rate_estimate,
    operability_feature_frame,
)
from rental.refdata import load_state_insurance
from rental.sources import CountyTaxRateSource, EvictionLabSource

TAX_FIXTURE = Path(__file__).parent / "fixtures" / "county_tax_sample.json"
EVIC_FIXTURE = Path(__file__).parent / "fixtures" / "eviction_lab_sample.csv"


def _con_with_geo() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    init_schema(con)
    # Seed geo_zcta: each zip lives in one state.
    con.execute(
        """
        INSERT INTO geo_zcta (zcta5, state, population, aland_sqmi) VALUES
          ('10025', 'NY', 95000, 1.0),
          ('60614', 'IL', 60000, 1.8),
          ('46220', 'IN', 30000, 9.0),
          ('38104', 'TN', 25000, 4.5),
          ('44102', 'OH', 28000, 5.2),
          ('77002', 'TX', 18000, 2.3)
        """
    )
    # Seed crosswalk: simple one-zip / one-county mapping with res_ratio=1.0,
    # plus a split zip (44102 mostly Cuyahoga, partial in a neighbor).
    con.execute(
        """
        INSERT INTO geo_zcta_county_xwalk (zcta5, county_fips, res_ratio) VALUES
          ('10025', '36061', 1.0),
          ('60614', '17031', 1.0),
          ('46220', '18097', 1.0),
          ('38104', '47157', 1.0),
          ('44102', '39035', 0.8),
          ('77002', '48201', 1.0)
        """
    )
    return con


def test_effective_tax_rate_weighted_to_zip():
    con = _con_with_geo()
    CountyTaxRateSource().load(con, TAX_FIXTURE)
    df = effective_tax_rate(con)
    rates = dict(zip(df["zcta5"], df["effective_tax_rate"], strict=False))
    # 10025 -> 36061: 8200/720000
    assert abs(rates["10025"] - 8200 / 720000) < 1e-9
    # 44102 -> 39035: 1900/92000  (res_ratio cancels in single-county case).
    assert abs(rates["44102"] - 1900 / 92000) < 1e-9


def test_eviction_filing_rate_uses_latest_year_per_county():
    con = _con_with_geo()
    EvictionLabSource().load(con, EVIC_FIXTURE)
    df = eviction_filing_rate(con)
    rates = dict(zip(df["zcta5"], df["eviction_filing_rate"], strict=False))
    # 60614 -> 17031 has both 2016 (4.9) and 2018 (5.2). Latest is 2018.
    assert abs(rates["60614"] - 5.2) < 1e-9
    assert abs(rates["38104"] - 7.4) < 1e-9


def test_insurance_rate_estimate_state_join():
    con = _con_with_geo()
    load_state_insurance(con)
    df = insurance_rate_estimate(con)
    by_zip = dict(zip(df["zcta5"], df["insurance_rate_estimate"], strict=False))
    # NY 2021 = 1395; OH 2021 = 1009; TX 2021 = 2253 (per bundled CSV).
    assert by_zip["10025"] == 1395
    assert by_zip["44102"] == 1009
    assert by_zip["77002"] == 2253


def test_operability_feature_frame_outer_joins_three_components():
    con = _con_with_geo()
    CountyTaxRateSource().load(con, TAX_FIXTURE)
    EvictionLabSource().load(con, EVIC_FIXTURE)
    load_state_insurance(con)
    df = operability_feature_frame(con)
    expected_cols = {"effective_tax_rate", "insurance_rate_estimate", "eviction_filing_rate"}
    assert expected_cols <= set(df.columns)
    assert len(df) >= 5


def test_empty_xwalk_yields_empty_county_features():
    con = duckdb.connect(":memory:")
    init_schema(con)
    CountyTaxRateSource().load(con, TAX_FIXTURE)
    # No geo seeded -> joins return zero rows.
    assert effective_tax_rate(con).empty
    assert eviction_filing_rate(con).empty
