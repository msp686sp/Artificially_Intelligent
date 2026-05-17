# GUI Build Plan (a.k.a. "the gooey")

A complete, opinionated plan for a single-developer-user GUI on top of
the existing rental platform. Goal: surface every workflow, every
source, every score, every backtest run, every config, and every row
of the warehouse — with charts, comparisons, tables, search, filters,
SQL, and full mobile + desktop responsiveness.

**Hard constraint:** zero new product features. The GUI is a window
into the system that already exists.

---

## 1. Target user + non-goals

- **One user** (the developer). Authentication is optional and
  defaults off; everything is local-first.
- **Depth over breadth.** Where a tradeoff exists between "polished
  consumer surface" and "developer sees everything," we pick the
  developer view every time — raw SQL access, raw schema, refresh
  logs, internal IDs.
- **Non-goals:** multi-tenant auth, real-time collaboration, mobile
  app (just responsive web), accessibility audits beyond the basics.

---

## 2. Stack

| Layer | Choice | Why |
|---|---|---|
| API | **FastAPI** + uvicorn + pydantic v2 | Same Python runtime as the platform; auto OpenAPI; trivial WebSocket support for long-running refresh/backtest progress |
| DB driver | Existing **DuckDB** | All data is already there; no second store |
| Frontend build | **Vite** + TypeScript | Fast dev loop, smaller bundles than CRA, first-class TS |
| Framework | **React 18** | Largest ecosystem, mature, agents are well-trained on it |
| Styling | **Tailwind CSS 3.4** + headlessui | Requested explicitly; consistent design system, mobile-first responsive utilities |
| Router | **React Router v6** | File-based-ish routing without Next.js overhead |
| Data | **TanStack Query** (`@tanstack/react-query`) | Caching, retries, background refresh, devtools |
| Tables | **TanStack Table v8** | Headless, fully customizable, supports the sort/filter/pagination workloads |
| Charts | **Recharts** | Composable React charts; ResponsiveContainer handles mobile reflow |
| SQL editor | **CodeMirror 6** (`@uiw/react-codemirror` + `@codemirror/lang-sql`) | Smaller than Monaco; touch-friendly enough on tablets |
| YAML editor | CodeMirror with `@codemirror/lang-yaml` | Same family as SQL editor; consistent UX |
| Forms | **React Hook Form** + **zod** | Type-safe validation that matches FastAPI/pydantic models |
| Unit tests | **Vitest** + **React Testing Library** | Vite-native, fast |
| E2E + visual | **Playwright** | Already installed at `/opt/node22/bin/playwright`; cross-browser + screenshot diff |
| Lint/format | **eslint** + **prettier** + Tailwind plugin | Standard |
| Backend tests | **pytest** + **httpx.AsyncClient** | Already in pyproject; integration-test the API |

---

## 3. Repository layout

```
.
├── src/rental/                     # existing Python package
├── api/                            # NEW — FastAPI app
│   ├── __init__.py
│   ├── main.py                     # FastAPI app, middleware, router mount
│   ├── deps.py                     # connection factory, settings
│   ├── progress.py                 # in-process pub/sub for WebSocket events
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── health.py
│   │   ├── sources.py              # GET /sources, POST /sources/{name}/refresh
│   │   ├── sql.py                  # POST /sql (read-only enforced)
│   │   ├── schema.py               # GET /schema (table tree)
│   │   ├── rankings.py             # GET /rankings (paginated)
│   │   ├── zips.py                 # GET /zips/{zcta5}, /zips/compare
│   │   ├── charts.py               # pre-computed chart payloads
│   │   ├── manifest.py             # GET /manifest
│   │   ├── config.py               # GET/PUT /config/{file}
│   │   ├── backtest.py             # POST /backtest/run, /tune, /runs, /runs/{id}
│   │   └── events.py               # WebSocket /events
│   └── models/                     # pydantic schemas
├── frontend/                       # NEW — Vite + React + TS
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── postcss.config.cjs
│   ├── playwright.config.ts
│   ├── index.html
│   ├── src/
│   │   ├── main.tsx                # entry; React root
│   │   ├── App.tsx                 # router shell + layout
│   │   ├── api/                    # generated client + fetch wrappers
│   │   │   ├── client.ts
│   │   │   └── types.ts
│   │   ├── components/             # shared UI (Button, Card, Table, Sheet, …)
│   │   ├── layout/
│   │   │   ├── Shell.tsx           # sidebar + topbar
│   │   │   ├── Sidebar.tsx
│   │   │   ├── MobileNav.tsx
│   │   │   └── ThemeProvider.tsx
│   │   ├── routes/                 # one folder per page (see §4)
│   │   ├── charts/                 # Recharts wrappers
│   │   ├── hooks/
│   │   ├── lib/                    # utilities, formatters
│   │   └── styles/
│   │       └── globals.css
│   └── tests/
│       ├── unit/                   # vitest
│       └── e2e/                    # playwright
└── docs/
    ├── plan.md                     # existing build plan
    ├── rental-market-analysis-discovery.md
    └── gooey-plan.md               # THIS FILE
```

