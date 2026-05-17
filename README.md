# Rental Market Analysis

![CI](https://github.com/msp686sp/Artificially_Intelligent/actions/workflows/ci.yml/badge.svg)

Personal platform for finding profitable buy-and-hold SFR rental markets at
the US zip-code level — with a FastAPI + React/Tailwind GUI on top. See
[`docs/gooey-plan.md`](docs/gooey-plan.md) for the GUI build plan.

## GUI quick start

```bash
make gui-install       # FastAPI extras
make gui-fe-install    # frontend deps
make gui-api-dev       # FastAPI on :8000  (in one terminal)
make gui-fe-dev        # Vite on :5173    (in another)
# → open http://localhost:5173
```

Visual baselines for every route at desktop + mobile live under
[`frontend/tests/e2e/__screenshots__/visual-capture.spec.ts/`](frontend/tests/e2e/__screenshots__/visual-capture.spec.ts/).
Regenerate with `make gui-screens`.
the US zip-code level, using free public data.

- **Discovery:** [`docs/rental-market-analysis-discovery.md`](docs/rental-market-analysis-discovery.md)
- **Build plan:** [`docs/plan.md`](docs/plan.md)

## Status

Phases 0–6 complete:

- **0** project skeleton, DuckDB warehouse, Source ABC, Zillow ZHVI reference
- **1** Zillow ZORI + Census geo spine; YieldScore
- **2** BLS QCEW + IRS migration + ACS demographics; DemandScore
- **3** Census Building Permits Survey + ACS housing stock; SupplyScore
- **4** ACS property tax + NAIC state insurance + Eviction Lab + FEMA NRI; OperabilityScore + RiskScore
- **5** MarketScore composite + hard-filter engine + `rental rank` CLI
- **6** point-in-time feature snapshots, realized 5yr levered return, walk-forward weight tuner, HTML backtest report

Plus Redfin Data Center (DOM, sale-to-list, inventory) and CI
infrastructure (GitHub Actions, refresh manifest, `rental status` /
`make doctor`).

Next: Phase 7 (event alerts + weekly email digest), Phase 8 (Streamlit
dashboard), then v2's property-level underwriter.

## Quick start

```bash
make install         # install package + dev deps
make init            # create the DuckDB warehouse
make smoke           # Phase 0 fixture pipeline (init → refresh ZHVI → score CSV)
make smoke-rank      # full pipeline (refreshes ZHVI + ZORI + Redfin → MarketScore CSV)
make test            # 202 tests
```

For real data refreshes (requires outbound network to the source hosts):

```bash
rental refresh --source zillow_zhvi
rental refresh --source zillow_zori
rental refresh --source census_geo            # geo spine (Census ZCTA + CBSA)
rental refresh --source bls_qcew              # jobs + wages
rental refresh --source irs_migration         # county-to-county migration
rental refresh --source acs_demographics
rental refresh --source acs_housing_stock
rental refresh --source census_bps            # building permits
rental refresh --source redfin_market
rental refresh --source county_tax_rate
rental refresh --source eviction_lab
rental refresh --source fema_nri
rental rank                                   # composite MarketScore + hard filters
```

To reach the CBSA delineation xlsx, install the `xlsx` extra:
`pip install -e ".[xlsx]"`.

## Backtest

```bash
rental backtest run   --output data/backtest/backtest_report.html
rental backtest tune  --output data/backtest/tune_report.html
```

`run` produces a snapshot-by-snapshot Spearman + quintile-bucket
report with bootstrap CIs and a READY / NOT READY banner.
`tune` performs walk-forward weight tuning (default train 2013–17,
validate 2018–22) and reports the best weights.

## Layout

```
src/rental/
  cli.py              # rental init/refresh/score/rank/status/backtest/digest
  config.py           # paths + YAML loaders + env-var overrides
  manifest.py         # refresh-freshness JSON tracker
  db/                 # DuckDB connection + schema
  sources/            # 12 data sources (Source ABC pattern)
  features/           # engineered features per dimension
  scoring/            # sub-scores + composite + populate driver
  backtest/           # PIT snapshots, returns, walk-forward tuner, report
  refdata/            # bundled reference data (state insurance averages)
config/
  filters.yaml        # configurable hard filters
  weights.yaml        # composite + sub-score weights
  watchlist.yaml      # zips to monitor + alert rules (Phase 7)
  state_insurance_rates.csv
data/                 # gitignored; rebuildable from sources
tests/                # 202 pytest cases + bundled fixtures
docs/                 # discovery + build plan
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
