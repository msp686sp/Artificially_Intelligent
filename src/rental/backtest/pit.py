"""Point-in-time feature snapshot.

The single rule this module enforces: a feature value is only available
at ``as_of`` if its source had published it by then. Each source
publishes on a lag (see :class:`PublicationLag`); we apply that lag when
filtering the raw observations.

For ZHVI/ZORI we treat the latest published observation_date <= as_of as
the value of the feature at as_of. We never carry future data backwards.

The function is tolerant of missing optional tables: a warehouse that
only has ZHVI loaded (e.g., Phase 0) still returns a usable DataFrame
— ZORI-derived features simply come back as NaN and downstream consumers
decide whether to drop those rows.
"""

from __future__ import annotations

from datetime import date, timedelta

import duckdb
import pandas as pd

from rental.backtest.assumptions import Assumptions, PublicationLag


def _table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    rows = con.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = ?",
        [name],
    ).fetchall()
    return bool(rows)


def _latest_value_as_of(
    con: duckdb.DuckDBPyConnection,
    table: str,
    value_col: str,
    cutoff: date,
) -> pd.DataFrame:
    """Per-zip latest ``value_col`` whose observation_date <= cutoff.

    Returns columns ``zcta5`` and ``value_col``. Empty DataFrame when the
    table doesn't exist or contains no qualifying rows.
    """
    if not _table_exists(con, table):
        return pd.DataFrame(columns=["zcta5", value_col])
    return con.execute(
        f"""
        WITH ranked AS (
            SELECT zcta5,
                   observation_date,
                   {value_col} AS val,
                   ROW_NUMBER() OVER (
                       PARTITION BY zcta5
                       ORDER BY observation_date DESC
                   ) AS rn
            FROM {table}
            WHERE observation_date <= ?
              AND {value_col} IS NOT NULL
        )
        SELECT zcta5, val AS {value_col}
        FROM ranked
        WHERE rn = 1
        """,
        [cutoff],
    ).df()


def snapshot_features(
    con: duckdb.DuckDBPyConnection,
    as_of: date,
    assumptions: Assumptions | None = None,
    lags: PublicationLag | None = None,
) -> pd.DataFrame:
    """Return zip-level features as they were available on ``as_of``.

    Lookahead protection works per source: ``zhvi`` rows are filtered to
    ``observation_date <= as_of - lags.zhvi_days``; ``zori`` similarly.
    Optional tables (ZORI, tax rates, insurance) are merged on when
    present and filled with assumption defaults when absent.

    Columns returned (some may be NaN for thin zips):

        zcta5, zhvi, zori, gross_yield_monthly_pct,
        effective_tax_rate, insurance_rate, as_of
    """
    assumptions = assumptions or Assumptions()
    lags = lags or PublicationLag()

    zhvi_cutoff = as_of - timedelta(days=lags.zhvi_days)
    zori_cutoff = as_of - timedelta(days=lags.zori_days)

    zhvi = _latest_value_as_of(con, "raw_zillow_zhvi", "zhvi", zhvi_cutoff)
    zori = _latest_value_as_of(con, "raw_zillow_zori", "zori", zori_cutoff)

    if zhvi.empty:
        return pd.DataFrame(
            columns=[
                "zcta5", "zhvi", "zori", "gross_yield_monthly_pct",
                "effective_tax_rate", "insurance_rate", "as_of",
            ]
        )

    features = zhvi.merge(zori, on="zcta5", how="left")

    # Yield (monthly): ZORI is monthly rent, ZHVI is value — so
    # rent / value × 100 gives a monthly gross yield in percent.
    features["gross_yield_monthly_pct"] = (
        features["zori"] / features["zhvi"] * 100.0
    )

    # Tax/insurance: if dedicated feature tables exist (Phase 1 adds
    # them), join. Otherwise fall back to assumption defaults so the
    # backtest still runs against a thin warehouse.
    if _table_exists(con, "feature_tax_rate"):
        tax = con.execute(
            """
            SELECT zcta5, effective_tax_rate
            FROM feature_tax_rate
            WHERE as_of_date <= ?
            QUALIFY ROW_NUMBER() OVER (PARTITION BY zcta5 ORDER BY as_of_date DESC) = 1
            """,
            [as_of],
        ).df()
        features = features.merge(tax, on="zcta5", how="left")
    else:
        features["effective_tax_rate"] = pd.NA

    if _table_exists(con, "feature_insurance_rate"):
        ins = con.execute(
            """
            SELECT zcta5, insurance_rate
            FROM feature_insurance_rate
            WHERE as_of_date <= ?
            QUALIFY ROW_NUMBER() OVER (PARTITION BY zcta5 ORDER BY as_of_date DESC) = 1
            """,
            [as_of],
        ).df()
        features = features.merge(ins, on="zcta5", how="left")
    else:
        features["insurance_rate"] = pd.NA

    features["effective_tax_rate"] = features["effective_tax_rate"].fillna(
        assumptions.default_tax_rate
    )
    features["insurance_rate"] = features["insurance_rate"].fillna(
        assumptions.default_insurance_rate
    )

    features["as_of"] = as_of
    return features
