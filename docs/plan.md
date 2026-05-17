# Rental Market Analysis Platform — Build Plan

This plan operationalizes the decisions captured in
[`rental-market-analysis-discovery.md`](./rental-market-analysis-discovery.md).
Every choice below traces back to a confirmed decision; nothing is speculative.

## Confirmed design

| Decision | Choice |
|---|---|
| Audience | Personal tool, just for you |
| Investment thesis | Buy-and-hold SFR cash flow |
| Source of edge | Doing the basics rigorously |
| Geographic grain | Zip-code level (ZCTA), nationwide |
| Data budget | Free + scraped only |
| Cadence | Monthly refresh + event triggers on **market-metric threshold crossings** (no corporate news scraping, no regulatory feeds in v1) |
| Tenant risk | First-class scoring dimension (`OperabilityScore`) |
| Filters | Configurable hard filters + soft scoring (default ON: **price band $80k–$250k** only; regulation/climate/population filters available but OFF by default) |
| Portfolio | Tracked as metadata only; does not change recommendations |
| Outputs | Layered: Jupyter notebook + local dashboard + weekly email digest |
| Backtest target | **5-year levered cash-on-cash + appreciation, combined** (single primary target; other definitions computed but not used for weight tuning) |
| Funnel depth | v1 ends at the zip code. **v2 adds a property-level underwriter** that takes an address + price + rehab and runs the standardized pro forma against zip-level market inputs. |

## Final scoring model

```
MarketScore(zip) =
    0.25 × YieldScore        (rent/price, taxes, insurance)
  + 0.30 × DemandScore       (jobs, migration, income, demographics)
  + 0.20 × SupplyScore       (permits vs. formation, vacancy, DOM)
  + 0.20 × OperabilityScore  (eviction, tenant income, regulation, crime)
  - 0.05 × RiskScore         (climate, insurance trend, employer HHI)
```

Weights tuned against the backtest in Phase 6. Operability gets meaningful
weight because of the SFR-cash-flow thesis: a zip with great yield but
bad operator outcomes is a trap, and the scorecard must say so.

Default hard filters (configurable via YAML). Only the price band and a
data-quality minimum are ON by default — everything else is opt-in so the
universe of zips you'll consider isn't silently pre-narrowed beyond your
non-negotiable.

```yaml
filters:
  # ON by default
  median_home_price: { min: 80000, max: 250000, enabled: true }
  zori_coverage:     { min: 24, enabled: true }     # months of rent data available

  # OFF by default — opt in when/if you want them
  gross_yield_monthly_pct:    { min: 0.8, enabled: false }
  exclude_rent_controlled:    { enabled: false }
  exclude_high_climate_risk:  { enabled: false }
  exclude_shrinking_metros:   { population_cagr_min: -0.0025, enabled: false }
```

---

## Tech stack

- **Language:** Python 3.12
- **Warehouse:** DuckDB + Parquet on disk (single-file, zero infra)
- **ETL:** Plain Python modules + Makefile targets (no Prefect/Airflow at this scale)
- **HTTP:** `httpx` with `requests-cache`
- **Scraping (where needed):** `selectolax` for HTML; `playwright` only if JS-required
- **Geo:** `geopandas` + HUD-USPS ZIP-Tract crosswalk + Census TIGER
- **Notebook:** Jupyter
- **Dashboard:** Streamlit (single-file deploy, fits "personal tool")
- **Email:** SMTP via local relay or SendGrid free tier; HTML template via `jinja2`
- **Scheduler:** `systemd` user timers (or cron) — no orchestrator
- **Testing:** `pytest` + `pytest-snapshot` for ETL output regression

Project layout:

```
artificially_intelligent/
├── data/
│   ├── raw/                  # untouched downloads (gitignored)
│   ├── interim/              # parsed but un-joined
│   └── warehouse.duckdb      # gitignored; rebuildable from raw
├── src/rental/
│   ├── geo/                  # crosswalks, downscaling
│   ├── sources/              # one module per data source
│   ├── features/             # engineered metrics per dimension
│   ├── scoring/              # sub-scores + composite
│   ├── filters/              # hard-filter engine
│   ├── alerts/               # threshold-crossing detector + digest
│   ├── backtest/             # historical reconstruction + validation
│   └── cli.py                # `rental refresh`, `rental score`, `rental digest`
├── notebooks/                # exploratory + reporting
├── dashboard/                # Streamlit app
├── config/
│   ├── filters.yaml          # user-editable defaults
│   ├── weights.yaml          # tunable scoring weights
│   └── watchlist.yaml        # zips you care about + alert thresholds
├── tests/
├── docs/
└── Makefile
```

