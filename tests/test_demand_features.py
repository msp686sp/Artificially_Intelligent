"""Tests for the Phase 2 demand-side feature builders.

Each test loads the bundled source fixtures into an in-memory warehouse
and seeds a small ZCTA↔county crosswalk so the county-grain metrics can
be aggregated to the ZCTA level for the joined feature frame.
"""

from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

from rental.db import init_schema
from rental.features.demand_features import (
    county_to_zcta,
    demand_features,
    hh_income_growth_5yr,
    net_migration_per_1000,
    wage_weighted_job_cagr_5yr,
)
from rental.sources import (
    ACSDemographicsSource,
    BLSQcewSource,
    IRSMigrationSource,
)

FIX = Path(__file__).parent / "fixtures"


def _seed_warehouse() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    init_schema(con)
    BLSQcewSource().load(con, FIX / "qcew_sample.csv")
    IRSMigrationSource().load(con, FIX / "irs_migration_sample.csv")
    ACSDemographicsSource().load(con, FIX / "acs_sample.json")

    # Seed a tiny ZCTA↔county xwalk: one zip per county at res_ratio 1.0.
    xwalk = pd.DataFrame(
        [
            ("60614", "17031", 1.0),  # Cook County → Chicago zip
            ("10025", "36061", 1.0),  # New York County → Manhattan zip
            ("46220", "18097", 1.0),  # Marion County → Indianapolis zip
            ("38104", "47157", 1.0),  # Shelby County → Memphis zip
            ("44102", "39035", 1.0),  # Cuyahoga County → Cleveland zip
        ],
        columns=["zcta5", "county_fips", "res_ratio"],
    )
    con.register("_xwalk_seed", xwalk)
    con.execute("INSERT INTO geo_zcta_county_xwalk SELECT * FROM _xwalk_seed")
    con.unregister("_xwalk_seed")

    # Also seed the zcta→state lookup so the score tests have a state column.
    geo = pd.DataFrame(
        [
            ("60614", "IL", 50000, 1.0),
            ("10025", "NY", 70000, 0.8),
            ("46220", "IN", 30000, 6.0),
            ("38104", "TN", 22000, 4.0),
            ("44102", "OH", 18000, 5.0),
        ],
        columns=["zcta5", "state", "population", "aland_sqmi"],
    )
    con.register("_geo_seed", geo)
    con.execute("INSERT INTO geo_zcta SELECT * FROM _geo_seed")
    con.unregister("_geo_seed")
    return con


def test_wage_weighted_job_cagr_emits_one_row_per_county():
    con = _seed_warehouse()
    df = wage_weighted_job_cagr_5yr(con, end_year=2023, horizon_years=5)
    assert set(df["county_fips"]) == {"17031", "36061", "18097", "47157", "39035"}
    assert (df["end_year"] == 2023).all()
    assert (df["start_year"] == 2018).all()
    # Cook County's wage-weighted total grew sector-on-sector (per the fixture)
    # so its CAGR must be positive.
    cook = df.loc[df["county_fips"] == "17031", "wage_weighted_job_cagr_5yr"].iloc[0]
    assert cook > 0


def test_net_migration_per_1000_uses_total_migration_row_as_denominator():
    con = _seed_warehouse()
    df = net_migration_per_1000(con, year=2020)
    # Cook County: inflow_returns(non-self) = 1850+420+1120 = 3390; outflow_returns
    # (non-self) = 2200+1050+1450 = 4700. pop_exemptions(self-row inflow) = 71200.
    # net per 1000 = (3390 - 4700) * 1000 / 71200 ≈ -18.4
    cook = df.loc[df["county_fips"] == "17031", "net_migration_per_1000"].iloc[0]
    assert cook == pytest_approx(-18.40, abs=0.05)
    # Marion County is a net winner per the fixture.
    marion = df.loc[df["county_fips"] == "18097", "net_migration_per_1000"].iloc[0]
    assert marion > 0


def test_hh_income_growth_5yr_returns_empty_when_no_two_years():
    """Our ACS fixture only has 1 year (2022); 5yr CAGR needs 2 endpoints."""
    con = _seed_warehouse()
    df = hh_income_growth_5yr(con, end_year=2022, horizon_years=5)
    assert df.empty


def test_hh_income_growth_5yr_computes_cagr_when_both_years_present():
    con = _seed_warehouse()
    # Seed a second ACS year (2017) for the same zips so 5yr CAGR is defined.
    earlier = pd.DataFrame(
        [
            ("10025", 2017, 50000, 95000, 38.0, date.today()),
            ("60614", 2017, 55000, 86000, 33.0, date.today()),
            ("46220", 2017, 27000, 50000, 36.0, date.today()),
        ],
        columns=[
            "zcta5",
            "year",
            "population",
            "median_household_income",
            "median_age",
            "snapshot_date",
        ],
    )
    con.register("_acs_back", earlier)
    con.execute("INSERT INTO raw_acs_demographics SELECT * FROM _acs_back")
    con.unregister("_acs_back")

    df = hh_income_growth_5yr(con, end_year=2022, horizon_years=5)
    assert set(df["zcta5"]) == {"10025", "60614", "46220"}
    # 10025: 118500 / 95000 → CAGR ≈ (1.2474)**(1/5)-1 ≈ 4.51%
    row = df[df["zcta5"] == "10025"].iloc[0]
    assert row["hh_income_growth_5yr"] == pytest_approx(0.0451, abs=0.001)


def test_county_to_zcta_uses_res_ratio_weights():
    con = _seed_warehouse()
    # Re-seed a multi-county zip to exercise the weighted average.
    con.execute("DELETE FROM geo_zcta_county_xwalk WHERE zcta5 = 'TEST1'")
    con.execute(
        "INSERT INTO geo_zcta_county_xwalk VALUES "
        "('TEST1', '17031', 0.75), "
        "('TEST1', '18097', 0.25)"
    )
    metric = pd.DataFrame(
        [("17031", 10.0), ("18097", 2.0)],
        columns=["county_fips", "value"],
    )
    out = county_to_zcta(con, metric, "value")
    # Weighted: (10*0.75 + 2*0.25) / (0.75+0.25) = 8.0
    test_zip = out.loc[out["zcta5"] == "TEST1", "value"].iloc[0]
    assert test_zip == pytest_approx(8.0, abs=1e-9)


def test_demand_features_returns_one_row_per_known_zcta():
    con = _seed_warehouse()
    df = demand_features(con)
    # Two features available (jobs + migration) for 5 zips; income is absent.
    assert set(df["zcta5"]) == {"60614", "10025", "46220", "38104", "44102"}
    assert "wage_weighted_job_cagr_5yr" in df.columns
    assert "net_migration_per_1000" in df.columns
    assert "hh_income_growth_5yr" in df.columns
    # income column is present even when there's no data, just NaN.
    assert df["hh_income_growth_5yr"].isna().all()


# pytest-style "approx" without pulling the import to the top (keeps the
# module loadable in environments where only the stdlib is on the path).
def pytest_approx(expected, abs=0.0, rel=0.0):
    from pytest import approx as _approx

    return _approx(expected, abs=abs, rel=rel)
