import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  createColumnHelper,
  getCoreRowModel,
  useReactTable,
  type RowSelectionState,
  type SortingState,
  type VisibilityState,
} from "@tanstack/react-table";
import { useRankings } from "../../hooks/useRankings";
import type { RankingRow, SortOrder } from "../../api/types";
import { Card } from "../../components/Card";
import { Button } from "../../components/Button";
import { Chip } from "../../components/Chip";
import { DataTable } from "../../components/DataTable";
import { ScoreHistogram } from "../../charts/ScoreHistogram";
import { formatNumber, scoreColorClass } from "../../lib/format";
import { cx } from "../../lib/cx";

const PAGE_SIZE = 50;

const helper = createColumnHelper<RankingRow>();

export default function RankingsIndex() {
  const [search, setSearch] = useSearchParams();
  const navigate = useNavigate();

  const [stateFilter, setStateFilter] = useState(search.get("state") ?? "");
  const [metroFilter, setMetroFilter] = useState(search.get("metro") ?? "");
  const [minScore, setMinScore] = useState<number>(parseFloatOrDefault(search.get("min_score"), 0));
  const [maxScore, setMaxScore] = useState<number>(parseFloatOrDefault(search.get("max_score"), 100));
  const [sorting, setSorting] = useState<SortingState>(parseSorting(search.get("sort"), search.get("order")));
  const [page, setPage] = useState<number>(parseIntOrDefault(search.get("page"), 0));
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({});
  const [density, setDensity] = useState<"compact" | "comfortable">("comfortable");
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});

  const sortKey = sorting[0]?.id ?? "market_score";
  const sortOrder: SortOrder = sorting[0]?.desc === false ? "asc" : "desc";

  const query = useRankings({
    state: stateFilter || undefined,
    metro: metroFilter || undefined,
    minScore: minScore > 0 ? minScore : undefined,
    maxScore: maxScore < 100 ? maxScore : undefined,
    sort: sortKey,
    order: sortOrder,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  });

  // Mirror filter state into the URL so deep-links are shareable.
  function syncUrl(next: Record<string, string | number | undefined>) {
    const sp = new URLSearchParams(search);
    for (const [k, v] of Object.entries(next)) {
      if (v === undefined || v === "" || v === null) sp.delete(k);
      else sp.set(k, String(v));
    }
    setSearch(sp, { replace: true });
  }

  const columns = useMemo(
    () => [
      helper.display({
        id: "select",
        enableSorting: false,
        size: 32,
        header: ({ table }) => (
          <input
            type="checkbox"
            aria-label="Select all"
            className="h-4 w-4"
            checked={table.getIsAllRowsSelected()}
            onChange={table.getToggleAllRowsSelectedHandler()}
          />
        ),
        cell: ({ row }) => (
          <input
            type="checkbox"
            aria-label={`Select ${row.original.zcta5}`}
            className="h-4 w-4"
            checked={row.getIsSelected()}
            onClick={(e) => e.stopPropagation()}
            onChange={row.getToggleSelectedHandler()}
          />
        ),
      }),
      helper.accessor("zcta5", {
        header: "ZIP",
        cell: (info) => (
          <span className="font-mono font-semibold text-accent">{info.getValue()}</span>
        ),
      }),
      helper.accessor("state", { header: "State", cell: (info) => info.getValue() ?? "—" }),
      helper.accessor("metro", { header: "Metro", cell: (info) => info.getValue() ?? "—" }),
      helper.accessor("market_score", {
        header: "MarketScore",
        cell: (info) => (
          <span className={cx("font-semibold", scoreColorClass(info.getValue()))}>
            {formatNumber(info.getValue(), { decimals: 1 })}
          </span>
        ),
      }),
      helper.accessor("yield_score", {
        header: "Yield",
        cell: (info) => formatNumber(info.getValue(), { decimals: 1 }),
      }),
      helper.accessor("growth_score", {
        header: "Growth",
        cell: (info) => formatNumber(info.getValue(), { decimals: 1 }),
      }),
      helper.accessor("stability_score", {
        header: "Stability",
        cell: (info) => formatNumber(info.getValue(), { decimals: 1 }),
      }),
      helper.accessor("affordability_score", {
        header: "Afford.",
        cell: (info) => formatNumber(info.getValue(), { decimals: 1 }),
      }),
      helper.accessor("risk_score", {
        header: "Risk",
        cell: (info) => formatNumber(info.getValue(), { decimals: 1 }),
      }),
      helper.accessor("gross_yield_monthly_pct", {
        header: "Yield %",
        cell: (info) => formatNumber(info.getValue(), { decimals: 2, suffix: "%" }),
      }),
    ],
    [],
  );

  const data = query.data?.rows ?? [];
  const total = query.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const table = useReactTable<RankingRow>({
    data,
    columns,
    state: { sorting, columnVisibility, rowSelection },
    onSortingChange: (updater) => {
      const next = typeof updater === "function" ? updater(sorting) : updater;
      setSorting(next);
      const first = next[0];
      syncUrl({ sort: first?.id, order: first?.desc === false ? "asc" : "desc", page: 0 });
      setPage(0);
    },
    onColumnVisibilityChange: setColumnVisibility,
    onRowSelectionChange: setRowSelection,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
    manualPagination: true,
    enableRowSelection: true,
    pageCount,
    getRowId: (r) => r.zcta5,
  });

  const selectedZips = Object.keys(rowSelection).filter((k) => rowSelection[k]);

  function goToCompare() {
    if (selectedZips.length < 2) return;
    navigate(`/compare?z=${selectedZips.join(",")}`);
  }

  function exportCsv() {
    const visibleCols = table.getVisibleLeafColumns().filter((c) => c.id !== "select");
    const header = visibleCols.map((c) => (typeof c.columnDef.header === "string" ? c.columnDef.header : c.id));
    const lines = [header.join(",")];
    for (const r of data) {
      lines.push(
        visibleCols
          .map((c) => {
            const v = (r as Record<string, unknown>)[c.id];
            if (v === null || v === undefined) return "";
            const s = typeof v === "string" && (v.includes(",") || v.includes('"')) ? `"${v.replace(/"/g, '""')}"` : String(v);
            return s;
          })
          .join(","),
      );
    }
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `rankings-page-${page + 1}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">MarketScore rankings</h1>
          <p className="text-sm text-fg-muted">{total.toLocaleString()} zips total</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="primary"
            size="sm"
            onClick={goToCompare}
            disabled={selectedZips.length < 2}
            data-testid="compare-selected"
          >
            Compare selected ({selectedZips.length})
          </Button>
          <Button variant="secondary" size="sm" onClick={exportCsv}>
            Export CSV
          </Button>
        </div>
      </header>

      <Card>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className="block text-sm">
            <span className="mb-1 block text-fg-muted">State</span>
            <input
              type="text"
              maxLength={2}
              placeholder="e.g. NY"
              value={stateFilter}
              onChange={(e) => {
                setStateFilter(e.target.value.toUpperCase());
                setPage(0);
                syncUrl({ state: e.target.value.toUpperCase() || undefined, page: 0 });
              }}
              className="touch-target w-full rounded-md border border-bg-panel bg-bg-subtle px-3 py-2 font-mono uppercase"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-fg-muted">Metro</span>
            <input
              type="search"
              placeholder="Search metro"
              value={metroFilter}
              onChange={(e) => {
                setMetroFilter(e.target.value);
                setPage(0);
                syncUrl({ metro: e.target.value || undefined, page: 0 });
              }}
              className="touch-target w-full rounded-md border border-bg-panel bg-bg-subtle px-3 py-2"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-fg-muted">Min score: {minScore.toFixed(0)}</span>
            <input
              type="range"
              min={0}
              max={100}
              value={minScore}
              onChange={(e) => {
                const v = Number(e.target.value);
                setMinScore(v);
                syncUrl({ min_score: v || undefined, page: 0 });
              }}
              className="w-full"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-fg-muted">Max score: {maxScore.toFixed(0)}</span>
            <input
              type="range"
              min={0}
              max={100}
              value={maxScore}
              onChange={(e) => {
                const v = Number(e.target.value);
                setMaxScore(v);
                syncUrl({ max_score: v < 100 ? v : undefined, page: 0 });
              }}
              className="w-full"
            />
          </label>
        </div>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-fg-subtle">Columns:</span>
            {table.getAllLeafColumns().filter((c) => c.id !== "select").map((c) => (
              <label key={c.id} className="inline-flex items-center gap-1">
                <input
                  type="checkbox"
                  className="h-3 w-3"
                  checked={c.getIsVisible()}
                  onChange={c.getToggleVisibilityHandler()}
                />
                <span>{typeof c.columnDef.header === "string" ? c.columnDef.header : c.id}</span>
              </label>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-fg-subtle">Density:</span>
            <Button
              size="sm"
              variant={density === "comfortable" ? "primary" : "ghost"}
              onClick={() => setDensity("comfortable")}
            >
              Comfortable
            </Button>
            <Button
              size="sm"
              variant={density === "compact" ? "primary" : "ghost"}
              onClick={() => setDensity("compact")}
            >
              Compact
            </Button>
          </div>
        </div>
      </Card>

      {data.length > 0 ? (
        <Card padded={false}>
          <DataTable
            table={table}
            density={density}
            onRowClick={(r) => navigate(`/rankings/${r.zcta5}`)}
          />
        </Card>
      ) : query.isLoading ? (
        <Card>
          <p className="text-sm text-fg-muted">Loading…</p>
        </Card>
      ) : query.isError ? (
        <Card>
          <p className="text-sm text-danger">Failed to load rankings.</p>
        </Card>
      ) : (
        <Card>
          <p className="text-sm text-fg-muted">No rows match.</p>
        </Card>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="secondary"
            disabled={page === 0}
            onClick={() => {
              const p = Math.max(0, page - 1);
              setPage(p);
              syncUrl({ page: p });
            }}
          >
            Previous
          </Button>
          <Button
            size="sm"
            variant="secondary"
            disabled={(page + 1) * PAGE_SIZE >= total}
            onClick={() => {
              const p = page + 1;
              setPage(p);
              syncUrl({ page: p });
            }}
          >
            Next
          </Button>
          <Chip tone="neutral">
            Page {page + 1} / {pageCount}
          </Chip>
        </div>
        <div className="hidden xl:block w-72">
          <Card>
            <h3 className="mb-2 text-xs font-semibold uppercase text-fg-subtle">Score distribution (this page)</h3>
            <ScoreHistogram
              values={data
                .map((r) => r.market_score)
                .filter((v): v is number => typeof v === "number")}
            />
          </Card>
        </div>
      </div>
    </div>
  );
}

function parseFloatOrDefault(v: string | null | undefined, def: number): number {
  if (v === null || v === undefined) return def;
  const n = parseFloat(v);
  return Number.isFinite(n) ? n : def;
}

function parseIntOrDefault(v: string | null | undefined, def: number): number {
  if (v === null || v === undefined) return def;
  const n = parseInt(v, 10);
  return Number.isFinite(n) ? n : def;
}

function parseSorting(sort: string | null, order: string | null): SortingState {
  if (!sort) return [{ id: "market_score", desc: true }];
  return [{ id: sort, desc: order !== "asc" }];
}
