.PHONY: init install refresh refresh-fixture score rank smoke test lint ci doctor status clean \
        gui-fe-install gui-fe-dev gui-fe-build gui-fe-test gui-fe-lint

PYTHON ?= python3
RANK_OUT ?= data/rankings/price_rank.csv
MARKET_RANK_OUT ?= data/rankings/market_score.csv
STALE_DAYS ?= 45

install:
	$(PYTHON) -m pip install -e ".[dev]"

init: install
	$(PYTHON) -m rental.cli init

# Real refresh: hits Zillow's CDN. Requires outbound network to
# files.zillowstatic.com — run locally, not in restricted environments.
refresh:
	$(PYTHON) -m rental.cli refresh --source zillow_zhvi

# Offline refresh: loads the bundled fixture into the warehouse so the
# smoke pipeline can be exercised end-to-end without network access.
refresh-fixture:
	$(PYTHON) -m rental.cli refresh --source zillow_zhvi --from-fixture tests/fixtures/zhvi_sample.csv

score:
	$(PYTHON) -m rental.cli score --output $(RANK_OUT)

# Composite MarketScore: reads zip_scores, applies hard filters,
# writes the ranked CSV. The CLI populates features + sub-scores
# from whatever raw data is present, so this works against a partial
# warehouse.
rank:
	$(PYTHON) -m rental.cli rank --output $(MARKET_RANK_OUT)

# Phase 0 smoke: init schema, load fixture, write a price-ranked CSV.
# Proves the end-to-end ETL → query → output path with no network.
smoke: init refresh-fixture score
	@echo "Smoke OK. Output at $(RANK_OUT)"

# Full pipeline smoke against bundled fixtures: ZHVI + ZORI + Redfin
# load, then populate features + sub-scores, composite + filters,
# ranked CSV. Output zips may be empty depending on filter defaults —
# what matters is the pipeline exits 0.
smoke-rank: init
	$(PYTHON) -m rental.cli refresh --source zillow_zhvi --from-fixture tests/fixtures/zhvi_sample.csv
	$(PYTHON) -m rental.cli refresh --source zillow_zori --from-fixture tests/fixtures/zori_sample.csv
	$(PYTHON) -m rental.cli refresh --source redfin_market --from-fixture tests/fixtures/redfin_market_sample.tsv
	$(PYTHON) -m rental.cli rank --output $(MARKET_RANK_OUT)
	@echo "Smoke rank OK. Output at $(MARKET_RANK_OUT)"

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check src tests

# What CI runs. Use this locally before pushing to catch drift early.
ci: test lint

# Source freshness summary (pretty table).
status:
	$(PYTHON) -m rental.cli status

# Health check: status + staleness gate. Warns (and exits non-zero) if
# any source is older than STALE_DAYS (default 45) or in error state.
doctor:
	$(PYTHON) -m rental.cli status --stale-days $(STALE_DAYS) --strict

clean:
	rm -rf data/warehouse.duckdb data/raw data/interim data/snapshots data/rankings data/manifest.json

# ===========================================================================
# GUI frontend targets (owned by fe-shell, agent #4 of the gooey build).
# Other agents (5/6/7) add to package.json and tests; these targets remain
# the canonical entry points for install/dev/build/test/lint.
# ===========================================================================

# Install frontend deps with a lockfile-respecting install. The frontend
# lives in ./frontend with its own package.json.
gui-fe-install:
	cd frontend && npm ci

# Start the Vite dev server on :5173 with the /api proxy to FastAPI :8000.
gui-fe-dev:
	cd frontend && npm run dev

# Production build → frontend/dist (served by `make gui-serve` when added
# by api-core).
gui-fe-build:
	cd frontend && npm run build

# Vitest run (unit tests + component tests). Playwright e2e runs under
# `make gui-test` (added by agent #8).
gui-fe-test:
	cd frontend && npm run test

# ESLint with --max-warnings=0 (configured inside package.json).
gui-fe-lint:
	cd frontend && npm run lint
