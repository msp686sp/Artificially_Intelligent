# Rental Market Analysis Platform — Discovery

**Scope:** Predict the most profitable US rental markets at the **zip-code level**,
using **free + scrapeable public data only**. This document precedes any
build — its purpose is to enumerate the data sources, the engineering cost
of each, the indicators that actually predict rent growth and appreciation,
and a proposed scoring model. Build decisions come after.

---

## 1. Definition of "profitable"

A property's profitability has two components, and a good platform must
model both:

| Component | What it captures | Time horizon |
|---|---|---|
| **Yield (cash flow)** | NOI / cash invested, after taxes, insurance, PM, maintenance, vacancy, debt service | Year 1+ |
| **Appreciation + rent growth** | Equity buildup, refi capacity, exit price, lease renewals | Years 3–10 |

Most public "best rental markets" lists rank only on **today's** rent-to-price
ratio (gross yield). That misses the dynamic — a 9% gross yield in a
shrinking metro with rising insurance and no wage growth is worse than a
6% yield in a market with 4% annual rent growth and a permit-constrained
supply curve.

The platform's job is to score **both**, then expose the trade-off.

### Standardized pro forma (the "yield" half)

For any candidate zip + price point, compute:

```
Gross rent (annual)           = median_rent_zip × 12 × (1 - vacancy_rate)
- Property tax                = price × effective_tax_rate_zip
- Insurance                   = price × insurance_rate_zip (climate-adjusted)
- Property management         = gross_rent × 0.10
- Repairs & maintenance       = gross_rent × 0.08
- CapEx reserve               = gross_rent × 0.05
- HOA (if applicable)         = lookup
= NOI
- Debt service                = mortgage(price, down%, rate, term)
= Cash flow
÷ Cash invested (down + closing + rehab) = Cash-on-cash return
```

Hold these assumptions **constant across markets** so the ranking is
apples-to-apples. The variation that matters is in the *market inputs*
(rent, tax rate, insurance, vacancy), not the assumption layer.

---

## 2. Data sources (free + scrapeable, zip-grain where possible)

Organized by what each source contributes to the model. Cadence and grain
matter: not every dataset exists at zip-level, and we'll need to interpolate.

### 2.1 Property fundamentals (price, taxes, comps)

| Source | What it gives | Grain | Cadence | Engineering cost |
|---|---|---|---|---|
| **County assessor / tax collector sites** | Assessed value, effective tax rate, ownership, sale history, parcel polygons | Parcel | Annual (re-assessment) | **High** — ~3,000 counties, no standard format, mix of HTML, ArcGIS REST, and PDFs. Build adapters for top-50 MSAs first. |
| **Zillow Research downloads** (free CSVs) | ZHVI (home value index), ZORI (rent index), days-on-market, inventory | Zip, metro | Monthly | **Low** — static CSVs at zillow.com/research/data |
| **Redfin Data Center** | Median sale price, sale/list ratio, DOM, new listings | Zip, metro | Weekly | **Low** — public CSVs |
| **Realtor.com Research** | Active listing count, median list price, hotness index | Zip, metro | Monthly | **Low** — public CSVs |
| **FHFA House Price Index** | Repeat-sales appreciation series | 3-digit zip, MSA | Quarterly | **Low** — CSV download |
| **FFIEC / HMDA** | Mortgage originations, denial rates, loan amounts by tract | Tract | Annual | **Medium** — bulk download, large files |

> **Zip-grain note:** ZHVI and ZORI are the practical backbone for
> zip-level price and rent. They're modeled estimates, not transaction
> data, so cross-check against Redfin/Realtor for sanity.

### 2.2 Distress / acquisition-side signal

