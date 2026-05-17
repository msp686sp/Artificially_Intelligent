from rental.sources.base import RefreshResult, Source
from rental.sources.census_geo import CensusGeoSource
from rental.sources.zillow_zhvi import ZillowZHVISource
from rental.sources.zori import ZillowZORISource

REGISTRY: dict[str, type[Source]] = {
    "zillow_zhvi": ZillowZHVISource,
    "zillow_zori": ZillowZORISource,
    "census_geo": CensusGeoSource,
}

__all__ = [
    "REGISTRY",
    "CensusGeoSource",
    "RefreshResult",
    "Source",
    "ZillowZHVISource",
    "ZillowZORISource",
]
