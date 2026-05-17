import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import type { ColumnDef } from "@tanstack/react-table";
import { Button, Card, Pill, Spinner } from "@/components/ui";
import { DataTable } from "@/components/DataTable";
import {
  useBacktestRuns,
  useStartBacktestRun,
  useStartBacktestTune,
} from "@/hooks/useBacktestRuns";
import type {
  BacktestRunSummary,
  JobEvent,
  RunRequest,
  TuneRequest,
} from "@/api/types";
import { cn } from "@/lib/cn";

const STATUS_TONES: Record<BacktestRunSummary["status"], "success" | "warning" | "danger" | "default" | "accent"> = {
  succeeded: "success",
  ready: "success",
  running: "accent",
  queued: "warning",
  not_ready: "warning",
  failed: "danger",
};

function formatDuration(seconds?: number | null): string {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m${s.toString().padStart(2, "0")}s`;
}

function NewRunCard({ activeJobId }: { activeJobId: string | null }) {
  const mutation = useStartBacktestRun();
  const { register, handleSubmit, formState } = useForm<RunRequest>({
    defaultValues: { start_year: 2013, end_year: 2019 },
  });
  return (
    <Card>
      <h2 className="text-lg font-semibold">New run</h2>
      <p className="mt-1 text-xs text-fg-muted">
        Range-of-years rolling backtest.
      </p>
      <form
        className="mt-3 flex flex-wrap items-end gap-3"
        onSubmit={handleSubmit((data) => mutation.mutate(data))}
      >
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-fg-muted">Start year</span>
          <input
            type="number"
            min={1996}
            max={2099}
            {...register("start_year", { valueAsNumber: true, required: true })}
            className="w-28 rounded-md border border-bg-subtle bg-bg-subtle px-3 py-2 text-sm"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-fg-muted">End year</span>
          <input
            type="number"
            min={1996}
            max={2099}
            {...register("end_year", { valueAsNumber: true, required: true })}
            className="w-28 rounded-md border border-bg-subtle bg-bg-subtle px-3 py-2 text-sm"
          />
        </label>
        <Button
          type="submit"
          variant="primary"
          disabled={mutation.isPending || !formState.isValid}
        >
          {mutation.isPending ? <Spinner /> : null} Run
        </Button>
      </form>
      {mutation.error && (
        <div className="mt-2 text-xs text-danger">
          {(mutation.error as Error).message}
        </div>
      )}
      {activeJobId && (
        <div className="mt-2 text-xs text-fg-muted">
          Job <code>{activeJobId}</code> running…
        </div>
      )}
    </Card>
  );
}

function NewTuneCard() {
  const mutation = useStartBacktestTune();
  const { register, handleSubmit, formState } = useForm<TuneRequest>({
    defaultValues: {
      train_start: 2013,
      train_end: 2016,
      validate_start: 2017,
      validate_end: 2019,
    },
  });
  return (
    <Card>
      <h2 className="text-lg font-semibold">New tune</h2>
      <p className="mt-1 text-xs text-fg-muted">
        Walk-forward train / validate split.
      </p>
      <form
        className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4"
        onSubmit={handleSubmit((data) => mutation.mutate(data))}
      >
        {(["train_start", "train_end", "validate_start", "validate_end"] as const).map(
          (key) => (
            <label key={key} className="flex flex-col gap-1 text-xs">
              <span className="text-fg-muted">{key.replace("_", " ")}</span>
              <input
                type="number"
                min={1996}
                max={2099}
                {...register(key, { valueAsNumber: true, required: true })}
                className="rounded-md border border-bg-subtle bg-bg-subtle px-3 py-2 text-sm"
              />
            </label>
          ),
        )}
        <div className="col-span-2 flex items-end sm:col-span-4">
          <Button
            type="submit"
            variant="primary"
            disabled={mutation.isPending || !formState.isValid}
          >
            {mutation.isPending ? <Spinner /> : null} Tune
          </Button>
        </div>
      </form>
      {mutation.error && (
        <div className="mt-2 text-xs text-danger">
          {(mutation.error as Error).message}
        </div>
      )}
    </Card>
  );
}

export default function BacktestHub() {
  const navigate = useNavigate();
  const runsQuery = useBacktestRuns();
  const [selected, setSelected] = useState<Set<string | number>>(new Set());
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [progressLine, setProgressLine] = useState<string | null>(null);
  const startMutation = useStartBacktestRun();

  // WebSocket: subscribe whenever a job kicks off. Reconnect on close.
  useEffect(() => {
    const job = startMutation.data?.job_id;
    if (!job) return;
    setActiveJobId(job);
    if (typeof window === "undefined") return;
    const wsScheme = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(
      `${wsScheme}://${window.location.host}/api/events?job_id=${job}`,
    );
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as JobEvent;
        if (data.job_id !== job) return;
        const payload = data.payload as { step?: string; percent?: number };
        setProgressLine(
          `${payload.step ?? "running"} ${
            payload.percent !== undefined ? `${Math.round(payload.percent)}%` : ""
          }`,
        );
        if (data.type.endsWith(".complete") || data.type.endsWith(".error")) {
          setActiveJobId(null);
          setProgressLine(null);
        }
      } catch {
        // ignore malformed frames
      }
    };
    ws.onerror = () => {
      setProgressLine(null);
    };
    return () => {
      ws.close();
    };
  }, [startMutation.data?.job_id]);

  const toggle = useCallback((id: string | number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const columns = useMemo<ColumnDef<BacktestRunSummary>[]>(
    () => [
      {
        id: "select",
        header: "",
        cell: ({ row }) => (
          <input
            type="checkbox"
            checked={selected.has(row.original.id)}
            onChange={() => toggle(row.original.id)}
            onClick={(e) => e.stopPropagation()}
            aria-label={`Select run ${row.original.id}`}
          />
        ),
        enableSorting: false,
      },
      { id: "id", accessorKey: "id", header: "ID" },
      { id: "mode", accessorKey: "mode", header: "Mode" },
      {
        id: "started_at",
        accessorKey: "started_at",
        header: "Started",
        cell: ({ getValue }) => {
          const v = getValue() as string;
          return v ? new Date(v).toLocaleString() : "—";
        },
      },
      {
        id: "duration",
        accessorKey: "duration_s",
        header: "Duration",
        cell: ({ getValue }) => formatDuration(getValue() as number),
      },
      {
        id: "primary_metric",
        accessorKey: "primary_metric",
        header: "Primary metric",
        cell: ({ getValue }) => {
          const v = getValue() as number | null;
          return v === null || v === undefined ? "—" : v.toFixed(3);
        },
      },
      {
        id: "status",
        accessorKey: "status",
        header: "Status",
        cell: ({ getValue }) => {
          const v = getValue() as BacktestRunSummary["status"];
          return <Pill tone={STATUS_TONES[v] ?? "default"}>{v}</Pill>;
        },
      },
    ],
    [selected, toggle],
  );

  const selectedIds = useMemo(() => Array.from(selected), [selected]);

  return (
    <div className="flex flex-col gap-4 p-4 lg:p-6">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold">Backtest</h1>
        {progressLine && (
          <Pill tone="accent" className={cn("animate-pulse")}>
            {progressLine}
          </Pill>
        )}
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <NewRunCard activeJobId={activeJobId} />
        <NewTuneCard />
      </div>

      <Card>
        <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">History</h2>
          <div className="flex items-center gap-2">
            <span className="text-xs text-fg-muted">
              {selected.size} selected
            </span>
            <Button
              variant="secondary"
              disabled={selected.size < 2}
              onClick={() =>
                navigate(`/backtest/compare?ids=${selectedIds.join(",")}`)
              }
            >
              Compare
            </Button>
          </div>
        </header>
        {runsQuery.isLoading ? (
          <Spinner />
        ) : runsQuery.error ? (
          <div className="text-danger">
            {(runsQuery.error as Error).message}
          </div>
        ) : (
          <DataTable
            data={runsQuery.data ?? []}
            columns={columns}
            onRowClick={(r) => navigate(`/backtest/${r.id}`)}
            rowKey={(r) => r.id}
            emptyMessage="No runs yet — kick off one above."
            enableColumnVisibility={false}
          />
        )}
      </Card>
    </div>
  );
}
