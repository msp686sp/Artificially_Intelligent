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
from rental.features.operability_features import (
    effective_tax_rate,
    eviction_filing_rate,
    insurance_rate_estimate,
    operability_feature_frame,
)
from rental.features.redfin_features import redfin_features
from rental.features.risk_features import (
    climate_risk_features,
    climate_risk_score,
)
from rental.features.supply_features import (
    county_supply_features,
    zcta_supply_features,
)
from rental.features.yield_features import yield_features
from rental.features.zhvi import latest_zhvi_per_zip

__all__ = [
    "climate_risk_features",
    "climate_risk_score",
    "county_supply_features",
    "demand_features",
    "effective_tax_rate",
    "eviction_filing_rate",
    "hh_income_growth_5yr",
    "insurance_rate_estimate",
    "latest_zhvi_per_zip",
    "net_migration_per_1000",
    "operability_feature_frame",
    "redfin_features",
    "wage_weighted_job_cagr_5yr",
    "yield_features",
    "zcta_supply_features",
]
