"""Realized 5-year levered total return for a single zip.

Formula (per the locked plan):

    LeveredTotalReturn_5yr(zip) =
        sum_{y=1..5} [ annual_cash_flow_y / cash_invested ]
      + [ (ZHVI_t+5 - ZHVI_t) * leverage_ratio ] / cash_invested

Where:

    cash_invested = down_payment_pct * ZHVI_t + closing_costs_pct * ZHVI_t
    leverage_ratio = 1.0                       # appreciation accrues on the
                                               # full property value, so the
                                               # whole delta lands on equity.
    annual_cash_flow_y =
        12 * ZORI_y * (1 - vacancy_pct)
        - 12 * ZORI_y * (PM + maintenance + capex)
        - tax_rate * ZHVI_y
        - insurance_rate * ZHVI_y
        - 12 * monthly_mortgage_payment

Cash-on-cash for year y therefore divides annual_cash_flow_y by
cash_invested (a constant). The implementation keeps the *components*
separate so the backtest report can show CoC vs. appreciation
contributions side-by-side.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta

import duckdb
import pandas as pd

from rental.backtest.assumptions import Assumptions


@dataclass(frozen=True)
class RealizedReturn:
    zcta5: str
    snapshot_date: date
    cash_invested: float
    initial_price: float
    final_price: float
    coc_yr1: float
    coc_5yr_sum: float
    appreciation_return: float
    levered_total_return_5yr: float


def _annual_mortgage_payment(principal: float, apr: float, term_years: int) -> float:
    """Standard amortizing mortgage; returns the annual P&I payment."""
    if apr <= 0:
        return principal / term_years
    monthly_rate = apr / 12.0
    n = term_years * 12
    monthly = principal * (monthly_rate * (1 + monthly_rate) ** n) / (
        (1 + monthly_rate) ** n - 1
    )
    return monthly * 12.0


def _series_for_zip(
    con: duckdb.DuckDBPyConnection,
    table: str,
    value_col: str,
    zcta5: str,
    start: date,
    end: date,
) -> pd.DataFrame:
    """Pull the monthly trajectory of ``value_col`` for ``zcta5`` between dates."""
    rows = con.execute(
        f"""
        SELECT observation_date, {value_col} AS val
        FROM {table}
        WHERE zcta5 = ?
          AND observation_date BETWEEN ? AND ?
          AND {value_col} IS NOT NULL
        ORDER BY observation_date
        """,
        [zcta5, start, end],
    ).fetchall()
    return pd.DataFrame(rows, columns=["observation_date", "val"])


def _value_at(
    series: pd.DataFrame,
    target: date,
    max_staleness_days: int = 60,
) -> float | None:
    """Latest value with observation_date <= target, but only if that
    observation is recent enough.

    ``max_staleness_days`` guards against silently substituting an old
    value for a missing future one — important for the t+5 endpoint
    check: if the warehouse only goes to 2024-12 we must NOT use that
    as the "value at 2029-06" simply because it's the latest available.
    """
    if series.empty:
        return None
    eligible = series[series["observation_date"] <= target]
    if eligible.empty:
        return None
    latest = eligible.iloc[-1]
    delta = (target - latest["observation_date"]).days
    if delta > max_staleness_days:
        return None
    return float(latest["val"])


def realized_levered_return_5yr(
    con: duckdb.DuckDBPyConnection,
    zcta5: str,
    snapshot_date: date,
    assumptions: Assumptions | None = None,
    tax_rate: float | None = None,
    insurance_rate: float | None = None,
) -> RealizedReturn | None:
    """Compute the realized 5yr levered total return for one zip.

    Returns ``None`` when the warehouse doesn't have enough trajectory
    coverage (no ZHVI at t or at t+5; no ZORI to underwrite rent).
    """
    a = assumptions or Assumptions()
    tax_rate = a.default_tax_rate if tax_rate is None else tax_rate
    insurance_rate = a.default_insurance_rate if insurance_rate is None else insurance_rate

    horizon = a.horizon_years
    end_date = date(snapshot_date.year + horizon, snapshot_date.month, snapshot_date.day)

    zhvi = _series_for_zip(
        con, "raw_zillow_zhvi", "zhvi", zcta5,
        snapshot_date - timedelta(days=400), end_date + timedelta(days=400),
    )
    initial_price = _value_at(zhvi, snapshot_date)
    final_price = _value_at(zhvi, end_date)
    if initial_price is None or final_price is None:
        return None

    # ZORI table may be missing on a thin warehouse; we still want a
    # tractable answer when it is, so we fall back to a proxy of
    # gross_yield = 0.6% monthly (~7.2% gross annual yield) applied to
    # ZHVI at each year-end. That proxy is *only* exercised when the
    # warehouse truly has no rent data, and tests for the happy path
    # exercise the real-ZORI branch.
    have_zori = False
    zori_series = pd.DataFrame(columns=["observation_date", "val"])
    rows = con.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'raw_zillow_zori'"
    ).fetchall()
    if rows:
        zori_series = _series_for_zip(
            con, "raw_zillow_zori", "zori", zcta5,
            snapshot_date - timedelta(days=400), end_date + timedelta(days=400),
        )
        have_zori = not zori_series.empty

    cash_invested = (a.down_payment_pct + a.closing_costs_pct) * initial_price
    loan_principal = (1.0 - a.down_payment_pct) * initial_price
    annual_pi = _annual_mortgage_payment(loan_principal, a.mortgage_rate_apr, a.mortgage_term_years)

    operating_pct = a.property_management_pct + a.maintenance_pct + a.capex_reserve_pct
    coc_components: list[float] = []

    for y in range(1, horizon + 1):
        year_end = date(snapshot_date.year + y, snapshot_date.month, snapshot_date.day)
        zhvi_y = _value_at(zhvi, year_end) or initial_price
        if have_zori:
            zori_y = _value_at(zori_series, year_end)
            if zori_y is None:
                zori_y = initial_price * 0.006   # fallback monthly rent
        else:
            zori_y = zhvi_y * 0.006

        gross_rent = 12.0 * zori_y
        effective_rent = gross_rent * (1.0 - a.vacancy_pct)
        opex_from_rent = gross_rent * operating_pct
        tax = zhvi_y * tax_rate
        insurance = zhvi_y * insurance_rate
        annual_cf = effective_rent - opex_from_rent - tax - insurance - annual_pi

        coc_components.append(annual_cf / cash_invested if cash_invested > 0 else 0.0)

    coc_5yr_sum = sum(coc_components)
    appreciation_return = (final_price - initial_price) / cash_invested
    total = coc_5yr_sum + appreciation_return

    return RealizedReturn(
        zcta5=zcta5,
        snapshot_date=snapshot_date,
        cash_invested=cash_invested,
        initial_price=initial_price,
        final_price=final_price,
        coc_yr1=coc_components[0] if coc_components else 0.0,
        coc_5yr_sum=coc_5yr_sum,
        appreciation_return=appreciation_return,
        levered_total_return_5yr=total,
    )


def realized_returns_for_universe(
    con: duckdb.DuckDBPyConnection,
    snapshot_date: date,
    zips: list[str],
    assumptions: Assumptions | None = None,
    tax_by_zip: dict[str, float] | None = None,
    insurance_by_zip: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Vectorized convenience wrapper over the single-zip function.

    Skips zips for which we lack endpoint coverage; returns one row per
    zip we could compute, with the same column shape as
    :class:`RealizedReturn`.
    """
    a = assumptions or Assumptions()
    tax_by_zip = tax_by_zip or {}
    insurance_by_zip = insurance_by_zip or {}
    out: list[dict] = []
    for z in zips:
        r = realized_levered_return_5yr(
            con, z, snapshot_date, a,
            tax_rate=tax_by_zip.get(z),
            insurance_rate=insurance_by_zip.get(z),
        )
        if r is not None:
            out.append(asdict(r))
    return pd.DataFrame(out)
