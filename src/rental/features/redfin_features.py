"""Redfin-derived market features (DOM, sale-to-list, inventory).

These features are *not* turned into a Redfin-specific subscore. Instead
they are exported for downstream consumption by two other agents:

- **SupplyScore** (Phase 3): rising DOM and rising inventory both signal
  supply pressure, so ``dom_yoy_delta`` (positive = softening demand) and
  ``inventory_yoy_change`` (positive = more supply) feed in there.
- **OperabilityScore** (Phase 4): high absolute DOM is an illiquidity
  proxy — a zip where homes sit on market for ~100 days is harder to
  exit, and that's a real operator cost beyond the cash-flow math.

Source table: ``raw_redfin_market`` (zip × month).

Design notes:
- All trailing windows pivot on the latest snapshot's most-recent month
  per zip. We never silently fill gaps; if the 3mo window has fewer than
  two months of data we return ``NaN`` for the average rather than a
  misleading single-month value.
- YoY features require the observation 12 months prior to the latest
  observation for that zip. If that month is missing (sparse data) we
  return ``NaN``. Downstream filters can drop NaN rows or impute as they
  see fit; we don't bake an imputation policy in here.
- Zip codes are 5-character strings throughout — never integers — so
  leading-zero New England / Puerto Rico zips round-trip correctly.
"""

from __future__ import annotations

import duckdb
import pandas as pd

_MIN_WINDOW_OBS = 2  # require at least 2 of the trailing 3 months for a 3mo avg


def _load_panel(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Pull the latest-snapshot Redfin panel as a tidy zip × month frame."""
    df = con.execute("""
        WITH latest_snapshot AS (
            SELECT MAX(snapshot_date) AS snap FROM raw_redfin_market
        )
        SELECT zcta5, period_begin, period_end,
               median_dom, median_sale_to_list, inventory,
               new_listings, median_sale_price, homes_sold
        FROM raw_redfin_market r, latest_snapshot ls
        WHERE r.snapshot_date = ls.snap
        ORDER BY zcta5, period_begin
    """).df()
    if df.empty:
        return df
    df["period_begin"] = pd.to_datetime(df["period_begin"])
    df["period_end"] = pd.to_datetime(df["period_end"])
    return df


def _trailing_mean(group: pd.DataFrame, col: str, months: int = 3) -> float:
    """Mean of ``col`` over the trailing ``months`` calendar months ending at the
    group's most recent observation. Returns NaN when fewer than
    ``_MIN_WINDOW_OBS`` observations fall in the window.
    """
    if group.empty:
        return float("nan")
    latest = group["period_begin"].max()
    window_start = latest - pd.DateOffset(months=months - 1)
    window = group[(group["period_begin"] >= window_start) & (group["period_begin"] <= latest)]
    values = window[col].dropna()
    if len(values) < _MIN_WINDOW_OBS:
        return float("nan")
    return float(values.mean())


def _yoy_value(group: pd.DataFrame, col: str) -> tuple[float, float]:
    """Return ``(latest, year_ago)`` for ``col`` aligned on ``period_begin``.

    ``year_ago`` is the value whose ``period_begin`` is exactly 12 months before
    the latest observation. NaN when not present — we never fall back to a
    different month, because the YoY semantics only hold for matching periods.
    """
    if group.empty:
        return (float("nan"), float("nan"))
    latest_row = group.loc[group["period_begin"].idxmax()]
    latest_period = latest_row["period_begin"]
    target = latest_period - pd.DateOffset(years=1)
    prior = group[group["period_begin"] == target]
    latest_val = float(latest_row[col]) if pd.notna(latest_row[col]) else float("nan")
    if prior.empty:
        return (latest_val, float("nan"))
    prior_val = prior.iloc[0][col]
    prior_val = float(prior_val) if pd.notna(prior_val) else float("nan")
    return (latest_val, prior_val)


def redfin_features(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Return one row per zip with the four Redfin-derived features.

    Columns:
        zcta5                       — 5-char zip
        latest_period_begin         — anchor month for the trailing windows
        dom_3mo_avg                 — trailing 3mo median DOM
        dom_yoy_delta               — latest DOM minus same-month-prior-year DOM
                                      (positive = market softening)
        sale_to_list_3mo_avg        — trailing 3mo sale-to-list ratio
                                      (<1.0 buyer's market)
        inventory_yoy_change        — (latest - year_ago) / year_ago, fraction
                                      (positive = more supply)

    NaN appears whenever the underlying window doesn't have enough data.
    """
    panel = _load_panel(con)
    if panel.empty:
        return pd.DataFrame(
            columns=[
                "zcta5",
                "latest_period_begin",
                "dom_3mo_avg",
                "dom_yoy_delta",
                "sale_to_list_3mo_avg",
                "inventory_yoy_change",
            ]
        )

    rows: list[dict[str, object]] = []
    for zcta5, group in panel.groupby("zcta5", sort=True):
        group = group.sort_values("period_begin")
        latest_period = group["period_begin"].max()

        dom_3mo = _trailing_mean(group, "median_dom")
        s2l_3mo = _trailing_mean(group, "median_sale_to_list")

        dom_latest, dom_prior = _yoy_value(group, "median_dom")
        dom_yoy = (
            dom_latest - dom_prior
            if pd.notna(dom_latest) and pd.notna(dom_prior)
            else float("nan")
        )

        inv_latest, inv_prior = _yoy_value(group, "inventory")
        if pd.notna(inv_latest) and pd.notna(inv_prior) and inv_prior != 0:
            inv_yoy = (inv_latest - inv_prior) / inv_prior
        else:
            inv_yoy = float("nan")

        rows.append(
            {
                "zcta5": zcta5,
                "latest_period_begin": latest_period.date(),
                "dom_3mo_avg": dom_3mo,
                "dom_yoy_delta": dom_yoy,
                "sale_to_list_3mo_avg": s2l_3mo,
                "inventory_yoy_change": inv_yoy,
            }
        )

    return pd.DataFrame(rows)
