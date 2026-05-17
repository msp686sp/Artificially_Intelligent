from rental.sources.base import RefreshResult, Source

# Phase 1/3 (Redfin agent): zip-grain market tracker for DOM, sale-to-list,
# inventory. Consumed by SupplyScore and OperabilityScore features.
from rental.sources.redfin import RedfinMarketSource
from rental.sources.zillow_zhvi import ZillowZHVISource

REGISTRY: dict[str, type[Source]] = {
    "zillow_zhvi": ZillowZHVISource,
    "redfin_market": RedfinMarketSource,
}

__all__ = [
    "REGISTRY",
    "RefreshResult",
    "Source",
    "ZillowZHVISource",
    "RedfinMarketSource",
]
