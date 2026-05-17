.PHONY: init install refresh refresh-fixture score rank smoke smoke-rank test lint ci doctor status clean \
        gui-install gui-api-dev \
        gui-fe-install gui-fe-dev gui-fe-build gui-fe-test gui-fe-lint \
        gui-test gui-screens gui-screens-ci

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

# ============================================================
# GUI (the "gooey") — see docs/gooey-plan.md.
# Backend targets owned by api-core (agent 1).
# Frontend targets owned by fe-shell (agent 4).
# E2E/visual targets owned by playwright (agent 8).
# ============================================================

# --- Backend ---

# Install the rental package with the GUI extras (FastAPI + uvicorn + ...).
gui-install:
	$(PYTHON) -m pip install -e ".[gui,dev]"

# Run the FastAPI app with hot-reload on :8000. CORS is open to the Vite
# dev server (:5173). OpenAPI docs at http://localhost:8000/docs.
gui-api-dev:
	$(PYTHON) -m uvicorn api.main:app --reload --port 8000

# --- Frontend ---

# Install frontend deps with a lockfile-respecting install. The frontend
# lives in ./frontend with its own package.json.
gui-fe-install:
	cd frontend && npm ci

# Start the Vite dev server on :5173 with the /api proxy to FastAPI :8000.
gui-fe-dev:
	cd frontend && npm run dev

# Production build → frontend/dist (served by `make gui-serve` when added).
gui-fe-build:
	cd frontend && npm run build

# Vitest run (unit + component). Playwright e2e runs under `make gui-test`.
gui-fe-test:
	cd frontend && npm run test

# ESLint with --max-warnings=0 (configured inside package.json).
gui-fe-lint:
	cd frontend && npm run lint
# --- Playwright (e2e + visual regression) ---

# Full GUI smoke: API tests + frontend unit tests + Playwright E2E.
gui-test:
	$(PYTHON) -m pytest tests/api
	cd frontend && npm run test
	cd frontend && npx playwright test

# Regenerate Playwright visual baselines under
# frontend/tests/e2e/__screenshots__/. Run this locally after the frontend
# is integrated, then commit the resulting PNGs.
gui-screens:
	cd frontend && npx playwright test --update-snapshots

# CI-only compare. Fails if any screenshot diverges from baseline.
gui-screens-ci:
	cd frontend && npx playwright test