---

## Phased build

Phases are sequenced so each one produces a usable artifact before the next
starts. Anything past Phase 6 is optional and can be reprioritized after the
backtest tells us which features actually predict outcomes.

### Phase 0 — Foundation (2 days)

- Python project skeleton, dependencies, Makefile, pytest harness
- DuckDB initialization + schema migrations (raw / interim / mart / feature layers)
- Geo spine: load HUD-USPS ZIP↔TRACT crosswalk, Census ZCTA↔COUNTY↔CBSA tables
- `rental refresh --source <name>` CLI scaffold

**Deliverable:** `make init` produces a working warehouse with empty tables and the geo spine populated.

### Phase 1 — Yield half (1 week)

Sources:
- Zillow Research: ZHVI (price), ZORI (rent), inventory, DOM — zip-level CSVs
- Redfin Data Center: zip-level weekly market tracker
- Realtor.com Research: zip-level monthly market hotness
- County effective tax rates: scrape top-50 MSAs (Lincoln Institute supplements)
- State homeowner insurance averages (NAIC + state DOIs)

Features:
- `gross_yield_monthly` = ZORI / ZHVI × 100
- `effective_tax_rate` (joined county → zip)
- `insurance_rate_estimate` = state_avg × climate_multiplier (placeholder until Phase 5)
- `zori_coverage_months` (data quality)

Scoring:
- `YieldScore` = 0.50·z(grossYield) + 0.30·z(-effTaxRate) + 0.20·z(-insuranceRate)

**Deliverable:** ranked CSV of zips by YieldScore, default filters applied. Sanity-check against a known market (e.g., your reference zip).

### Phase 2 — Demand half (1 week)

Sources:
- BLS QCEW (county × industry × quarter)
- BLS LAUS (county unemployment, monthly)
- BEA Regional (county personal income, annual)
- IRS SOI county-to-county migration (annual, ~2yr lag)
- Census ACS 5-year (zip/ZCTA: demographics, renter share, household income, formation)

Downscaling: county-grain metrics are apportioned to constituent zips by ACS population weights. Each downscaled feature is flagged `is_interpolated=true` so downstream consumers know.

Features:
- `wage_weighted_job_cagr_5yr` = Σ(jobs_industry × median_wage) growth
- `net_agi_in_per_capita`
- `population_cagr_5yr`
- `renter_share` + `renter_share_trend`
- `rent_to_income_ratio` (median rent × 12 / median household income)

Scoring:
- `DemandScore` = 0.30·z(jobs) + 0.30·z(migration) + 0.20·z(popCAGR) + 0.10·z(renterTrend) + 0.10·z(-rentToIncome)

**Deliverable:** ranked CSV by combined `YieldScore + DemandScore`. Compare top-50 to top-50 by yield alone — the differences are the early signal of whether the demand layer adds anything.

### Phase 3 — Supply half (3 days)

Sources:
- Census Building Permits Survey (place/county/MSA, monthly)
- HUD aggregated USPS vacancy data (tract/zip, quarterly)
- Redfin DOM trend (already loaded in Phase 1)

Features:
- `permit_to_formation_ratio` = permits_5yr / household_formation_5yr
- `vacancy_rate` (USPS residential)
- `dom_trend_12mo`

Scoring:
- `SupplyScore` = 0.50·z(-permitToFormation) + 0.30·z(-vacancy) + 0.20·z(-domTrend)

**Deliverable:** full preliminary `MarketScore` (Yield + Demand + Supply, no Operability yet) with sub-score breakdown.

### Phase 4 — Operability (tenant-risk) layer (1 week)

This is the SFR-cash-flow-specific dimension and the place the platform's
opinion shows up most clearly. The dirty secret of high-yield Midwest/South
markets is operator-side pain.