| Source | What it gives | Grain | Cadence | Engineering cost |
|---|---|---|---|---|
| **County recorder filings** | NODs, lis pendens, tax liens, trustee sales | Parcel | Daily | **High** — same fragmentation problem as assessors |
| **HUD foreclosure data** | Aggregate foreclosure starts/completions | County, MSA | Quarterly | **Low** |
| **USPS vacancy data (via HUD)** | Residential vacancies (3+ months) | Tract, zip | Quarterly | **Low** — registration required, free |
| **Tax delinquency lists** | Properties behind on property tax | Parcel | Annual | **Medium** — published per-county |

### 2.3 Demand drivers (the leading indicators)

This is where the alpha lives. These predict whether tomorrow's rent will
be higher than today's.

| Source | What it gives | Grain | Cadence | Engineering cost |
|---|---|---|---|---|
| **BLS QCEW** (Quarterly Census of Employment & Wages) | Jobs and wages by industry (NAICS 6-digit) | County | Quarterly | **Low** — bulk download API |
| **BLS LAUS** | Unemployment rate | County, MSA | Monthly | **Low** — API |
| **BLS OEWS** | Wages by occupation | MSA | Annual | **Low** |
| **BEA Regional** | Personal income, GDP by metro | County, MSA | Annual | **Low** — API |
| **IRS SOI county-to-county migration** | Net moves with AGI of movers attached | County | Annual (2yr lag) | **Low** — public files. **Highest-signal migration dataset available for free.** |
| **USPS Change-of-Address (NCOA aggregated)** | Higher-frequency migration | Zip | Monthly | **Medium** — not directly public; HUD publishes aggregated quarterly extracts |
| **Census ACS 5-year** | Demographics, household formation, renter share, income distribution, commute | Tract, zip (ZCTA) | Annual | **Low** — `tidycensus` / Census API |
| **Census Building Permits Survey** | New residential permits | Place, county, MSA | Monthly | **Low** — CSV/API. **Critical for supply-side analysis.** |
| **HUD CHAS** | Housing affordability/cost burden | Tract | Annual | **Low** |
| **GreatSchools (scraped)** | School ratings by attendance zone | School/zone | Annual | **Medium** — TOS-aware scraping; consider NCES as primary |
| **NCES Common Core of Data** | School demographics, performance | School | Annual | **Low** — official, free |
| **FBI Crime Data Explorer** | Reported crime by agency | Agency (≈city) | Annual | **Low** — API |
| **Local PD open data portals** | Incident-level crime | Geocoded | Daily | **High** — per-city portals |
| **First Street Foundation (free tier)** | Flood, fire, heat risk scores | Property, zip | Annual | **Medium** — partial free access; FEMA + NOAA as backstop |
| **FEMA NFHL** | Flood zones | Parcel polygons | Continuous | **Medium** |
| **NOAA SPC + billion-dollar disasters** | Severe weather frequency | County | Continuous | **Low** |
| **State insurance commissioners** | Average homeowner insurance premiums | State (some zip) | Annual | **Medium** — varies by state |

### 2.4 What we *can't* get for free at zip grain