`api/` and `frontend/` are top-level so they're easy to reason about
independently. They share nothing at build time; the frontend talks to
the API over HTTP.

---

## 4. Pages (the gooey map)

Every URL is a deep-link. Mobile uses the same routes with a different
chrome.

| Path | Page | What you see |
|---|---|---|
| `/` | **Dashboard** | Top-line numbers (sources fresh / stale / errored, zips in warehouse, top-5 by market_score, manifest health). Live status pill. "Run all refreshes" quick action. Recent backtest summary. |
| `/sources` | **Sources** | Card per source: name, status, last refresh, age, manifest rows, warehouse rows, source URL, license, cadence. Action menu: Refresh, Preview rows, Open in SQL, Reset manifest. |
| `/sources/:name` | **Source detail** | Schema for the raw table, sample rows (paginated), refresh history, fetch URL, copy-to-clipboard for the CLI command. |
| `/rankings` | **MarketScore rankings** | TanStack Table over `/rankings` with server-side sort + pagination. Filter sidebar (editable filters.yaml live). Column selector. Bulk select → Compare. CSV export. |
| `/rankings/:zcta5` | **Zip detail** | Single-zip drill-down. Identity header (state, metro, county). Score breakdown radar (5 sub-scores). Feature table with raw + z-score columns. Time series charts for ZHVI / ZORI. Redfin DOM strip chart. Tax / insurance / eviction / climate cards. Filter status (which filters this zip passes/fails). |
| `/compare?z=NNNNN,NNNNN,…` | **Compare** | Side-by-side N zips. Numeric grid, sub-score radar overlay, ZHVI/ZORI overlay charts, diff column ("better/worse vs first"). |
| `/sql` | **SQL workbench** | CodeMirror SQL editor (autocomplete from schema). Run, Save, History. Read-only enforcement on by default with a toggle for the dev. Results table with sort/CSV. EXPLAIN view. Query templates library. |
| `/schema` | **Schema browser** | Tree of tables → columns. Click table → preview + counts. "Show as SQL" copies a SELECT skeleton. |
| `/filters` | **Filters & weights** | Side-by-side editors for filters.yaml + weights.yaml using CodeMirror. Live diff panel showing what changes in the top-100 rankings if filters/weights were applied today. Save creates a versioned snapshot. |
| `/backtest` | **Backtest** | New run form (start/end/snapshot grid). Run history. Each run row clicks through to the inline HTML report (iframe-isolated) + a tabular summary view (Spearman per snapshot, quintile means, READY/NOT READY banner). |
| `/backtest/compare?ids=…` | **Backtest compare** | Side-by-side runs: weight diff, Spearman by snapshot, baseline deltas. |
| `/manifest` | **Manifest** | Same data as `rental status` but interactive: filter by status, sort by age, drill into a source. |
| `/settings` | **Settings** | Env vars, warehouse path, manifest path. Theme toggle (light/dark/auto). Mobile bottom-nav toggle. About + version. |
| `/logs` | **Refresh log** | `refresh_log` table viewer with filter/sort. |

All pages live in `frontend/src/routes/<route>/index.tsx`. Each owns
its own loader hook + components, but pulls layout + design tokens
from `frontend/src/layout` + `frontend/src/components`.

---

## 5. API surface

OpenAPI is auto-generated from FastAPI's type hints. The TypeScript
client is generated from the OpenAPI JSON at build time. Endpoints:

### Health + meta
- `GET /api/health` → `{status, version, uptime_s}`
- `GET /api/version` → `{api, app, python}`

### Sources
- `GET /api/sources` → `[{name, last_refresh, rows_loaded, status, source_url, license, cadence, warehouse_rows}]`
- `GET /api/sources/{name}` → detail
- `POST /api/sources/{name}/refresh` → kicks off a job; returns `{job_id}`. Progress streams on the WebSocket.
- `GET /api/sources/{name}/preview?limit=50&offset=0` → rows
- `GET /api/sources/{name}/schema` → column info

