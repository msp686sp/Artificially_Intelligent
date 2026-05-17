# `data-testid` registry (Playwright E2E source of truth)

This file is the canonical list of `data-testid` attributes the Playwright
suite expects. Frontend agents (4–7) wire components with these exact
strings so specs and snapshots stay stable.

## Convention

`<component>-<element>-<modifier?>`, kebab-case. Examples:

- `dashboard-stat-sources-ok`
- `sources-card-zillow_zhvi-refresh-btn`
- `rankings-row-10025`

Numeric IDs (zip codes, run IDs) keep their original casing/digits. Source
names match the keys in `manifest.json` (snake_case).

## Layout / Shell (`fe-shell`)

| testid                          | meaning                                    |
|---------------------------------|--------------------------------------------|
| `shell-root`                    | the outermost layout container             |
| `shell-sidebar`                 | desktop sidebar                            |
| `shell-mobile-nav`              | mobile bottom-nav drawer trigger           |
| `shell-mobile-nav-open`         | mobile drawer open state                   |
| `shell-theme-toggle`            | theme switcher                             |
| `shell-status-pill`             | top-bar API/warehouse health pill          |
| `toast-region`                  | bottom-right toast container               |
| `toast-item`                    | individual toast                           |

## Dashboard (`/`)

| testid                                  | meaning                          |
|-----------------------------------------|----------------------------------|
| `dashboard-root`                        | page root                        |
| `dashboard-empty-state`                 | "warehouse not initialized" copy |
| `dashboard-empty-cta-init`              | "Run `make init`" CTA            |
| `dashboard-stat-sources-ok`             | count of healthy sources         |
| `dashboard-stat-sources-stale`          | stale count                      |
| `dashboard-stat-sources-error`          | error count                      |
| `dashboard-stat-zip-count`              | zips in warehouse                |
| `dashboard-top5-table`                  | top-5 by market_score            |
| `dashboard-quick-refresh-all`           | "Run all refreshes" CTA          |
| `dashboard-quick-compute-rank`          | "Compute MarketScore" CTA        |
| `dashboard-recent-backtest`             | recent backtest summary card     |

## Sources (`/sources`)

| testid                                              | meaning                       |
|-----------------------------------------------------|-------------------------------|
| `sources-root`                                      | page root                     |
| `sources-grid`                                      | grid wrapper                  |
| `sources-card-<name>`                               | one per source                |
| `sources-card-<name>-status`                        | status badge                  |
| `sources-card-<name>-refresh-btn`                   | refresh action button         |
| `sources-card-<name>-fixture-btn`                   | "Use bundled fixture" link    |
| `sources-card-<name>-preview-btn`                   | "Preview rows" action         |
| `sources-card-<name>-sql-btn`                       | "Open in SQL" action          |

## Source detail (`/sources/:name`)

| testid                          | meaning                  |
|---------------------------------|--------------------------|
| `source-detail-root`            | page root                |
| `source-detail-schema-table`    | schema column table      |
| `source-detail-sample-table`    | sample rows table        |
| `source-detail-history`         | refresh history          |
| `source-detail-cli-copy`        | copy CLI button          |

## Rankings (`/rankings`)

| testid                                | meaning                              |
|---------------------------------------|--------------------------------------|
| `rankings-root`                       | page root                            |
| `rankings-table`                      | TanStack table                       |
| `rankings-row-<zcta5>`                | one per row                          |
| `rankings-col-<field>`                | header cell for a column             |
| `rankings-sort-<field>`               | sort toggle on column header         |
| `rankings-filter-state`               | state filter select                  |
| `rankings-filter-min-score`           | min market_score input               |
| `rankings-filter-apply-btn`           | apply filters button                 |
| `rankings-pagination-next`            | next page                            |
| `rankings-pagination-prev`            | previous page                        |
| `rankings-export-csv-btn`             | export CSV                           |
| `rankings-compare-btn`                | "Compare selected" CTA               |
| `rankings-checkbox-<zcta5>`           | row selector                         |

## Zip detail (`/rankings/:zcta5`)

| testid                          | meaning                          |
|---------------------------------|----------------------------------|
| `zip-detail-root`               | page root                        |
| `zip-detail-identity`           | identity header                  |
| `zip-detail-radar`              | sub-score radar chart            |
| `zip-detail-score-<name>`       | a single sub-score readout       |
| `zip-detail-features-table`     | features (raw + z) table         |
| `zip-detail-chart-zhvi`         | ZHVI time series chart           |
| `zip-detail-chart-zori`         | ZORI time series chart           |
| `zip-detail-chart-redfin`       | Redfin DOM strip chart           |
| `zip-detail-filter-status`      | passes/fails breakdown           |

