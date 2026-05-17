"""Standard underwriting assumptions and per-source publication lags.

Two small dataclasses kept separate from the rest of the module so they
can be imported by code that doesn't want to pull in pandas/DuckDB.

`Assumptions` holds the constants that every zip's pro forma uses.
They are intentionally identical across zips so that ranking is not
contaminated by per-zip operator-skill assumptions — the platform
ranks markets, not deals.

`PublicationLag` holds the per-source publication lags used by the
point-in-time feature snapshot to avoid lookahead bias. The values come
from the discovery notes (see ``docs/plan.md``): ZHVI/ZORI publish on a
roughly 45-day cadence, BLS QCEW is ~180 days behind, ACS lags 9-12
months, and the Census Building Permits Survey ships ~30 days after the
month it covers.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Assumptions:
    """Standard pro-forma assumptions held constant across zips."""

    # Capital structure
    down_payment_pct: float = 0.25
    mortgage_rate_apr: float = 0.07            # prevailing 30yr; snapshot can override
    mortgage_term_years: int = 30
    closing_costs_pct: float = 0.03            # of purchase price

    # Operating expenses as fractions of gross rent
    property_management_pct: float = 0.10
    maintenance_pct: float = 0.08
    capex_reserve_pct: float = 0.05
    vacancy_pct: float = 0.07

    # Fallback opex rates when the zip's features don't carry them.
    # Both are fractions of property value per year.
    default_tax_rate: float = 0.011            # ~1.1% effective US avg
    default_insurance_rate: float = 0.0055     # ~$1,200/$220k (varies by state)

    # Horizon
    horizon_years: int = 5


@dataclass(frozen=True)
class PublicationLag:
    """How many days each source publishes behind the period it covers.

    Used by the point-in-time snapshot: a row with ``observation_date d``
    is only considered available at ``as_of`` when ``as_of >= d + lag``.
    """

    zhvi_days: int = 45
    zori_days: int = 45
    bls_qcew_days: int = 180
    acs_days: int = 365                          # 9-12 months; use 12
    bps_permits_days: int = 30
    redfin_days: int = 14

    # Convenience mapping used by snapshot_features. Kept as a method
    # rather than a class attribute so dataclass frozen=True doesn't
    # complain about mutable defaults.
    def as_mapping(self) -> dict[str, int]:
        return {
            "zhvi": self.zhvi_days,
            "zori": self.zori_days,
            "qcew": self.bls_qcew_days,
            "acs": self.acs_days,
            "bps": self.bps_permits_days,
            "redfin": self.redfin_days,
        }


@dataclass(frozen=True)
class WeightGrid:
    """A small named grid of MarketScore weight values to search.

    Five sub-scores × five grid values per dimension is 3,125 points —
    cheap to enumerate for the personal-tool scale of this project.
    """

    yield_: list[float] = field(default_factory=lambda: [0.15, 0.20, 0.25, 0.30, 0.35])
    demand: list[float] = field(default_factory=lambda: [0.20, 0.25, 0.30, 0.35, 0.40])
    supply: list[float] = field(default_factory=lambda: [0.10, 0.15, 0.20, 0.25, 0.30])
    operability: list[float] = field(default_factory=lambda: [0.10, 0.15, 0.20, 0.25, 0.30])
    risk: list[float] = field(default_factory=lambda: [-0.10, -0.075, -0.05, -0.025, 0.0])
