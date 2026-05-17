"""Tests for the realized 5-year levered total return calculation."""

from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from rental.backtest.assumptions import Assumptions
from rental.backtest.returns import (
    _annual_mortgage_payment,
    realized_levered_return_5yr,
)
from rental.db import init_schema

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    init_schema(c)
    c.execute("""
        CREATE TABLE IF NOT EXISTS raw_zillow_zori (
            zcta5 VARCHAR,
            observation_date DATE,
            zori DOUBLE,
            snapshot_date DATE,
            PRIMARY KEY (zcta5, observation_date, snapshot_date)
        )
    """)
    return c


def _load(con):
    z = pd.read_csv(FIXTURE_DIR / "synthetic_zhvi_long.csv", dtype={"zcta5": str})
    z["observation_date"] = pd.to_datetime(z["observation_date"]).dt.date
    z["snapshot_date"] = date(2025, 1, 1)
    z["region_id"] = "0"
    z["state"] = "CA"
    z["metro"] = "Synthetic"
    z["county_name"] = "Test"
    con.register("_z", z)
    con.execute("""
        INSERT INTO raw_zillow_zhvi
        SELECT region_id, zcta5, state, metro, county_name,
               observation_date, zhvi, snapshot_date FROM _z
    """)
    con.unregister("_z")

    r = pd.read_csv(FIXTURE_DIR / "synthetic_zori_long.csv", dtype={"zcta5": str})
    r["observation_date"] = pd.to_datetime(r["observation_date"]).dt.date
    r["snapshot_date"] = date(2025, 1, 1)
    # Phase 1 made raw_zillow_zori 8-column (mirrors ZHVI); fill the join fields.
    r["region_id"] = "0"
    r["state"] = "CA"
    r["metro"] = "Synthetic"
    r["county_name"] = "Test"
    con.register("_r", r)
    con.execute("""
        INSERT INTO raw_zillow_zori
        SELECT region_id, zcta5, state, metro, county_name,
               observation_date, zori, snapshot_date FROM _r
    """)
    con.unregister("_r")


def test_mortgage_payment_matches_known_value():
    # $300k @ 6% / 30yr → ~$1798.65/mo → $21583.81/yr
    annual = _annual_mortgage_payment(300_000, 0.06, 30)
    assert annual == pytest.approx(21583.79, rel=1e-4)


def test_levered_total_return_for_known_zip(con):
    _load(con)
    # 90001: initial ZHVI ~150k (Jan 2013), 6% appreciation → ~200.8k at Jan 2018.
    # ZORI grows 4% on $1300 start.
    a = Assumptions(
        down_payment_pct=0.25,
        mortgage_rate_apr=0.05,
        mortgage_term_years=30,
        closing_costs_pct=0.03,
        property_management_pct=0.10,
        maintenance_pct=0.08,
        capex_reserve_pct=0.05,
        vacancy_pct=0.07,
        default_tax_rate=0.012,
        default_insurance_rate=0.005,
        horizon_years=5,
    )
    r = realized_levered_return_5yr(con, "90001", date(2013, 1, 31), a)
    assert r is not None
    # cash_invested = 0.28 × 150000 (approximately; uses date(2013,1,31) value)
    # Trajectory is exponential, so ZHVI(Jan 2013) ≈ 150000 × 1.06^5 = 200730 final.
    assert r.initial_price == pytest.approx(150000 * 1.06 ** 5, rel=1e-3)
    assert r.final_price == pytest.approx(150000 * 1.06 ** 10, rel=1e-3)

    # Hand-computed reference: build the same pro forma step-by-step.
    initial = 150000 * 1.06 ** 5
    cash_invested = (a.down_payment_pct + a.closing_costs_pct) * initial
    loan = (1 - a.down_payment_pct) * initial
    annual_pi = _annual_mortgage_payment(loan, a.mortgage_rate_apr, a.mortgage_term_years)
    opex_frac = a.property_management_pct + a.maintenance_pct + a.capex_reserve_pct
    coc_sum = 0.0
    zori0 = 1300 * 1.04 ** 5  # ZORI at snapshot date
    zhvi0 = initial
    for y in range(1, 6):
        zhvi_y = zhvi0 * 1.06 ** y
        zori_y = zori0 * 1.04 ** y
        gross = 12 * zori_y
        effective = gross * (1 - a.vacancy_pct)
        opex = gross * opex_frac
        tax = zhvi_y * a.default_tax_rate
        ins = zhvi_y * a.default_insurance_rate
        cf = effective - opex - tax - ins - annual_pi
        coc_sum += cf / cash_invested
    final = zhvi0 * 1.06 ** 5
    appreciation = (final - initial) / cash_invested
    expected_total = coc_sum + appreciation

    assert r.coc_5yr_sum == pytest.approx(coc_sum, rel=1e-3)
    assert r.appreciation_return == pytest.approx(appreciation, rel=1e-3)
    assert r.levered_total_return_5yr == pytest.approx(expected_total, rel=1e-3)


def test_levered_return_ranks_high_yield_above_low(con):
    _load(con)
    # 90001 (top-yield) must outrank 90005 (worst) over the same horizon.
    a = Assumptions(mortgage_rate_apr=0.05)
    top = realized_levered_return_5yr(con, "90001", date(2013, 1, 31), a)
    worst = realized_levered_return_5yr(con, "90005", date(2013, 1, 31), a)
    assert top.levered_total_return_5yr > worst.levered_total_return_5yr


def test_returns_none_when_horizon_data_missing(con):
    _load(con)
    # Snapshot in 2024 has no t+5 data in our fixture.
    a = Assumptions()
    r = realized_levered_return_5yr(con, "90001", date(2024, 6, 30), a)
    assert r is None


def test_handles_missing_zori_table(con):
    """When ZORI is absent the fallback rent proxy keeps the calc going."""
    # Drop ZORI; load ZHVI only.
    _load(con)
    con.execute("DROP TABLE raw_zillow_zori")
    a = Assumptions(mortgage_rate_apr=0.05)
    r = realized_levered_return_5yr(con, "90001", date(2013, 1, 31), a)
    assert r is not None
    assert r.levered_total_return_5yr != 0.0
