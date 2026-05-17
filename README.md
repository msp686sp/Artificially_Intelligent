# Rental Market Analysis

![CI](https://github.com/msp686sp/Artificially_Intelligent/actions/workflows/ci.yml/badge.svg)

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

## Development

Continuous integration runs `pytest` + `ruff` on every push and on PRs to
`main` (see `.github/workflows/ci.yml`). To replicate locally:

```bash
make ci              # pytest + ruff (same as the GitHub Actions job)
```

Operational helpers:

```bash
rental status        # pretty table of last-refresh date + row counts per source
make doctor          # same as `rental status --strict`, warns if a source > 45d stale
```

Refresh freshness is tracked in `data/manifest.json`, updated automatically
inside `Source.refresh()`. Override the warehouse / manifest location with
the `RENTAL_WAREHOUSE_PATH` and `RENTAL_MANIFEST_PATH` environment
variables (used by the CLI integration tests to keep runs hermetic).