### SQL + schema
- `POST /api/sql` body `{query, limit?: 1000, read_only?: true}` → `{columns, rows, elapsed_ms, row_count}`. Enforces read-only by checking the parsed statement via DuckDB's `EXPLAIN`. The dev can override by setting `read_only=false`.
- `GET /api/schema` → tree `[{kind: "table"|"view", name, columns: [{name, type, nullable}], row_count}]`

### Rankings + zips
- `GET /api/rankings?state=&metro=&min_score=&max_score=&sort=market_score&order=desc&limit=50&offset=0&filters_yaml=`
- `GET /api/zips/{zcta5}` → full detail bundle (identity, scores, features, time series)
- `GET /api/zips/compare?zcta5s=10025,46220,…` → keyed dict of details + diff helpers

### Charts
- `GET /api/charts/score-distribution?dim=market_score` → histogram bins
- `GET /api/charts/feature-vs-score?feature=gross_yield_monthly_pct&score=market_score` → scatter
- `GET /api/charts/zhvi/{zcta5}?since=2010-01-01` → time series
- `GET /api/charts/zori/{zcta5}` → same
- `GET /api/charts/redfin/{zcta5}` → DOM + sale-to-list + inventory

### Manifest + config
- `GET /api/manifest` → all entries
- `GET /api/manifest/{source}` → one
- `GET /api/config/files` → `["filters.yaml", "weights.yaml", "watchlist.yaml"]`
- `GET /api/config/{file}` → `{content: "...", parsed: {...}}`
- `PUT /api/config/{file}` body `{content}` → 204 (validates as YAML server-side first)

### Backtest
- `POST /api/backtest/run` body `{start_year, end_year}` → `{job_id, run_id}`
- `POST /api/backtest/tune` body `{train_start, train_end, validate_start, validate_end}` → same shape
- `GET /api/backtest/runs` → list (id, started_at, mode, weights, primary metric)
- `GET /api/backtest/runs/{id}` → detail (snapshots, quintile bins, html_report_path)
- `GET /api/backtest/runs/{id}/report.html` → raw HTML

### WebSocket
- `WS /api/events` → emits `{type: "refresh.progress"|"backtest.progress", job_id, payload}` for any in-flight job

### Pre-flight + read-only enforcement
- `POST /api/sql` parses the query with `duckdb.cursor().sql(f"EXPLAIN {q}")` and rejects statements that touch INSERT/UPDATE/DELETE/CREATE/DROP/ALTER unless `read_only=false`. Even with `read_only=false`, the API writes back-pressure via a `dev_unsafe=true` query param the frontend never sets unless the user explicitly toggles it in `/sql`.

---

## 6. Design system

Tailwind-driven, tokens defined in `tailwind.config.ts`. Mobile-first
breakpoints: default → `sm: 640px` → `md: 768px` → `lg: 1024px` → `xl: 1280px`.

### Tokens
```ts
theme.extend = {
  colors: {
    bg:       { DEFAULT: "#0b0d12", subtle: "#11141b", panel: "#171a23" },
    fg:       { DEFAULT: "#e6e8ee", muted: "#9aa0ad", subtle: "#6b7080" },
    accent:   { DEFAULT: "#5b8def", hover: "#7a9ff2" },
    success:  "#3aaf85",
    warning:  "#d9a441",
    danger:   "#e15c5c",
    score:    { high: "#3aaf85", mid: "#d9a441", low: "#e15c5c" },
  },
  fontFamily: {
    sans: ["Inter", "system-ui", "sans-serif"],
    mono: ["JetBrains Mono", "ui-monospace", "monospace"],
  },
  spacing: { 18: "4.5rem", 88: "22rem" },
};
```
Dark theme is the default (developer tools convention). Light theme available via the `class="dark"` toggle on `<html>`.

### Layout primitives
- `Shell` — full-page chrome (sidebar + topbar + content).
- `Card` — `bg-bg-panel rounded-xl shadow-sm p-4`
- `Stat` — large number + label + delta arrow.
- `DataTable` — TanStack Table wrapper with our toolbar (search, column visibility, density toggle, export).
- `CodeBlock` — read-only CodeMirror.
- `Sheet` — slide-out panel (used for filter sidebar on `/rankings`).
- `Dialog` — modal.
- `Toast` — bottom-right notification.