## Compare (`/compare?z=…`)

| testid                          | meaning                          |
|---------------------------------|----------------------------------|
| `compare-root`                  | page root                        |
| `compare-grid`                  | numeric comparison grid          |
| `compare-row-<field>`           | one row per metric               |
| `compare-cell-<zcta5>-<field>`  | a single value cell              |
| `compare-radar`                 | sub-score radar overlay          |
| `compare-chart-zhvi`            | ZHVI overlay chart               |
| `compare-chart-zori`            | ZORI overlay chart               |

## SQL workbench (`/sql`)

| testid                  | meaning                                  |
|-------------------------|------------------------------------------|
| `sql-root`              | page root                                |
| `sql-editor`            | CodeMirror SQL editor                    |
| `sql-run-btn`           | "Run" button                             |
| `sql-results-table`     | result grid                              |
| `sql-row-count`         | row count readout                        |
| `sql-elapsed`           | elapsed-ms readout                       |
| `sql-readonly-toggle`   | read-only enforcement toggle             |
| `sql-export-csv-btn`    | export CSV                               |
| `sql-history`           | query history panel                      |

## Schema browser (`/schema`)

| testid                                  | meaning                  |
|-----------------------------------------|--------------------------|
| `schema-root`                           | page root                |
| `schema-tree`                           | left-side tree           |
| `schema-tree-item-<name>`               | a table/view node        |
| `schema-preview`                        | right-side preview pane  |
| `schema-preview-open-sql-btn`           | "Open in SQL" button     |

## Filters (`/filters`)

| testid                              | meaning                              |
|-------------------------------------|--------------------------------------|
| `filters-root`                      | page root                            |
| `filters-editor-yaml`               | YAML editor (filters.yaml)           |
| `filters-editor-weights`            | YAML editor (weights.yaml)           |
| `filters-preview-btn`               | preview button                       |
| `filters-diff`                      | diff panel                           |
| `filters-diff-added`                | added rows section                   |
| `filters-diff-removed`              | removed rows section                 |
| `filters-save-btn`                  | save button                          |

## Backtest hub (`/backtest`)

| testid                                  | meaning                          |
|-----------------------------------------|----------------------------------|
| `backtest-root`                         | page root                        |
| `backtest-runs-table`                   | history table                    |
| `backtest-run-row-<id>`                 | one per run                      |
| `backtest-new-run-btn`                  | open new-run form                |
| `backtest-run-form-root`                | form container                   |
| `backtest-run-form-start-year`          | start_year input                 |
| `backtest-run-form-end-year`            | end_year input                   |
| `backtest-run-form-submit`              | submit button                    |

## Backtest detail (`/backtest/:id`)

| testid                                  | meaning                          |
|-----------------------------------------|----------------------------------|
| `backtest-detail-root`                  | page root                        |
| `backtest-detail-tab-report`            | report tab button                |
| `backtest-detail-tab-summary`           | summary tab button               |
| `backtest-detail-report-iframe`         | iframe containing HTML report    |
| `backtest-detail-summary-table`         | spearman-per-snapshot table      |
| `backtest-detail-quintiles`             | quintile-means panel             |
| `backtest-detail-ready-banner`          | READY / NOT-READY banner         |

## Backtest compare (`/backtest/compare`)

| testid                                  | meaning                          |
|-----------------------------------------|----------------------------------|
| `backtest-compare-root`                 | page root                        |
| `backtest-compare-weight-diff`          | weight-diff table                |
| `backtest-compare-spearman`             | spearman-by-snapshot panel       |

## Manifest (`/manifest`)

| testid                                  | meaning                          |
|-----------------------------------------|----------------------------------|
| `manifest-root`                         | page root                        |
| `manifest-table`                        | full manifest table              |
| `manifest-row-<source>`                 | one row per source               |
| `manifest-filter-status`                | status filter                    |
| `manifest-sort-age`                     | sort-by-age toggle               |

## Settings (`/settings`)

| testid                          | meaning                          |
|---------------------------------|----------------------------------|
| `settings-root`                 | page root                        |
| `settings-env`                  | env vars panel                   |
| `settings-warehouse-path`       | warehouse path readout           |
| `settings-manifest-path`        | manifest path readout            |
| `settings-theme`                | theme toggle (light/dark/auto)   |
| `settings-mobile-nav-toggle`    | mobile bottom-nav toggle         |
| `settings-version`              | version readout                  |