- **MLS sold transactions** (paywalled; we approximate via Redfin/Zillow)
- **Lease-level rent comps** (Rentometer/RentCast are paid; ZORI is our proxy)
- **Per-zip insurance quotes** (state averages are the best free proxy)
- **Real-time eviction filings** (some courts publish, most don't)

These gaps inform where paid data would later add the most value — but
they don't block a v1 scorecard.

---

## 3. Indicators that predict rent growth & appreciation

Ordered by empirical signal strength (based on published academic and
industry research; we'd validate on historical data during build).

### Tier 1 — Strongest predictors

1. **Wage-weighted job growth (5yr CAGR)** — total jobs is noisy; the
   right metric is `Σ(jobs_industry × median_wage_industry)`. Source: BLS QCEW.
2. **Net AGI in-migration per capita** — IRS SOI gives net dollars
   flowing in/out. Markets receiving high-income migrants see rent
   pressure faster than population growth alone predicts.
3. **Permit-to-household-formation ratio** — when permits lag
   household formation, rents compound. The single biggest
   appreciation driver in supply-constrained metros (Census BPS ÷ ACS).
4. **Rent-to-income ratio (current level)** — a ceiling indicator. If
   already >30%, future rent growth is capped by wage growth.

### Tier 2 — Meaningful predictors

5. **Employer concentration (HHI across NAICS 2-digit industries)** —
   low diversification = single-employer risk (think Detroit pre-2010).
6. **Renter share of households + trend** — high and rising = durable
   demand.
7. **School rating *trajectory*** (delta over 3-5 yrs, not absolute) —
   schools improving faster than the metro median drives family demand
   into specific zips.
8. **Days-on-market trend (Redfin)** — falling DOM with rising prices =
   demand outpacing supply.

### Tier 3 — Risk modifiers (subtract from score)

9. **Insurance premium growth rate** — FL, LA, parts of TX/CA are
   silently destroying cash flow. A 6% gross yield can become 3% in
   three years.
10. **Climate-risk composite** (FEMA + NOAA + First Street) — affects
    both insurance and exit liquidity.
11. **Population trend (5yr)** — flat or negative is a flag, but not
    necessarily fatal if wage growth is positive.

### What we are *deliberately* excluding from v1

- Sentiment/Reddit/news scrapes — noisy, hard to validate
- Per-property "deal score" — that's the v2 underwriter, not the v1
  scorecard
- ML on labeled "good deals" — no labeled dataset exists at this stage;
  start with a transparent weighted scorecard and let it earn the right
  to become a learned model

---

## 4. Proposed scoring model

A transparent weighted scorecard for v1. Every input is z-scored across
all US zips (or counties, where the source dictates), clipped to ±3, and
combined as:

```
MarketScore(zip) =
    0.25 × YieldScore         (rent/price, taxes, insurance)
  + 0.40 × DemandScore        (jobs, migration, income, demographics)
  + 0.25 × SupplyScore        (permits vs. formation, vacancy, DOM)
  - 0.10 × RiskScore          (climate, insurance trend, employer HHI)
```

Each sub-score is itself a weighted z-score combo:

```
YieldScore   = 0.50·z(grossYield) + 0.30·z(-effTaxRate) + 0.20·z(-insuranceCost)
DemandScore  = 0.30·z(wageWeightedJobCAGR)
             + 0.30·z(netAGIperCapita)
             + 0.20·z(populationCAGR)
             + 0.10·z(renterShareTrend)
             + 0.10·z(-rentToIncome)             # affordability headroom
SupplyScore  = 0.50·z(-permitToFormationRatio)   # fewer permits = better for rents
             + 0.30·z(-vacancyRate)
             + 0.20·z(-domTrend)
RiskScore    = 0.40·z(climateComposite)
             + 0.30·z(insurancePremiumCAGR)
             + 0.30·z(employerHHI)
```

Weights are starting points. The first validation step (see §6) is to
**backtest**: do high-scoring zips from 2015 actually show higher rent
growth and price appreciation through 2024 than low-scoring ones? If
not, the weights are wrong — or we're missing a feature.

Output is a ranked list of zips, but also each sub-score broken out, so
a user can filter for their strategy (e.g., "high yield, accept lower
appreciation").

---

## 5. Architecture sketch

```
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  Source adapters │ →  │  Raw landing zone│ →  │  Geo-normalized  │
│  (one per API/   │    │  (Parquet on disk│    │  fact tables     │
│   scraper)       │    │   or S3, by date)│    │  (DuckDB/Postgres)│
└──────────────────┘    └──────────────────┘    └──────────────────┘
                                                          │
                                                          ▼
                                              ┌──────────────────────┐
                                              │  Feature store       │
                                              │  (per-zip metrics,   │
                                              │   z-scores, trends)  │
                                              └──────────────────────┘
                                                          │
                                          ┌───────────────┼───────────────┐
                                          ▼                               ▼
                              ┌──────────────────────┐      ┌──────────────────────┐
                              │  Market scorecard    │      │  Backtest harness    │
                              │  (ranked zip list +  │      │  (validate weights   │
                              │   sub-scores)        │      │   on historical data)│
                              └──────────────────────┘      └──────────────────────┘
```

**Tech choices for the free/scraped path:**
- Storage: **DuckDB + Parquet** locally; trivial to migrate to Postgres or
  BigQuery later. DuckDB handles the full US zip × monthly grain comfortably.
- Orchestration: **Prefect** or plain Makefile + cron. Avoid Airflow at this
  scale.
- Scraping: **Playwright** for assessor sites that need JS;
  **httpx + selectolax** for HTML; **requests-cache** to avoid
  re-hitting sources.
- Geo: **GeoPandas** for parcel/zip/tract joins. Crosswalks from
  HUD-USPS ZIP-Tract.

**Geographic spine:** every metric lands on at least one of
`(zip5/ZCTA, county_fips, msa_cbsa)` with crosswalks. Sources that only
publish at county or MSA grain (BLS QCEW, BEA, IRS SOI) get downscaled
to zip via population-weighted apportionment — flagged as such so the
scorecard knows which features are interpolated vs. native.

---

## 6. Validation plan (before trusting any ranking)

A scorecard is worthless if it doesn't predict the future. Before
calling v1 done:

1. **Reconstruct the feature set as of Jan 2015** using only data that
   was available then (no look-ahead).
2. **Compute the MarketScore for all zips at that point.**
3. **Measure realized rent growth (ZORI) and price appreciation (ZHVI)
   from 2015 → 2024** for each zip.
4. **Bucket zips by score quintile** and compare realized returns.
5. The top quintile should clearly outperform the bottom quintile on
   total return (rent growth + appreciation). If not, iterate on
   weights and features before exposing the tool.

Stretch: walk-forward validation (2015→18, 2016→19, etc.) to catch
regime-dependent weights.

---

## 7. Risks & open questions

- **County-data fragmentation** is the single biggest engineering risk.
  Mitigation: start with the top 25 MSAs by population, where ATTOM/Zillow
  derivative data covers most needs without per-county scrapers.
- **IRS SOI migration has a ~2 year lag.** Mitigation: blend with USPS
  CoA aggregates and ACS migration where available.
- **ZORI is modeled, not transacted.** It can drift in low-density zips
  with thin data. Mitigation: report a confidence band per zip based on
  sample size; suppress scores where ZORI coverage is weak.
- **Insurance is becoming the dominant cost in coastal/wildfire markets**
  and there is no free zip-level insurance dataset. Mitigation: model
  insurance as `state_average × climate_risk_multiplier` for v1, flag
  as approximate, prioritize paid data here in v2.
- **TOS on scraping.** Zillow/Redfin published research data is fine;
  scraping their listing pages is not. We stay on the published-data
  side of the line.

---

## 8. What to build first (if/when we move past discovery)

A four-week v1 that proves the concept end-to-end before scaling sources:

| Week | Deliverable |
|---|---|
| 1 | Geo spine + ingestion for ZHVI, ZORI, BLS QCEW, Census ACS, BPS, IRS SOI. Land in DuckDB. |
| 2 | Feature engineering: yield, wage-weighted jobs, permits/formation, migration, affordability. Z-scores. |
| 3 | Composite MarketScore + zip-level ranked output (CSV + simple HTML table). |
| 4 | Backtest harness (§6). Iterate weights until the top quintile beats the bottom on 2015→2024 data. |

Everything past that — distress signals, school deltas, climate risk
modifiers, deal-level underwriter, web UI — is v2+, prioritized by what
the backtest reveals as undermodeled.

---

## 9. Decision checkpoint

Before any code:
- Do the indicator weights in §4 match your priors, or do you want to
  reweight (e.g., heavier on yield, lighter on appreciation)?
- Top-25 MSAs first, or full US zip coverage from day one? (Top-25 is
  ~3× faster to build, captures ~55% of US households.)
- Is the 4-week v1 in §8 the right scope, or do you want a smaller
  proof first (e.g., just the yield half, no demand-side scoring)?
