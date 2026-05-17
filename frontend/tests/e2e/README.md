# Playwright E2E + Visual Regression Suite

The end-to-end + visual-regression suite for the rental-market GUI.
Owned by agent 8 (this directory); referenced by every frontend agent.

## TL;DR

```sh
cd frontend
npm ci
npx playwright install --with-deps chromium
npx playwright test               # run all specs, both projects
npx playwright test --list        # what specs exist
npx playwright test --update-snapshots   # regenerate baselines
npx playwright test --reporter=line dashboard.spec.ts  # one file
```

## Required deps (to land in `frontend/package.json`)

This agent (#8) does not own `frontend/package.json` — agent 4
(`fe-shell`) does. The orchestrator must add the following to
`devDependencies` at integration time:

```jsonc
{
  "@playwright/test": "^1.48.0",
  "@types/node": "^20.16.0"
}
```

`fixtures.ts` uses `node:fs` + `node:path` + `__dirname`, so
`@types/node` is required to keep `tsc` / `eslint` clean.

Or from the repo root:

```sh
make gui-test       # pytest + frontend unit + Playwright
make gui-screens    # regenerate Playwright baselines
make gui-screens-ci # compare-only (used in CI)
```

## Architecture

- **`playwright.config.ts`** — two projects (`desktop-chrome` 1440×900,
  `mobile-iphone-14` 390×844) and one web server (`npm run dev -- --port 5173`).
  Both projects run every spec, so each page gets two screenshots.
- **`fixtures.ts`** — every test extends a custom `test` from here, which:
  - Mocks **all** `/api/**` requests against the JSON files in
    `__fixtures__/`. The route table is the single source of truth.
    Unknown endpoints return 404 with `{error: "unmocked api call: …"}`
    so the test fails loudly until you add a fixture.
  - Allows per-test overrides via the `apiOverrides` fixture (e.g. the
    dashboard empty-state test overrides `/api/health`).
  - Injects a CSS reset that disables animations, transitions, caret
    blink, and scrollbars — these are the top sources of pixel diff.
  - Freezes `Date.now()`/`new Date()` to `2026-05-17T12:00:00Z` so any
    relative timestamp ("3 hours ago") renders the same every run.
  - Exposes a `stable()` helper that awaits `document.fonts.ready` plus
    one `requestAnimationFrame` tick — call it right before every
    `toHaveScreenshot()`.
- **`__fixtures__/*.json`** — one file per endpoint. Sourced from the
  API contract in `docs/gooey-plan.md` §5. Backtest reports are HTML
  (served as `text/html`).
- **`__screenshots__/`** — committed baselines. Path template is
  `{snapshotDir}/{testFilePath}/{arg}-{projectName}{ext}` so every spec
  has two screenshots (one per project). **No baselines are committed
  in agent 8's initial commit** — the frontend doesn't exist yet. The
  orchestrator regenerates baselines post-integration via
  `make gui-screens` and commits them. Until then the CI `gui` job runs
  with `continue-on-error: true` (see `.github/workflows/ci.yml`).

## How to update baselines after the frontend lands

1. Pull the integrated `claude/gui` branch.
2. `cd frontend && npm ci && npx playwright install --with-deps chromium`.
3. `make gui-screens` (which runs `npx playwright test --update-snapshots`).
4. Inspect the diff in `__screenshots__/`; commit only the intended
   changes.

## `data-testid` convention

`<component>-<element>-<modifier?>`, kebab-case. The complete list of
testids the specs reference lives in **`testids.md`** — that file is
the source of truth that frontend agents wire components against. If
you add a new testid in a spec, add it to `testids.md` in the same
commit.

## Specs and the §7 workflow map

| Spec file                  | Plan §7 workflow                              |
|----------------------------|-----------------------------------------------|
| `dashboard.spec.ts`        | #1 Onboarding (empty + healthy)               |
| `sources.spec.ts`          | #2 Refresh a source, #3 Refresh from fixture  |
| `source-detail.spec.ts`    | #2 (drill-in)                                 |
| `rankings.spec.ts`         | #5 Explore rankings                           |
| `zip-detail.spec.ts`       | #5 Drill into a zip                           |
| `compare.spec.ts`          | #6 Compare zips                               |
| `sql.spec.ts`              | #8 SQL workbench                              |
| `schema.spec.ts`           | #9 Schema browser                             |
| `filters.spec.ts`          | #7 Edit filters                               |
| `backtest.spec.ts`         | #10 New backtest run                          |
| `backtest-detail.spec.ts`  | #10 Inline report + summary toggle            |
| `backtest-compare.spec.ts` | #11 Backtest compare                          |
| `manifest.spec.ts`         | Manifest viewer                               |
| `settings.spec.ts`         | Settings                                      |

Every spec ends with `await expect(page).toHaveScreenshot()`, so every
workflow is covered by both **interaction** assertions and **visual**
regression on both projects (desktop + mobile = 14 × 2 = 28 baseline
screenshots once generated).

## Hermetic by design

The suite **does not** require the FastAPI backend to be running. All
`/api/**` requests are intercepted in `fixtures.ts`. To prove this:

```sh
# in one terminal
cd frontend && npm run dev -- --port 5173
# in another, with NO backend running:
cd frontend && npx playwright test
```

If a spec hits an endpoint that's missing a fixture, you'll see a
`unmocked api call: /api/foo` error in the test report — add the
fixture file under `__fixtures__/` and a routing rule in `fixtures.ts`.
