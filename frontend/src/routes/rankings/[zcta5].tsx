import { Link, useParams } from "react-router-dom";
import { useRedfin, useZhvi, useZip, useZori } from "../../hooks/useZip";
import { Card } from "../../components/Card";
import { Chip } from "../../components/Chip";
import { SubScoreRadar } from "../../charts/SubScoreRadar";
import { ZhviLine } from "../../charts/ZhviLine";
import { ZoriLine } from "../../charts/ZoriLine";
import { RedfinTrio } from "../../charts/RedfinTrio";
import { formatNumber, scoreBgClass, scoreColorClass } from "../../lib/format";
import type { CardEntries, FeatureEntry, FilterStatusEntry } from "../../api/types";
import { cx } from "../../lib/cx";

const SUB_SCORE_KEYS = [
  "yield_score",
  "demand_score",
  "supply_score",
  "operability_score",
  "risk_score",
];

export default function ZipDetail() {
  const { zcta5 } = useParams<{ zcta5: string }>();
  const zip = useZip(zcta5);
  const zhvi = useZhvi(zcta5);
  const zori = useZori(zcta5);
  const redfin = useRedfin(zcta5);

  if (!zcta5) {
    return <div className="text-fg-muted">Missing zcta5.</div>;
  }

  if (zip.isLoading) {
    return <div className="text-fg-muted">Loading zip {zcta5}…</div>;
  }
  if (zip.isError) {
    return (
      <div className="space-y-2">
        <p className="text-danger">Failed to load zip {zcta5}.</p>
        <Link to="/rankings" className="text-accent underline">
          ← Back to rankings
        </Link>
      </div>
    );
  }
  const data = zip.data;
  const subScores = (data?.sub_scores ?? {}) as Record<string, number | null>;
  return (
    <div className="space-y-4" data-testid="zip-detail-root">
      <header
        className="flex flex-wrap items-end justify-between gap-2"
        data-testid="zip-detail-identity"
      >
        <div className="space-y-1">
          <Link to="/rankings" className="text-xs text-accent underline">
            ← All rankings
          </Link>
          <h1 className="text-3xl font-bold font-mono">{zcta5}</h1>
          <div className="flex flex-wrap items-center gap-2 text-sm text-fg-muted">
            {data?.state ? <Chip tone="accent">{data.state}</Chip> : null}
            {data?.metro ? <span>{data.metro}</span> : null}
            {data?.county_name ? <span>· {data.county_name}</span> : null}
          </div>
        </div>
        <div className={cx("rounded-xl px-4 py-2 text-center", scoreBgClass(data?.market_score ?? null))}>
          <div className="text-xs uppercase text-fg-muted">MarketScore</div>
          <div className={cx("text-3xl font-bold", scoreColorClass(data?.market_score ?? null))}>
            {formatNumber(data?.market_score ?? null, { decimals: 1 })}
          </div>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="mb-2 text-lg font-semibold">Score breakdown</h2>
          <div data-testid="zip-detail-radar">
            <SubScoreRadar
              series={[
                { name: zcta5, scores: data?.sub_scores ?? null },
              ]}
            />
          </div>
          <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 text-sm sm:grid-cols-3">
            {SUB_SCORE_KEYS.map((key) => (
              <div
                key={key}
                data-testid={`zip-detail-score-${key}`}
                className="flex items-baseline justify-between gap-2"
              >
                <dt className="text-fg-subtle text-xs uppercase">{key.replace(/_score$/, "")}</dt>
                <dd className="font-mono tabular-nums">
                  {formatNumber(subScores[key] ?? null, { decimals: 1 })}
                </dd>
              </div>
            ))}
          </dl>
        </Card>
        <Card data-testid="zip-detail-filter-status">
          <h2 className="mb-2 text-lg font-semibold">Filter status</h2>
          <FilterStatusGrid items={data?.filter_status ?? []} />
        </Card>
      </div>

      <Card>
        <h2 className="mb-2 text-lg font-semibold">Features</h2>
        <FeatureTable
          features={(Array.isArray(data?.features) ? data!.features : []) as FeatureEntry[]}
        />
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card data-testid="zip-detail-chart-zhvi">
          <h2 className="mb-2 text-lg font-semibold">ZHVI (home value index)</h2>
          {zhvi.isLoading ? (
            <p className="text-sm text-fg-muted">Loading…</p>
          ) : (
            <ZhviLine series={[{ name: "ZHVI", data: zhvi.data?.series }]} />
          )}
        </Card>
        <Card data-testid="zip-detail-chart-zori">
          <h2 className="mb-2 text-lg font-semibold">ZORI (rent index)</h2>
          {zori.isLoading ? (
            <p className="text-sm text-fg-muted">Loading…</p>
          ) : (
            <ZoriLine series={[{ name: "ZORI", data: zori.data?.series }]} />
          )}
        </Card>
      </div>

      <Card data-testid="zip-detail-chart-redfin">
        <h2 className="mb-2 text-lg font-semibold">Redfin market activity</h2>
        <RedfinTrio data={redfin.data} />
      </Card>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <DetailCard title="Tax" entries={data?.tax} />
        <DetailCard title="Insurance" entries={data?.insurance} />
        <DetailCard title="Eviction" entries={data?.eviction} />
        <DetailCard title="Climate" entries={data?.climate} />
      </div>
    </div>
  );
}

