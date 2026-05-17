from rental.sources.acs_demographics import ACSDemographicsSource
from rental.sources.base import RefreshResult, Source
from rental.sources.bls_qcew import BLSQcewSource
from rental.sources.census_geo import CensusGeoSource
from rental.sources.irs_migration import IRSMigrationSource
from rental.sources.redfin import RedfinMarketSource
from rental.sources.zillow_zhvi import ZillowZHVISource
from rental.sources.zori import ZillowZORISource

REGISTRY: dict[str, type[Source]] = {
    "zillow_zhvi": ZillowZHVISource,
    "zillow_zori": ZillowZORISource,
    "census_geo": CensusGeoSource,
    "redfin_market": RedfinMarketSource,
    "bls_qcew": BLSQcewSource,
    "irs_migration": IRSMigrationSource,
    "acs_demographics": ACSDemographicsSource,
}

__all__ = [
    "REGISTRY",
    "ACSDemographicsSource",
    "BLSQcewSource",
    "CensusGeoSource",
    "IRSMigrationSource",
    "RedfinMarketSource",
    "RefreshResult",
    "Source",
    "ZillowZHVISource",
    "ZillowZORISource",
]
