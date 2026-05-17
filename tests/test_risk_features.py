from pathlib import Path

import duckdb

from rental.db import init_schema
from rental.features.risk_features import climate_risk_features, climate_risk_score
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


def test_climate_risk_features_wide_columns():
    con = _con_with_geo()
    FemaNriSource().load(con, FIXTURE)
    df = climate_risk_features(con)
    expected_cols = {"climate_risk_score", "flood_risk", "wildfire_risk", "hurricane_risk"}
    assert expected_cols <= set(df.columns)
    assert len(df) == 7


def test_climate_risk_score_miami_is_high_cleveland_is_low():
    con = _con_with_geo()
    FemaNriSource().load(con, FIXTURE)
    df = climate_risk_features(con)
    scores = dict(zip(df["zcta5"], df["climate_risk_score"], strict=False))
    # 33101 -> 12086 Miami-Dade composite ~98.7; 44102 -> 39035 Cuyahoga ~28.6.
    assert scores["33101"] > scores["44102"]
    assert scores["33101"] > 80
    assert scores["44102"] < 40


def test_hurricane_risk_zero_in_landlocked_zip():
    con = _con_with_geo()
    FemaNriSource().load(con, FIXTURE)
    df = climate_risk_features(con)
    hurr = dict(zip(df["zcta5"], df["hurricane_risk"], strict=False))
    # 60614 -> 17031 Cook County hurricane score is tiny in the fixture.
    assert hurr["60614"] < 5
    assert hurr["33101"] > 80   # Miami-Dade obviously high


def test_climate_risk_score_helper_returns_subset():
    con = _con_with_geo()
    FemaNriSource().load(con, FIXTURE)
    df = climate_risk_score(con)
    assert list(df.columns) == ["zcta5", "climate_risk_score"]


def test_empty_xwalk_yields_empty_dataframe():
    con = duckdb.connect(":memory:")
    init_schema(con)
    FemaNriSource().load(con, FIXTURE)
    assert climate_risk_features(con).empty
