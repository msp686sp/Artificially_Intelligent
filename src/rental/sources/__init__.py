from rental.sources.acs_housing_stock import ACSHousingStockSource
from rental.sources.base import RefreshResult, Source
from rental.sources.census_bps import CensusBPSSource
from rental.sources.zillow_zhvi import ZillowZHVISource

REGISTRY: dict[str, type[Source]] = {
    "zillow_zhvi": ZillowZHVISource,
    # Phase 3 — supply-side.
    "census_bps": CensusBPSSource,
    "acs_housing_stock": ACSHousingStockSource,
}

__all__ = [
    "ACSHousingStockSource",
    "CensusBPSSource",
    "REGISTRY",
    "RefreshResult",
    "Source",
    "ZillowZHVISource",
]
