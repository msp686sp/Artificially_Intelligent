import duckdb

from rental.db import init_schema
from rental.refdata import load_state_insurance, read_state_insurance_csv


def _con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    init_schema(con)
    return con


def test_state_insurance_csv_has_50_states_plus_dc():
    df = read_state_insurance_csv()
    assert len(df) >= 51
    assert {"AL", "CA", "FL", "NY", "TX", "DC"} <= set(df["state"].unique())


def test_state_insurance_premiums_are_positive_floats():
    df = read_state_insurance_csv()
    assert (df["avg_annual_premium"] > 0).all()
    assert df["avg_annual_premium"].dtype == float


def test_state_insurance_load_into_warehouse():
    con = _con()
    n = load_state_insurance(con)
    assert n >= 51
    loaded = con.execute("SELECT count(*) FROM ref_state_insurance").fetchone()[0]
    assert loaded == n


def test_state_insurance_load_is_idempotent():
    con = _con()
    load_state_insurance(con)
    load_state_insurance(con)  # re-load
    loaded = con.execute("SELECT count(*) FROM ref_state_insurance").fetchone()[0]
    # PK (state, year, policy_form) means duplicates are upserted, not appended.
    df = read_state_insurance_csv()
    assert loaded == len(df)
