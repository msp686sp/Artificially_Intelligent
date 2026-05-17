import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Card } from "../../components/Card";
import { Chip } from "../../components/Chip";
import { Button } from "../../components/Button";
import { SubScoreRadar } from "../../charts/SubScoreRadar";
import { ZhviLine } from "../../charts/ZhviLine";
import { ZoriLine } from "../../charts/ZoriLine";
import {
  parseCompareZips,
  serializeCompareZips,
  useCompare,
} from "../../hooks/useCompare";
import { formatNumber, scoreColorClass } from "../../lib/format";
import { cx } from "../../lib/cx";

const SERIES_COLORS = ["#5b8def", "#3aaf85", "#d9a441", "#e15c5c", "#c084fc", "#22d3ee", "#f472b6"];

const FEATURE_ROWS: Array<{ key: string; label: string; higherIsBetter: boolean }> = [
  { key: "market_score", label: "MarketScore", higherIsBetter: true },
  { key: "yield_score", label: "Yield score", higherIsBetter: true },
  { key: "growth_score", label: "Growth score", higherIsBetter: true },
  { key: "stability_score", label: "Stability score", higherIsBetter: true },
  { key: "affordability_score", label: "Affordability score", higherIsBetter: true },
  { key: "risk_score", label: "Risk score", higherIsBetter: false },
  { key: "median_home_value", label: "Median home value", higherIsBetter: false },
  { key: "median_rent", label: "Median rent", higherIsBetter: true },
  { key: "gross_yield_monthly_pct", label: "Gross yield (monthly %)", higherIsBetter: true },
];

export default function CompareIndex() {
  const [search, setSearch] = useSearchParams();
  const zcta5s = useMemo(() => parseCompareZips(search.get("z")), [search]);
  const [newZip, setNewZip] = useState("");

  const compare = useCompare(zcta5s);

  function updateZips(next: string[]) {
    const sp = new URLSearchParams(search);
    if (next.length === 0) sp.delete("z");
    else sp.set("z", serializeCompareZips(next));
    setSearch(sp, { replace: true });
  }

  function addZip() {
    const trimmed = newZip.trim();
    if (!/^\d{5}$/.test(trimmed)) return;
    if (zcta5s.includes(trimmed)) return;
    updateZips([...zcta5s, trimmed]);
    setNewZip("");
  }

  function removeZip(z: string) {
    updateZips(zcta5s.filter((x) => x !== z));
  }

  if (zcta5s.length === 0) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Compare zips</h1>
        <Card>
          <p className="text-sm text-fg-muted">
            Add zips to compare by URL <code className="font-mono">?z=10025,46220</code> or via the
            input below.
          </p>
          <AddZipInput value={newZip} onChange={setNewZip} onAdd={addZip} />
        </Card>
      </div>
    );
  }

  const radarSeries = compare.details.map((d, i) => ({
    name: d.zcta5,
    scores: d.data?.sub_scores ?? null,
    color: SERIES_COLORS[i % SERIES_COLORS.length],
  }));
  const zhviSeries = compare.zhvi.map((s, i) => ({
    name: s.zcta5,
    data: s.data?.series,
    color: SERIES_COLORS[i % SERIES_COLORS.length],
  }));
  const zoriSeries = compare.zori.map((s, i) => ({
    name: s.zcta5,
    data: s.data?.series,
    color: SERIES_COLORS[i % SERIES_COLORS.length],
  }));

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold">
          Compare {zcta5s.length} zip{zcta5s.length === 1 ? "" : "s"}
        </h1>
        <div className="flex flex-wrap items-center gap-2">
          {zcta5s.map((z, i) => (
            <Chip key={z} tone="accent" className="gap-2">
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ background: SERIES_COLORS[i % SERIES_COLORS.length] }}
                aria-hidden
              />
              <span className="font-mono">{z}</span>
              <button
                type="button"
                onClick={() => removeZip(z)}
                aria-label={`Remove ${z}`}
                className="ml-1 text-xs text-fg-subtle hover:text-fg"
              >
                ✕
              </button>
            </Chip>
          ))}
        </div>
      </header>

      <Card>
        <AddZipInput value={newZip} onChange={setNewZip} onAdd={addZip} />
      </Card>

      <Card>
        <h2 className="mb-2 text-lg font-semibold">Sub-score overlay</h2>
        <SubScoreRadar series={radarSeries} height={320} />
      </Card>

      {/* Numeric grid (desktop) + accordion (mobile) */}
      <div className="hidden md:block">
        <Card padded={false}>
          <FeatureGrid zips={compare} />
        </Card>
      </div>
      <div className="block md:hidden">
        <MobileAccordion compare={compare} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="mb-2 text-lg font-semibold">ZHVI overlay</h2>
          <ZhviLine series={zhviSeries} />
        </Card>
        <Card>
          <h2 className="mb-2 text-lg font-semibold">ZORI overlay</h2>
          <ZoriLine series={zoriSeries} />
        </Card>
      </div>
    </div>
  );
}

