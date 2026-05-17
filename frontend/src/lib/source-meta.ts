// Static metadata for every source, derived from the docstrings of the
// Python modules in src/rental/sources/. The API exposes some of this on
// the SourceSummary (source_url, license, cadence) but not all sources
// populate every field; we keep a baseline here so the UI always has
// real metadata to render, falling back to API values when richer.
//
// Whenever a source module's docstring is updated in src/rental/sources/,
// re-sync this map. The unit test in tests/unit/source-meta.test.ts
// enforces that every entry has the required fields.

export interface SourceMeta {
  /** Human-friendly name shown in the UI. */
  display_name: string;
  /** One-line description (subject + value). */
  description: string;
  /** Free-form license string (e.g. "Public domain (U.S. Census)"). */
  license: string;
  /** Free-form refresh cadence (e.g. "Monthly"). */
  cadence: string;
  /** Canonical landing/download URL for the upstream dataset. */
  source_url: string;
  /** True if outbound fetch is blocked in CI; UI should hint at fixture mode. */
  fixture_only_in_ci?: boolean;
}

// Keys are the canonical `source.name` values used by the CLI and API.
export const SOURCE_META: Record<string, SourceMeta> = {
  zillow_zhvi: {
    display_name: "Zillow ZHVI",
    description:
      "Zillow Home Value Index, all-homes, smoothed + seasonally adjusted, by ZIP.",
    license: "Free for non-commercial research (Zillow Research)",
    cadence: "Monthly",
    source_url:
      "https://files.zillowstatic.com/research/public_csvs/zhvi/Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv",
  },
  zillow_zori: {
    display_name: "Zillow ZORI",
    description:
      "Zillow Observed Rent Index, SFR + condo + multifamily, smoothed, by ZIP.",
    license: "Free for non-commercial research (Zillow Research)",
    cadence: "Monthly",
    source_url:
      "https://files.zillowstatic.com/research/public_csvs/zori/Zip_zori_uc_sfrcondomfr_sm_month.csv",
  },
  redfin_market: {
    display_name: "Redfin Data Center",
    description:
      "Weekly/monthly market tracker: DOM, sale-to-list, inventory, by ZIP.",
    license: "Free for personal / non-commercial research (attribution required)",
    cadence: "Weekly",
    source_url: "https://www.redfin.com/news/data-center/",
    fixture_only_in_ci: true,
  },
  acs_demographics: {
    display_name: "ACS Demographics",
    description:
      "5-year ACS population, median household income, and median age by ZCTA.",
    license: "U.S. Government work, public domain",
    cadence: "Annual (December release)",
    source_url: "https://api.census.gov/data/2022/acs/acs5",
    fixture_only_in_ci: true,
  },
  acs_housing_stock: {
    display_name: "ACS Housing Stock",
    description: "B25001 total housing units, county grain.",
    license: "U.S. Census Bureau, public domain (Title 13)",
    cadence: "Annual (December release)",
    source_url:
      "https://api.census.gov/data/2022/acs/acs5?get=NAME,B25001_001E&for=county:*&in=state:*",
    fixture_only_in_ci: true,
  },
  bls_qcew: {
    display_name: "BLS QCEW",
    description:
      "Quarterly Census of Employment and Wages, county-grain annual rollups.",
    license: "U.S. Government work, public domain",
    cadence: "Annual (single-file zip, ~May lag)",
    source_url: "https://data.bls.gov/cew/data/files/",
    fixture_only_in_ci: true,
  },
  census_bps: {
    display_name: "Census BPS",
    description: "Building Permits Survey, county-grain new residential permits.",
    license: "U.S. Census Bureau, public domain",
    cadence: "Monthly (~1mo lag); annual CSVs each spring",
    source_url: "https://www2.census.gov/econ/bps/County/",
    fixture_only_in_ci: true,
  },
  census_geo: {
    display_name: "Census Geographic Spine",
    description:
      "ZCTA gazetteer, ZCTA-to-county crosswalk, and CBSA delineation.",
    license: "U.S. Census Bureau, public domain",
    cadence: "Annual",
    source_url:
      "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/",
    fixture_only_in_ci: true,
  },
  county_tax_rate: {
    display_name: "County Effective Tax Rate",
    description:
      "Effective property-tax rate (B25103 / B25077) per county, derived from ACS.",
    license: "U.S. Census Bureau, public domain",
    cadence: "Annual (ACS 5-year vintage)",
    source_url:
      "https://api.census.gov/data/2022/acs/acs5?get=B25103_001E,B25077_001E&for=county:*",
    fixture_only_in_ci: true,
  },
  eviction_lab: {
    display_name: "Eviction Lab",
    description: "County-level eviction filings + filing rates.",
    license: "Eviction Lab Open Data License (research / non-commercial)",
    cadence: "Annual (multi-year lag)",
    source_url: "https://data-downloads.evictionlab.org/",
    fixture_only_in_ci: true,
  },
  fema_nri: {
    display_name: "FEMA National Risk Index",
    description:
      "County-level natural hazard risk: flood, wildfire, hurricane, heatwave.",
    license: "Public domain (attribution requested)",
    cadence: "Annual major releases",
    source_url:
      "https://hazards.fema.gov/nri/Content/StaticDocuments/DataDownload/NRI_Table_Counties.csv",
    fixture_only_in_ci: true,
  },
  irs_migration: {
    display_name: "IRS SOI Migration",
    description: "County-to-county migration counts (filers, exemptions, AGI).",
    license: "U.S. Government work, public domain",
    cadence: "Annual (~24mo lag)",
    source_url: "https://www.irs.gov/statistics/soi-tax-stats-migration-data",
    fixture_only_in_ci: true,
  },
};

