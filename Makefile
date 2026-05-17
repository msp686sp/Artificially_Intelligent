.PHONY: init install refresh refresh-fixture score smoke test lint ci doctor status clean

PYTHON ?= python3
RANK_OUT ?= data/rankings/price_rank.csv
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

# Phase 0 smoke: init schema, load fixture, write a price-ranked CSV.
# Proves the end-to-end ETL → query → output path with no network.
smoke: init refresh-fixture score
	@echo "Smoke OK. Output at $(RANK_OUT)"

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