function AddZipInput({
  value,
  onChange,
  onAdd,
}: {
  value: string;
  onChange: (v: string) => void;
  onAdd: () => void;
}) {
  return (
    <div className="flex flex-wrap items-end gap-2">
      <label className="block flex-1">
        <span className="mb-1 block text-sm text-fg-muted">Add zip</span>
        <input
          type="text"
          inputMode="numeric"
          maxLength={5}
          value={value}
          onChange={(e) => onChange(e.target.value.replace(/\D/g, ""))}
          onKeyDown={(e) => {
            if (e.key === "Enter") onAdd();
          }}
          placeholder="10025"
          className="touch-target w-full rounded-md border border-bg-panel bg-bg-subtle px-3 py-2 font-mono"
        />
      </label>
      <Button size="md" onClick={onAdd} disabled={!/^\d{5}$/.test(value)}>
        Add
      </Button>
    </div>
  );
}

function FeatureGrid({ zips }: { zips: ReturnType<typeof useCompare> }) {
  // For each row, determine the "best in row" value (numeric only).
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead className="bg-bg-subtle">
          <tr>
            <th className="px-3 py-2 text-left text-xs uppercase text-fg-subtle">Feature</th>
            {zips.zcta5s.map((z, i) => (
              <th key={z} className="px-3 py-2 text-left text-xs uppercase">
                <span className="inline-flex items-center gap-1">
                  <span
                    className="inline-block h-2 w-2 rounded-full"
                    style={{ background: SERIES_COLORS[i % SERIES_COLORS.length] }}
                  />
                  <span className="font-mono">{z}</span>
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-bg-panel">
          {FEATURE_ROWS.map((row) => {
            const values = zips.details.map((d) => {
              const v = (d.data as Record<string, unknown> | undefined)?.[row.key];
              return typeof v === "number" ? v : null;
            });
            const numericValues = values.filter((v): v is number => v !== null);
            const best = numericValues.length
              ? row.higherIsBetter
                ? Math.max(...numericValues)
                : Math.min(...numericValues)
              : null;
            return (
              <tr key={row.key}>
                <td className="px-3 py-1.5 font-mono text-xs">{row.label}</td>
                {values.map((v, i) => (
                  <td
                    key={i}
                    className={cx(
                      "px-3 py-1.5",
                      best !== null && v === best && "bg-success/15 text-success font-semibold",
                      row.key === "market_score" && scoreColorClass(v),
                    )}
                  >
                    {formatNumber(v, { decimals: row.key.endsWith("_pct") ? 2 : 1 })}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function MobileAccordion({ compare }: { compare: ReturnType<typeof useCompare> }) {
  return (
    <div className="flex flex-col gap-2">
      {compare.details.map((d, idx) => (
        <details
          key={d.zcta5}
          open={idx === 0}
          className="rounded-lg border border-bg-panel bg-bg-subtle"
        >
          <summary className="touch-target cursor-pointer list-none px-3 py-2">
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-2">
                <span
                  className="inline-block h-2 w-2 rounded-full"
                  style={{ background: SERIES_COLORS[idx % SERIES_COLORS.length] }}
                />
                <span className="font-mono font-semibold">{d.zcta5}</span>
              </span>
              <span className={cx("font-semibold", scoreColorClass(d.data?.market_score ?? null))}>
                {formatNumber(d.data?.market_score ?? null, { decimals: 1 })}
              </span>
            </div>
          </summary>
          <div className="border-t border-bg-panel p-3">
            <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 text-sm">
              {FEATURE_ROWS.map((row) => {
                const v = (d.data as Record<string, unknown> | undefined)?.[row.key];
                const num = typeof v === "number" ? v : null;
                return (
                  <div key={row.key} className="contents">
                    <dt className="text-fg-subtle">{row.label}</dt>
                    <dd>{formatNumber(num, { decimals: row.key.endsWith("_pct") ? 2 : 1 })}</dd>
                  </div>
                );
              })}
            </dl>
          </div>
        </details>
      ))}
    </div>
  );
}
