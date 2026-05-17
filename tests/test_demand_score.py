"""Tests for the DemandScore subscore (Phase 2)."""

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from rental.db import init_schema
from rental.scoring.demand_score import (
    _robust_z,
    demand_score,
    within_state_zscores,
)
from rental.sources import (
    ACSDemographicsSource,
    BLSQcewSource,
    IRSMigrationSource,
)

FIX = Path(__file__).parent / "fixtures"


def _seeded_con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    init_schema(con)
    BLSQcewSource().load(con, FIX / "qcew_sample.csv")
    IRSMigrationSource().load(con, FIX / "irs_migration_sample.csv")
    ACSDemographicsSource().load(con, FIX / "acs_sample.json")

    xwalk = pd.DataFrame(
        [
            ("60614", "17031", 1.0),
            ("10025", "36061", 1.0),
            ("46220", "18097", 1.0),
            ("38104", "47157", 1.0),
            ("44102", "39035", 1.0),
        ],
        columns=["zcta5", "county_fips", "res_ratio"],
    )
    con.register("_xwalk_seed", xwalk)
    con.execute("INSERT INTO geo_zcta_county_xwalk SELECT * FROM _xwalk_seed")
    con.unregister("_xwalk_seed")

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


def test_robust_z_centers_on_median_and_scales_by_mad():
    z = _robust_z(pd.Series([1.0, 2.0, 3.0, 4.0, 5.0]))
    # Median = 3, MAD = 1, so z(3) = 0 and z(5) = (5-3) / (1.4826*1) ≈ 1.349.
    assert z.iloc[2] == pytest.approx(0.0, abs=1e-9)
    assert z.iloc[4] == pytest.approx(1.3489, abs=1e-3)


def test_robust_z_handles_constant_column():
    """Constant-within-state columns must not return NaN."""
    z = _robust_z(pd.Series([5.0, 5.0, 5.0]))
    # MAD is 0 → every non-null value treated as exactly at the median (z=0).
    assert (z == 0.0).all()


def test_robust_z_preserves_nans():
    z = _robust_z(pd.Series([1.0, np.nan, 3.0, 5.0]))
    assert pd.isna(z.iloc[1])
    assert not pd.isna(z.iloc[0])


def test_within_state_zscores_groups_by_state():
    df = pd.DataFrame(
        [
            ("z1", "IL", 0.05),
            ("z2", "IL", 0.10),
            ("z3", "IL", 0.15),
            ("z4", "NY", 0.30),
            ("z5", "NY", 0.31),
            ("z6", "NY", 0.32),
        ],
        columns=["zcta5", "state", "feat"],
    )
    out = within_state_zscores(df, ["feat"])
    # Each state's median is its middle value → z=0 for those rows.
    assert out.loc[out["zcta5"] == "z2", "feat_z"].iloc[0] == pytest.approx(0.0)
    assert out.loc[out["zcta5"] == "z5", "feat_z"].iloc[0] == pytest.approx(0.0)


def test_demand_score_emits_one_row_per_zcta_with_score_column():
    con = _seeded_con()
    df = demand_score(con)
    assert set(df["zcta5"]) == {"60614", "10025", "46220", "38104", "44102"}
    assert "demand_score" in df.columns
    # Each zip lives in a single-zip state in our fixture, so within-state
    # z-scores collapse to 0 → demand_score should be 0 for every zip with
    # at least one non-null feature.
    assert (df["demand_score"].dropna() == 0.0).all()


def test_demand_score_uses_weights_yaml_keys():
    """Passing explicit weights overrides the YAML and is applied verbatim."""
    con = _seeded_con()
    # Same shape as config: rescaled across available features.
    df = demand_score(
        con,
        weights={
            "wage_weighted_job_cagr": 1.0,
            "net_migration_per_1000": 0.0,
            "hh_income_growth": 0.0,
        },
    )
    # With only jobs weighted, the score equals the jobs z-score.
    merged = df[["zcta5", "demand_score", "wage_weighted_job_cagr_5yr_z"]]
    nonnull = merged.dropna()
    assert np.allclose(nonnull["demand_score"], nonnull["wage_weighted_job_cagr_5yr_z"])


def test_demand_score_returns_empty_frame_with_columns_when_no_data():
    con = duckdb.connect(":memory:")
    init_schema(con)
    df = demand_score(con)
    assert df.empty
    assert "demand_score" in df.columns


def test_weights_yaml_block_has_three_keys_summing_to_one():
    """Acceptance: the demand_score block in config/weights.yaml is fully fleshed out."""
    from rental.config import load_yaml

    cfg = load_yaml("weights.yaml")
    block = cfg["demand_score"]
    assert set(block) == {
        "wage_weighted_job_cagr",
        "net_migration_per_1000",
        "hh_income_growth",
    }
    assert sum(block.values()) == pytest.approx(1.0, abs=1e-9)