/** Lookup with fallback for unknown sources. */
export function getSourceMeta(name: string): SourceMeta {
  return (
    SOURCE_META[name] ?? {
      display_name: name,
      description: "(no metadata)",
      license: "unknown",
      cadence: "unknown",
      source_url: "",
    }
  );
}

/**
 * Merge meta with an API SourceSummary (when fields are present, the API
 * value wins because it's the live truth).
 */
export function mergeSourceMeta(
  name: string,
  apiFields: Partial<Pick<SourceMeta, "license" | "cadence" | "source_url">>,
): SourceMeta {
  const base = getSourceMeta(name);
  return {
    ...base,
    license: apiFields.license || base.license,
    cadence: apiFields.cadence || base.cadence,
    source_url: apiFields.source_url || base.source_url,
  };
}

/** Format a refresh age in seconds as a human-readable string. */
export function formatAge(ageSeconds: number | null | undefined): string {
  if (ageSeconds === null || ageSeconds === undefined) return "never";
  if (ageSeconds < 0) return "just now";
  const minute = 60;
  const hour = 60 * minute;
  const day = 24 * hour;
  if (ageSeconds < minute) return `${Math.floor(ageSeconds)}s ago`;
  if (ageSeconds < hour) return `${Math.floor(ageSeconds / minute)}m ago`;
  if (ageSeconds < day) return `${Math.floor(ageSeconds / hour)}h ago`;
  return `${Math.floor(ageSeconds / day)}d ago`;
}

/** Format an ISO timestamp; falls back to "never" when null. */
export function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return "never";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString();
  } catch {
    return iso;
  }
}

/** Format a number with thousands separators; null → em-dash. */
export function formatCount(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString();
}

/** Tailwind class for a status badge. */
export function statusColor(status: string | null | undefined): string {
  switch (status) {
    case "ok":
      return "bg-emerald-500/20 text-emerald-300 border-emerald-500/40";
    case "stale":
      return "bg-amber-500/20 text-amber-300 border-amber-500/40";
    case "error":
      return "bg-rose-500/20 text-rose-300 border-rose-500/40";
    case "never":
    default:
      return "bg-slate-500/20 text-slate-300 border-slate-500/40";
  }
}

export const KNOWN_SOURCE_NAMES = Object.keys(SOURCE_META);
