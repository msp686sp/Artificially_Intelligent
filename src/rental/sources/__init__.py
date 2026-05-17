# Phase 2 (Demand half) — labor, migration, demographics.
from rental.sources.acs_demographics import ACSDemographicsSource
from rental.sources.base import RefreshResult, Source
from rental.sources.bls_qcew import BLSQcewSource
from rental.sources.irs_migration import IRSMigrationSource
from rental.sources.zillow_zhvi import ZillowZHVISource

REGISTRY: dict[str, type[Source]] = {
    "zillow_zhvi": ZillowZHVISource,
    "bls_qcew": BLSQcewSource,
    "irs_migration": IRSMigrationSource,
    "acs_demographics": ACSDemographicsSource,
}

__all__ = [
    "REGISTRY",
    "RefreshResult",
    "Source",
    "ZillowZHVISource",
    "BLSQcewSource",
    "IRSMigrationSource",
    "ACSDemographicsSource",
]
