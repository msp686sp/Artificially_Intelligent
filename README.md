# Rental Market Analysis

Personal platform for finding profitable buy-and-hold SFR rental markets at
the US zip-code level, using free public data.

- **Discovery:** [`docs/rental-market-analysis-discovery.md`](docs/rental-market-analysis-discovery.md)
- **Build plan:** [`docs/plan.md`](docs/plan.md)

## Status

Phase 0 complete: project skeleton, DuckDB warehouse + schema, CLI scaffold,
Zillow ZHVI source as the reference ETL shape, and an end-to-end smoke
pipeline that runs against a bundled fixture without network access.

Next: Phase 1 (full Yield half — adds ZORI, county tax rates, insurance estimates).

## Quick start

```bash
make install         # install package + dev deps
make init            # create the DuckDB warehouse
make smoke           # end-to-end (uses bundled fixture, no network)
make test            # run pytest
```

For a real refresh against Zillow's CDN (requires outbound network to
`files.zillowstatic.com`):

```bash
make refresh         # fetch + load ZHVI from the public CSV
make score           # write data/rankings/price_rank.csv
make rank            # composite MarketScore + hard filters → data/rankings/market_score.csv
```

## Layout

```
src/rental/
  cli.py              # `rental {init,refresh,score,digest}`
  config.py           # paths + YAML loaders
  db/                 # DuckDB connection + schema
  sources/            # one module per data source (Source ABC)
  features/           # engineered metrics per dimension
config/
  filters.yaml        # configurable hard filters (defaults documented in plan)
  weights.yaml        # composite scoring weights
  watchlist.yaml      # zips to monitor + alert rules (Phase 7)
data/                 # gitignored; rebuildable from sources
tests/                # pytest + bundled fixtures
docs/                 # discovery + plan
```
