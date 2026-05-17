from rental.sources.acs_demographics import ACSDemographicsSource
from rental.sources.acs_housing_stock import ACSHousingStockSource
from rental.sources.base import RefreshResult, Source
from rental.sources.bls_qcew import BLSQcewSource
from rental.sources.census_bps import CensusBPSSource
from rental.sources.census_geo import CensusGeoSource
from rental.sources.county_tax_rate import CountyTaxRateSource
from rental.sources.eviction_lab import EvictionLabSource
from rental.sources.fema_nri import FemaNriSource
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
    "census_bps": CensusBPSSource,
    "acs_housing_stock": ACSHousingStockSource,
    "county_tax_rate": CountyTaxRateSource,
    "eviction_lab": EvictionLabSource,
    "fema_nri": FemaNriSource,
}

__all__ = [
    "REGISTRY",
    "ACSDemographicsSource",
    "ACSHousingStockSource",
    "BLSQcewSource",
    "CensusBPSSource",
    "CensusGeoSource",
    "CountyTaxRateSource",
    "EvictionLabSource",
    "FemaNriSource",
    "IRSMigrationSource",
    "RedfinMarketSource",
    "RefreshResult",
    "Source",
    "ZillowZHVISource",
    "ZillowZORISource",
]
