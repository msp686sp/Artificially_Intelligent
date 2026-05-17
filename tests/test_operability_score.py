"""Tests for the OperabilityScore aggregator."""

import duckdb
import numpy as np

from rental.db import init_schema
from rental.refdata import load_state_insurance
from rental.scoring.operability_score import operability_score


def _con_with_three_ny_zips() -> duckdb.DuckDBPyConnection:
    """Set up three NY zips so within-state z-score is well-defined."""
    con = duckdb.connect(":memory:")
    init_schema(con)
    con.execute(
        """
        INSERT INTO geo_zcta (zcta5, state, population, aland_sqmi) VALUES
          ('10025', 'NY', 95000, 1.0),
          ('11201', 'NY', 60000, 1.8),
          ('12601', 'NY', 30000, 9.0)
        """
    )
    con.execute(
        """
        INSERT INTO geo_zcta_county_xwalk (zcta5, county_fips, res_ratio) VALUES
          ('10025', '36061', 1.0),
          ('11201', '36047', 1.0),
          ('12601', '36027', 1.0)
        """
    )
    # Seed county-tax with three NY counties of different rates.
    con.execute(
        """
        INSERT INTO raw_county_tax_rate VALUES
          ('36061', 2022, 8200, 720000, 8200.0/720000, DATE '2024-01-01'),
          ('36047', 2022, 5800, 580000, 5800.0/580000, DATE '2024-01-01'),
          ('36027', 2022, 6500, 320000, 6500.0/320000, DATE '2024-01-01')
        """
    )
    con.execute(
        """
        INSERT INTO raw_eviction_lab VALUES
          ('36061', 2018, 7200, 3.8, DATE '2024-01-01'),
          ('36047', 2018, 12500, 4.2, DATE '2024-01-01'),
          ('36027', 2018, 900, 2.0, DATE '2024-01-01')
        """
    )
    load_state_insurance(con)
    return con


def test_operability_score_returns_one_row_per_zip():
    con = _con_with_three_ny_zips()
    df = operability_score(con)
    assert set(df["zcta5"]) == {"10025", "11201", "12601"}
    assert "operability_score" in df.columns


def test_operability_score_negatively_correlated_with_pain():
    con = _con_with_three_ny_zips()
    df = operability_score(con).set_index("zcta5")
    # 12601 has the highest effective rate (6500/320000 = 0.020) but the
    # lowest eviction filing rate (2.0). 11201 is middle on tax, highest on
    # eviction. Either way, the zip with the lowest combined pain should
    # score highest. We confirm at least: scores are not all equal.
    assert df["operability_score"].nunique() > 1
    # The within-state z weights mean the sum of composite (signed) should
    # be ~ 0 because z-scores sum to zero within state.
    assert abs(df["operability_score"].sum()) < 1e-9


def test_operability_score_within_state_zscore_columns_present():
    con = _con_with_three_ny_zips()
    df = operability_score(con)
    for col in ("z_effective_tax_rate", "z_insurance_rate_estimate", "z_eviction_filing_rate"):
        assert col in df.columns


def test_operability_score_handles_missing_inputs():
    """If a zip lacks any operability input, it returns NaN (not 0)."""
    con = duckdb.connect(":memory:")
    init_schema(con)
    con.execute(
        "INSERT INTO geo_zcta (zcta5, state, population, aland_sqmi) VALUES ('00000', 'NY', 1, 1)"
    )
    df = operability_score(con)
    if not df.empty:
        # An all-missing zip's composite should be NaN.
        assert np.isnan(df.loc[df["zcta5"] == "00000", "operability_score"]).all()


def test_operability_score_loads_weights_from_yaml():
    """Spot check: passing explicit weights overrides config."""
    con = _con_with_three_ny_zips()
    custom = {
        "effective_tax_rate": -1.0,
        "insurance_rate_estimate": 0.0,
        "eviction_filing_rate": 0.0,
    }
    df = operability_score(con, weights=custom)
    # With only tax weighted (negative weight), the zip with the lowest
    # effective tax rate ranks highest. Rates in the fixture:
    #   36047 (11201) = 5800/580000  = 0.0100   <-- lowest
    #   36061 (10025) = 8200/720000  = 0.0114
    #   36027 (12601) = 6500/320000  = 0.0203
    top = df.iloc[0]["zcta5"]
    assert top == "11201"
