from rental.sources.base import RefreshResult, Source
from rental.sources.county_tax_rate import CountyTaxRateSource
from rental.sources.eviction_lab import EvictionLabSource
from rental.sources.fema_nri import FemaNriSource
from rental.sources.zillow_zhvi import ZillowZHVISource

REGISTRY: dict[str, type[Source]] = {
    "zillow_zhvi": ZillowZHVISource,
    "county_tax_rate": CountyTaxRateSource,
    "eviction_lab": EvictionLabSource,
    "fema_nri": FemaNriSource,
}

__all__ = [
    "REGISTRY",
    "CountyTaxRateSource",
    "EvictionLabSource",
    "FemaNriSource",
    "RefreshResult",
    "Source",
    "ZillowZHVISource",
]