### Responsive rules
- `< sm`: drawer-style navigation. Tables collapse to **stacked cards** (TanStack Table's row → key/value pair list). Charts use full width via Recharts' `ResponsiveContainer`. SQL workbench falls back to a single-column layout with the editor over the results.
- `sm – lg`: sidebar collapses to icons; full table layouts.
- `≥ lg`: full sidebar; multi-column comparison views.

Touch targets ≥ 44px. Hover-only interactions have tap equivalents (long-press for context menus is **not** used — we expose explicit `…` action buttons).

---

## 7. Workflows the GUI must execute end-to-end

These workflows are the acceptance test list. Each must work on
desktop and mobile, and each is covered by at least one Playwright test.

1. **Onboarding**: visit `/` cold (empty warehouse) → dashboard shows "warehouse not initialized," primary CTA "Run `make init`." After init, dashboard shows zero rows and CTAs for sources.
2. **Refresh a source**: `/sources` → click ZHVI → "Refresh." Progress streams over WebSocket. Toast on completion. Row count updates without page reload.
3. **Refresh from fixture** (dev shortcut): each source card has an "Use bundled fixture" link; clicking calls the same endpoint with `from_fixture=true`.
4. **Run end-to-end rank**: dashboard "Compute MarketScore" → calls `POST /api/rankings/populate` (which is just the populate orchestrator) → toast → land on `/rankings`.
5. **Explore rankings**: filter by state, set min market_score, sort by yield_score, click into a zip.
6. **Compare zips**: select 3 rows → "Compare" → `/compare?z=…` with overlaid time-series.
7. **Edit filters**: `/filters` → edit YAML → "Preview" runs a server-side dry-run against the current scores and shows the diff (rows added/removed). "Save" persists.
8. **SQL workbench**: open `/sql`, write `SELECT zcta5, market_score FROM zip_scores ORDER BY market_score DESC LIMIT 20`, run, sort columns, export CSV.
9. **Schema browser**: `/schema` → click `raw_zillow_zhvi` → preview 50 rows → "Open in SQL" → query autopopulated.
10. **Backtest**: `/backtest` → click "New run" → snapshot range 2013–2019 → progress streams → run lands in history → click → HTML report rendered inline + tabular summary.
11. **Backtest compare**: select 2 runs → `/backtest/compare?ids=…` → see weight diff + Spearman deltas.
12. **Mobile end-to-end**: every workflow above runs on a 390×844 viewport (iPhone 14). Sidebar becomes a sheet; tables become cards; charts reflow.

---

## 8. Testing strategy

### Backend (pytest, in `tests/api/`)
- Every endpoint hit with happy-path + error path.
- SQL endpoint covers: read-only enforcement, statement parsing, multi-statement rejection, large-result truncation, parameterized templates.
- Refresh endpoint: kicks off a fake source with a stub fetch, verifies WebSocket events come out in order.
- Backtest endpoints: stub the run with synthetic data so tests don't take minutes.

### Frontend unit (vitest, in `frontend/tests/unit/`)
- Pure-function tests for formatters, sort/filter helpers, YAML diff.
- Component tests for `DataTable`, `Stat`, `Sheet`, `CodeBlock`.
- Hook tests for query keys + cache invalidation.

### Frontend E2E (Playwright, in `frontend/tests/e2e/`)
- One test file per workflow above (`*.spec.ts`).
- **Two projects** in `playwright.config.ts`: `desktop-chrome` (1440×900) and `mobile-iphone` (390×844 with Pixel 7 emulation alternate).
- Every spec ends with `await expect(page).toHaveScreenshot()`.
- Screenshots stored under `frontend/tests/e2e/__screenshots__/` and committed.
- Visual regression: `npx playwright test --update-snapshots` regenerates; CI compares.

### Visual baseline coverage
| Page | Desktop | Mobile |
|---|---|---|
| `/` | ✓ | ✓ |
| `/sources` | ✓ | ✓ |
| `/sources/zillow_zhvi` | ✓ | ✓ |
| `/rankings` | ✓ | ✓ |
| `/rankings/10025` | ✓ | ✓ |
| `/compare?z=10025,46220` | ✓ | ✓ |
| `/sql` | ✓ | ✓ |
| `/schema` | ✓ | ✓ |
| `/filters` | ✓ | ✓ |
| `/backtest` | ✓ | ✓ |
| `/manifest` | ✓ | ✓ |
| `/settings` | ✓ | ✓ |

24 screenshots committed to source control.

### Smoke runner
- `make gui-test` → `pytest tests/api && cd frontend && npm run test && npx playwright test`
- `make gui-screens` → re-renders all screenshots
- `make gui-dev` → starts API on :8000 and Vite on :5173 in parallel

---

## 9. Make targets

```makefile
gui-install:      cd api && pip install -e ../[gui] ; cd frontend && npm ci
gui-dev:          start API + Vite together (using `concurrently`)
gui-build:        frontend production build → frontend/dist
gui-serve:        FastAPI serves frontend/dist on :8000
gui-test:         API tests + frontend unit tests + Playwright
gui-screens:      regenerate Playwright screenshots
gui-screens-ci:   compare Playwright screenshots in CI mode
```

---

## 10. Build partitioning (8 parallel agents)

Each agent is a vertical slice or shared layer. Conflicts are
intentionally minimized: shared files (`api/main.py`,
`frontend/src/App.tsx`, `package.json`, `pyproject.toml`) get small,
additive edits in clearly-labeled sections.

| # | Agent | Owns | Conflict surface |
|---|---|---|---|
| 1 | **api-core** | FastAPI app skeleton, deps, progress pub/sub, /health, /sources, /manifest, /schema; backend test infra; pyproject `[gui]` extra | `pyproject.toml`, `api/main.py` |
| 2 | **api-sql-rankings** | /sql, /rankings, /zips/* (incl. compare), /charts/*; their tests | `api/routes/__init__.py` |
| 3 | **api-config-backtest** | /config/*, /backtest/*, /events (WebSocket); their tests | `api/routes/__init__.py` |
| 4 | **fe-shell** | Vite scaffolding, tsconfig, tailwind config, design tokens, Shell+Sidebar+MobileNav+ThemeProvider, design-system primitives (Button/Card/Stat/DataTable/CodeBlock/Sheet/Dialog/Toast), router root, ESLint+Prettier, **no route content yet** (just blank routes) | `frontend/package.json`, `frontend/src/App.tsx` |
| 5 | **fe-sources-dashboard** | Pages: `/`, `/sources`, `/sources/:name`, `/manifest`, `/settings`, `/logs`. WebSocket progress integration. | `frontend/src/App.tsx` |
| 6 | **fe-rankings-zips** | Pages: `/rankings`, `/rankings/:zcta5`, `/compare`, `/filters`. TanStack Table integration, filter sidebar, Recharts panels (score breakdown radar, ZHVI/ZORI time series). | `frontend/src/App.tsx` |
| 7 | **fe-sql-backtest** | Pages: `/sql`, `/schema`, `/backtest`, `/backtest/compare`. CodeMirror integration. Iframe-isolated HTML report renderer. | `frontend/src/App.tsx` |
| 8 | **playwright** | `frontend/playwright.config.ts`, full E2E + visual suite (the 24 screenshots), `make gui-test` / `gui-screens` targets, CI workflow update to run them | `Makefile`, `.github/workflows/ci.yml` |

### Coordination rules

- **Agents 1–3** edit `api/routes/__init__.py` by appending one
  `register(router)` line per route module. Conflicts are mechanical.
- **Agents 5–7** each add their routes to `frontend/src/App.tsx` in
  the labeled "// ROUTES" block. Same mechanical conflict pattern.
- **Frontend `package.json`** baseline lands with `fe-shell`. Other
  frontend agents that need a new dep add it via `npm install <pkg>`
  in their worktree and document it in their report. Orchestrator
  reconciles the deps array at merge time.
- **Backend `pyproject.toml` `[gui]` extra** lands with `api-core`.
  Others extend if needed.
- **All agents** must hit:
  - `pytest tests/api` (backend) or `npm run test` (frontend) green
  - `ruff check` (backend) or `eslint` (frontend) clean
  - Their owned Playwright specs passing (agent 8 owns the suite
    overall, but agents 5–7 each contribute the specs for their
    pages and provide baseline screenshots).

---

## 11. Step-by-step build order in the parent session

1. Land this plan (`docs/gooey-plan.md`) — done in this commit.
2. Spin up 8 agents in worktrees.
3. As each agent finishes, integrate onto a `claude/gui` branch.
4. Conflict-resolve shared files at each merge.
5. Re-anchor `pip install -e .` and `npm ci` in the integrated tree.
6. Run the full smoke: `make test && make gui-test && make smoke && make smoke-rank`.
7. Commit + push, update PR.

---

## 12. Out of scope (for honesty)

- No login / multi-user. Single-user assumption is encoded in the API
  (CORS open to `localhost`, no auth middleware).
- No production deployment guide. `gui-serve` is for the developer's
  own machine.
- No PWA / offline mode. The platform is local-first by design; the
  GUI is just a process you start.
- No real-time collaborative editing of filters/weights — last-writer
  wins, with file revision history in git.
- No Phase 7 (alerts) or Phase 8 (dashboard streamlit) work — they're
  superseded by this GUI.
