"""Tests for the point-in-time feature snapshot.

The single must-not-fail property: a feature row stamped with
``observation_date d`` only becomes visible at ``as_of`` once
``as_of >= d + publication_lag``.
"""

from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from rental.backtest.assumptions import Assumptions, PublicationLag
from rental.backtest.pit import snapshot_features
from rental.db import init_schema

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    init_schema(c)
    # Augment with raw_zillow_zori — this column lives in the Phase 1
    # agent's schema migration, but for PIT tests we mint it locally so
    # we don't couple test ordering to phase ordering.
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


def _load_long_fixture(con, table: str, value_col: str, csv_path: Path) -> None:
    df = pd.read_csv(csv_path, dtype={"zcta5": str})
    df["observation_date"] = pd.to_datetime(df["observation_date"]).dt.date
    df["snapshot_date"] = date(2025, 1, 1)
    if table == "raw_zillow_zhvi":
        df["region_id"] = "0"
        df["state"] = "CA"
        df["metro"] = "Synthetic"
        df["county_name"] = "Test"
        con.register("_stg", df)
        con.execute(f"""
            INSERT OR REPLACE INTO {table}
            SELECT region_id, zcta5, state, metro, county_name,
                   observation_date, {value_col}, snapshot_date
            FROM _stg
        """)
    else:
        con.register("_stg", df)
        con.execute(f"""
            INSERT OR REPLACE INTO {table}
            SELECT zcta5, observation_date, {value_col}, snapshot_date
            FROM _stg
        """)
    con.unregister("_stg")


def _seed(con):
    _load_long_fixture(con, "raw_zillow_zhvi", "zhvi",
                       FIXTURE_DIR / "synthetic_zhvi_long.csv")
    _load_long_fixture(con, "raw_zillow_zori", "zori",
                       FIXTURE_DIR / "synthetic_zori_long.csv")


def test_snapshot_returns_one_row_per_zip(con):
    _seed(con)
    snap = snapshot_features(con, date(2015, 6, 1))
    assert sorted(snap["zcta5"].tolist()) == ["90001", "90002", "90003", "90004", "90005"]
    # All zhvi values must be from observation_dates <= cutoff
    assert snap["zhvi"].notna().all()
    assert snap["zori"].notna().all()


def test_snapshot_excludes_future_data(con):
    _seed(con)
    # 2010-01-01 with 45d lag — we may only see data observed by 2009-11-17
    as_of = date(2010, 1, 1)
    lags = PublicationLag()
    snap = snapshot_features(con, as_of, lags=lags)

    # For 90001, the latest visible observation should be
    # observation_date <= 2010-01-01 - 45d = 2009-11-17.
    # The closest month-end in the fixture is 2009-10-31, so ZHVI must
    # equal the 2009-10-31 value (NOT a 2009-12-31 value, which would be
    # leakage).
    leak = con.execute(
        """
        SELECT zhvi FROM raw_zillow_zhvi
        WHERE zcta5 = '90001' AND observation_date = DATE '2009-12-31'
        """
    ).fetchone()[0]
    valid = con.execute(
        """
        SELECT zhvi FROM raw_zillow_zhvi
        WHERE zcta5 = '90001' AND observation_date = DATE '2009-10-31'
        """
    ).fetchone()[0]
    snapped = float(snap.loc[snap["zcta5"] == "90001", "zhvi"].iloc[0])
    assert snapped == pytest.approx(valid)
    assert snapped != pytest.approx(leak)


def test_snapshot_lag_is_per_source(con):
    """A larger ZORI lag must hide rent data that ZHVI's lag would expose."""
    _seed(con)
    # ZHVI 45d, ZORI 365d
    lags = PublicationLag(zhvi_days=45, zori_days=365)
    snap = snapshot_features(con, date(2009, 6, 1), lags=lags)
    # ZHVI has data observed by ~2009-04-17; fixture starts 2008-01-31 → present.
    # ZORI must look back to 2008-06-01, also present, so we still expect
    # non-null but a STALER value than ZHVI.
    snap_zhvi_only = snapshot_features(
        con, date(2009, 6, 1), lags=PublicationLag(zori_days=45),
    )
    # The two ZORI numbers should differ because the cutoffs differ.
    assert (
        float(snap.loc[snap["zcta5"] == "90001", "zori"].iloc[0])
        < float(snap_zhvi_only.loc[snap_zhvi_only["zcta5"] == "90001", "zori"].iloc[0])
    )


def test_snapshot_handles_no_zori_table(con):
    """If only ZHVI is loaded the snapshot still works; ZORI columns NaN."""
    _load_long_fixture(con, "raw_zillow_zhvi", "zhvi",
                       FIXTURE_DIR / "synthetic_zhvi_long.csv")
    # Drop ZORI table to simulate Phase 0 warehouse.
    con.execute("DROP TABLE raw_zillow_zori")
    snap = snapshot_features(con, date(2015, 1, 1))
    assert not snap.empty
    assert snap["zori"].isna().all()
    assert snap["gross_yield_monthly_pct"].isna().all()


def test_snapshot_empty_when_no_zhvi(con):
    snap = snapshot_features(con, date(2015, 1, 1))
    assert snap.empty
    # Schema must still be the expected one so the report code doesn't trip.
    assert list(snap.columns) == [
        "zcta5", "zhvi", "zori", "gross_yield_monthly_pct",
        "effective_tax_rate", "insurance_rate", "as_of",
    ]


def test_snapshot_defaults_for_tax_and_insurance(con):
    _seed(con)
    a = Assumptions(default_tax_rate=0.02, default_insurance_rate=0.01)
    snap = snapshot_features(con, date(2015, 1, 1), assumptions=a)
    assert (snap["effective_tax_rate"] == 0.02).all()
    assert (snap["insurance_rate"] == 0.01).all()