function FilterStatusGrid({ items }: { items: FilterStatusEntry[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-fg-muted">No filters configured.</p>;
  }
  return (
    <ul className="flex flex-wrap gap-2">
      {items.map((f) => (
        <li key={f.name}>
          <Chip tone={f.passes ? "success" : "danger"}>
            {f.passes ? "✓" : "✗"} {f.name}
            {typeof f.value === "number" ? (
              <span className="ml-1 text-[10px] opacity-80">
                {formatNumber(f.value, { decimals: 2 })}
              </span>
            ) : null}
          </Chip>
        </li>
      ))}
    </ul>
  );
}

function FeatureTable({ features }: { features: FeatureEntry[] }) {
  if (features.length === 0) {
    return <p className="text-sm text-fg-muted">No features available.</p>;
  }
  return (
    <div className="overflow-x-auto" data-testid="zip-detail-features-table">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="text-left text-xs uppercase tracking-wide text-fg-subtle">
            <th className="px-2 py-1">Feature</th>
            <th className="px-2 py-1">Raw</th>
            <th className="px-2 py-1">z-score</th>
            <th className="px-2 py-1">Sign</th>
            <th className="px-2 py-1">Contribution</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-bg-panel">
          {features.map((f) => (
            <tr key={f.name}>
              <td className="px-2 py-1 font-mono text-xs">{f.name}</td>
              <td className="px-2 py-1">{formatNumber(f.raw, { decimals: 3 })}</td>
              <td className="px-2 py-1">{formatNumber(f.z, { decimals: 3 })}</td>
              <td className="px-2 py-1">
                {f.sign === "+" ? (
                  <Chip tone="success">+</Chip>
                ) : f.sign === "-" ? (
                  <Chip tone="danger">−</Chip>
                ) : (
                  <Chip>0</Chip>
                )}
              </td>
              <td className="px-2 py-1">{formatNumber(f.contribution, { decimals: 3 })}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DetailCard({ title, entries }: { title: string; entries: CardEntries | undefined }) {
  return (
    <Card>
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-fg-muted">{title}</h3>
      {entries && Object.keys(entries).length > 0 ? (
        <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 text-sm">
          {Object.entries(entries).map(([k, v]) => (
            <div className="contents" key={k}>
              <dt className="text-fg-subtle">{k}</dt>
              <dd className="text-fg">
                {v === null || v === undefined
                  ? "—"
                  : typeof v === "number"
                    ? formatNumber(v, { decimals: 2 })
                    : String(v)}
              </dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="text-sm text-fg-subtle">No data.</p>
      )}
    </Card>
  );
}