Sources:
- **Eviction Lab** (Princeton) — county/tract eviction filings + rates, public CSVs
- **HUD Picture of Subsidized Households** — voucher density (Section 8 market depth)
- **ACS rent-burden tables** — median tenant rent-to-income
- **FBI Crime Data Explorer + select PD open data** — crime levels + 3yr trend
- **State landlord-tenant law strength index** — manually curated from NCSL/RentRedi resources; lives in `data/reference/landlord_friendliness.csv`, versioned

Features:
- `eviction_filing_rate`
- `voucher_market_depth` (vouchers / rental units)
- `tenant_rent_burden_pct`
- `crime_index` + `crime_trend_3yr`
- `landlord_friendliness_score` (state-level, joined down)
- `vacancy_duration_proxy` (USPS long-vacancy share)

Scoring:
- `OperabilityScore` = 0.25·z(-evictionRate) + 0.20·z(landlordFriendliness) + 0.20·z(-tenantBurden) + 0.15·z(-crimeIndex) + 0.10·z(-crimeTrend) + 0.10·z(voucherDepth)

**Deliverable:** full `MarketScore` with all five dimensions. Top-50 list now reflects the SFR-cash-flow thesis honestly — Memphis-type traps should drop materially vs. the Phase 3 ranking.

### Phase 5 — Risk modifiers (3 days)

Sources:
- FEMA NFHL flood zones (parcel polygons → zip aggregation)
- NOAA billion-dollar disaster history (county)
- State insurance commissioner annual filings (premium CAGR)
- BLS QCEW (already loaded) → recompute employer HHI

Features:
- `climate_risk_composite` (flood + wildfire WUI + disaster frequency)
- `insurance_premium_cagr_5yr`
- `employer_hhi` (NAICS 2-digit concentration)

Refines `insurance_rate_estimate` from Phase 1 with climate multiplier.

Scoring:
- `RiskScore` = 0.40·z(climateComposite) + 0.30·z(insuranceCAGR) + 0.30·z(employerHHI)

**Deliverable:** final `MarketScore` formula complete.

### Phase 6 — Backtest harness (1 week) — *the validation gate*

No weight is trusted until this passes.

**Primary target — what the scorecard is tuned against:**

```
LeveredTotalReturn_5yr(zip) =
    Σ over 5 years of [annual_cash_flow × (1 / cash_invested)]    # CoC contribution
  + [(ZHVI_t+5 − ZHVI_t) × leverage_ratio] / cash_invested        # appreciation × leverage
```

with standard assumptions held constant across zips:
- 25% down, 30yr fixed at prevailing rate as of snapshot date
- 10% PM, 8% maintenance, 5% capex reserve, 7% vacancy
- Tax/insurance from zip features

Secondary targets — computed but not used for weight tuning, reported alongside for context:
- Year-1 CoC only
- 5yr rent-growth-only (ZORI CAGR)
- Risk-adjusted version (return / σ)

Method:
- Reconstruct feature snapshots as of Jan 2013, 2014, ..., 2019 using only data available at that time (point-in-time feature store)
- Compute realized `LeveredTotalReturn_5yr` per zip per snapshot
- Spearman rank correlation between `MarketScore` and realized return
- Bucket zips into score quintiles; chart realized outcome distribution per quintile
- Walk-forward: train weights on 2013–17 windows, validate on 2018–22 windows
- Baselines to beat: yield-only ranking, equal-weighted dimensions, random
- Tune weights against the primary target only

**Deliverable:** `backtest_report.html` showing score vs. realized levered total return per snapshot, with confidence intervals, walk-forward stability, and the recommended weights. If the top quintile doesn't beat the bottom quintile on the primary target with statistical significance, the scorecard isn't ready — iterate on features and weights before going further.

### Phase 7 — Event-trigger alerting (3 days)

Scope tightened: v1 alerts only on **market-metric threshold crossings**.
No corporate news scraping, no regulatory feed monitoring, no distress-spike
detectors — those can come later if the simple version proves valuable.

- `rental refresh` writes a versioned monthly snapshot to `data/snapshots/<yyyy-mm>.parquet`
- `rental alerts compute` diffs the latest snapshot against the prior, detects metric crossings per `config/watchlist.yaml` rules
- Threshold types supported:
  - Absolute (`vacancy_rate < 5%`)
  - Delta (`wage_weighted_job_cagr_5yr changed by > 1pp`)
  - Rank (`MarketScore moved up > 50 percentile ranks`)
