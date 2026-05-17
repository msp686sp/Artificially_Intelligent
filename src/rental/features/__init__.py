"""Feature engineering.

Phase 0 shipped latest-ZHVI-per-zip; later phases add yield, demand, supply,
operability, and risk features. Modules organized by dimension so each
sub-score agent can extend independently.
"""

from rental.features.demand_features import (
    demand_features,
    hh_income_growth_5yr,
    net_migration_per_1000,
    wage_weighted_job_cagr_5yr,
)
from rental.features.redfin_features import redfin_features
from rental.features.supply_features import (
    county_supply_features,
    zcta_supply_features,
)
from rental.features.yield_features import yield_features
from rental.features.zhvi import latest_zhvi_per_zip

__all__ = [
    "county_supply_features",
    "demand_features",
    "hh_income_growth_5yr",
    "latest_zhvi_per_zip",
    "net_migration_per_1000",
    "redfin_features",
    "wage_weighted_job_cagr_5yr",
    "yield_features",
    "zcta_supply_features",
]
