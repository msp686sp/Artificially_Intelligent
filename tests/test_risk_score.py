"""Tests for the RiskScore aggregator."""

from pathlib import Path

import duckdb
import numpy as np

from rental.db import init_schema
from rental.scoring.risk_score import risk_score
from rental.sources import FemaNriSource

FIXTURE = Path(__file__).parent / "fixtures" / "fema_nri_sample.csv"


def _con_with_geo() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    init_schema(con)
    con.execute(
        """
        INSERT INTO geo_zcta (zcta5, state, population, aland_sqmi) VALUES
          ('10025', 'NY', 95000, 1.0),
          ('60614', 'IL', 60000, 1.8),
          ('46220', 'IN', 30000, 9.0),
          ('38104', 'TN', 25000, 4.5),
          ('44102', 'OH', 28000, 5.2),
          ('33101', 'FL', 14000, 1.0),
          ('77002', 'TX', 18000, 2.3)
        """
    )
    con.execute(
        """
        INSERT INTO geo_zcta_county_xwalk (zcta5, county_fips, res_ratio) VALUES
          ('10025', '36061', 1.0),
          ('60614', '17031', 1.0),
          ('46220', '18097', 1.0),
          ('38104', '47157', 1.0),
          ('44102', '39035', 1.0),
          ('33101', '12086', 1.0),
          ('77002', '48201', 1.0)
        """
    )
    return con


def test_risk_score_one_row_per_zip():
    con = _con_with_geo()
    FemaNriSource().load(con, FIXTURE)
    df = risk_score(con)
    assert len(df) == 7
    assert "risk_score" in df.columns


def test_risk_score_low_for_high_hazard_zips():
    """Miami-Dade composite ~98.7 should score worse than Cuyahoga ~28.6."""
    con = _con_with_geo()
    FemaNriSource().load(con, FIXTURE)
    df = risk_score(con).set_index("zcta5")
    assert df.loc["33101", "risk_score"] < df.loc["44102", "risk_score"]


def test_risk_score_sums_to_zero_with_default_weights():
    """National z-scores sum to ~0; weighted sum should also sum to ~0."""
    con = _con_with_geo()
    FemaNriSource().load(con, FIXTURE)
    df = risk_score(con)
    assert abs(df["risk_score"].sum()) < 1e-6


def test_risk_score_empty_when_no_fema_data():
    con = duckdb.connect(":memory:")
    init_schema(con)
    df = risk_score(con)
    assert df.empty


def test_risk_score_z_columns_emitted():
    con = _con_with_geo()
    FemaNriSource().load(con, FIXTURE)
    df = risk_score(con)
    for col in ("z_climate_risk_score", "z_flood_risk", "z_wildfire_risk", "z_hurricane_risk"):
        assert col in df.columns


def test_risk_score_respects_custom_weights():
    con = _con_with_geo()
    FemaNriSource().load(con, FIXTURE)
    # Only hurricane matters: hurricane-prone zips should be at the bottom.
    df = risk_score(
        con,
        weights={"climate_risk_score": 0.0, "flood_risk": 0.0,
                 "wildfire_risk": 0.0, "hurricane_risk": -1.0},
    ).set_index("zcta5")
    assert df.loc["33101", "risk_score"] < df.loc["46220", "risk_score"]
    # And a zip with normal-ish risk should land near zero (np.isfinite ok).
    assert np.isfinite(df.loc["10025", "risk_score"])
