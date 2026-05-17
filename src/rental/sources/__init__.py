from rental.sources.base import RefreshResult, Source
from rental.sources.zillow_zhvi import ZillowZHVISource

REGISTRY: dict[str, type[Source]] = {
    "zillow_zhvi": ZillowZHVISource,
}

__all__ = ["REGISTRY", "RefreshResult", "Source", "ZillowZHVISource"]
