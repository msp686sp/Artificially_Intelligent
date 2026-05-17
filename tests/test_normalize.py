import numpy as np
import pandas as pd

from rental.scoring.normalize import zscore_within_state


def test_median_mad_zscore_basic():
    # Within a state, the median value should map to 0.
    df = pd.DataFrame({
        "state": ["TX"] * 5,
        "v": [1.0, 2.0, 3.0, 4.0, 5.0],
    })
    z = zscore_within_state(df, "v")
    assert z.loc[df["v"] == 3.0].iloc[0] == 0.0
    # Symmetric around the median.
    assert np.isclose(z.iloc[0], -z.iloc[4])
    assert np.isclose(z.iloc[1], -z.iloc[3])


def test_zscore_independent_per_state():
    # Each state is normalized within itself: TX's 100 should map to the
    # same z as CA's 1.0 because they're at the same median position.
    df = pd.DataFrame({
        "state": ["TX", "TX", "TX", "CA", "CA", "CA"],
        "v":     [50.0, 100.0, 150.0,  0.5, 1.0,  1.5],
    })
    z = zscore_within_state(df, "v")
    # Both states have 3 symmetric points, so the medians map to 0.0.
    assert np.isclose(z.iloc[1], 0.0)
    assert np.isclose(z.iloc[4], 0.0)
    # Top of state maps to same positive value in both states.
    assert np.isclose(z.iloc[2], z.iloc[5])


def test_nan_inputs_propagate_as_nan_outputs():
    df = pd.DataFrame({
        "state": ["IL", "IL", "IL", "IL"],
        "v":     [1.0, 2.0, np.nan, 3.0],
    })
    z = zscore_within_state(df, "v")
    assert np.isnan(z.iloc[2])
    # The remaining three values should have a finite z-score.
    finite = z.dropna()
    assert len(finite) == 3


def test_single_zip_state_returns_zero_not_nan():
    df = pd.DataFrame({
        "state": ["IL", "IL", "WY"],
        "v":     [1.0, 5.0, 7.0],
    })
    z = zscore_within_state(df, "v")
    # Wyoming has a single zip — MAD is 0 by definition, no spread.
    # Convention: finite value gets z=0, not NaN.
    assert z.iloc[2] == 0.0


def test_all_identical_values_in_state():
    df = pd.DataFrame({
        "state": ["AK"] * 3,
        "v":     [42.0, 42.0, 42.0],
    })
    z = zscore_within_state(df, "v")
    assert (z == 0.0).all()


def test_empty_frame_returns_empty_series():
    df = pd.DataFrame({"state": [], "v": []})
    z = zscore_within_state(df, "v")
    assert z.empty


def test_missing_column_raises():
    df = pd.DataFrame({"state": ["NY"], "v": [1.0]})
    try:
        zscore_within_state(df, "missing")
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError for missing value_col")


def test_output_index_aligns_with_input():
    df = pd.DataFrame({
        "state": ["TX", "TX", "TX"],
        "v": [1.0, 2.0, 3.0],
    }, index=[10, 20, 30])
    z = zscore_within_state(df, "v")
    assert list(z.index) == [10, 20, 30]