- `rental digest send` renders an HTML email with: top-20 zips this month, watchlist changes, new alerts, zips that fell out of qualification

**Deliverable:** Monday-morning email digest, fired by a systemd user timer.

### Phase 8 — Streamlit dashboard (1 week)

Pages:
- **Rankings** — filterable table; click zip → drill page
- **Zip drill** — sub-score breakdown, raw feature values, historical chart of MarketScore, peer-zip comparison
- **Watchlist** — your zips + alert state
- **Backtest** — embedded HTML report from Phase 6
- **Holdings** — read your `config/holdings.yaml`, show metadata-only view (no rec changes per design)

**Deliverable:** `streamlit run dashboard/app.py` opens the full UI locally.

### Phase 9 — Polish + ongoing care (ongoing)

- Documentation of every data source (URL, license, refresh URL, parse notes)
- Snapshot tests on the ETL so a source-format change is caught
- `make doctor` checks data freshness per source, warns on staleness
- Quarterly weight re-tune from rolling backtest

---

## v2 roadmap — Property-level underwriter

Once v1 is trusted and used weekly, v2 layers a per-property pro forma on
top. Explicitly out of scope until the market scorecard has earned its
keep.

- `rental underwrite <address> --price <p> --rehab <r>` CLI
- Geocode → resolve to zip → pull zip's market features (tax rate, insurance estimate, ZORI rent, ZHVI price)
- Run the standardized pro forma with stress scenarios (rent ±10%, vacancy +5pp, rate ±1pp)
- Output a one-page underwrite: CoC, cap rate, IRR, breakeven rent, breakeven price
- Dashboard page accepts the same inputs
- No listings scraping, no off-market sourcing — those are v3+ if at all

---

## Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Zillow changes their research-data URLs/formats | Medium | Snapshot tests; fall back to Redfin/Realtor for price/DOM |
| ZORI thin coverage in low-density zips | High | Suppress score where `zori_coverage_months < 24`; surface as data-quality flag |
| County-level downscaling distorts zip rankings | Medium | Flag downscaled features; sensitivity-test by recomputing scores at county grain too |
| Eviction Lab data is dated (2018 base) | High | Use as structural prior, refresh with state-court data where free |
| Insurance modeled as `state × multiplier` is wrong for FL/CA/LA | High | Explicit confidence band on `RiskScore` in those states; revisit as a paid-data candidate later |
| Backtest doesn't validate the scorecard | Medium | This is the point of Phase 6 — if it fails, we adjust features/weights before launch, not after |
| Scope creep into per-property underwriter | Low (design says no) | Hold the line; that's a separate v2 project |

---

## Timeline

| Phase | Effort | Cumulative |
|---|---|---|
| 0. Foundation | 2 days | 2d |
| 1. Yield | 1 week | 1w 2d |
| 2. Demand | 1 week | 2w 2d |
| 3. Supply | 3 days | 2w 5d |
| 4. Operability | 1 week | 3w 5d |
| 5. Risk modifiers | 3 days | 4w 3d |
| 6. Backtest harness | 1 week | 5w 3d |
| 7. Alerts + digest | 3 days | 6w 1d |
| 8. Dashboard | 1 week | 7w 1d |
| 9. Polish | ongoing | — |

~7 weeks of focused part-time work to a validated, used-weekly platform.
Scope tightenings in Phase 6 (single primary target) and Phase 7
(metric crossings only) shaved roughly a week off the original estimate.

---

## Phase-0 kickoff checklist

When you say go, the first session does only:

1. Initialize Python project (`pyproject.toml`, deps, formatters, pytest)
2. Set up DuckDB + the geo spine ingestion (ZCTA, county, CBSA, crosswalks)
3. Scaffold `rental` CLI with `init`, `refresh`, `score`, `digest` subcommands (stubbed)
4. Write the first ETL source as a reference shape: **Zillow ZHVI**
5. Ship a smoke test: `make refresh && make score-yield-only` produces a tiny ranked CSV

That single end-to-end slice proves the architecture before we widen it.
