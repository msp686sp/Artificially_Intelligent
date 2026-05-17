import { useEffect, useMemo, useState } from "react";
import CodeMirror from "@uiw/react-codemirror";
import { yaml as yamlLang } from "@codemirror/lang-yaml";
import { Card } from "../../components/Card";
import { Button } from "../../components/Button";
import { Chip } from "../../components/Chip";
import { useToast } from "../../components/Toast";
import { useConfigFile, useSaveConfig } from "../../hooks/useConfig";
import {
  diffYaml,
  rankingsDryRunDiff,
  tryParseYaml,
  type YamlChange,
} from "../../lib/yaml-diff";
import { apiFetch, buildQuery } from "../../api/client";
import type { RankingsResponse } from "../../api/types";
import { cx } from "../../lib/cx";

interface EditorState {
  file: "filters.yaml" | "weights.yaml";
  current: string; // server-known content
  draft: string;
  parseError?: string;
}

const DEFAULT_FILES: Array<EditorState["file"]> = ["filters.yaml", "weights.yaml"];

export default function FiltersIndex() {
  const toast = useToast();
  const filters = useConfigFile("filters.yaml");
  const weights = useConfigFile("weights.yaml");
  const saveFilters = useSaveConfig("filters.yaml");
  const saveWeights = useSaveConfig("weights.yaml");

  const [drafts, setDrafts] = useState<Record<EditorState["file"], string>>({
    "filters.yaml": "",
    "weights.yaml": "",
  });
  // Track which editors the user has touched so we only seed from the server once.
  const [seeded, setSeeded] = useState<Record<EditorState["file"], boolean>>({
    "filters.yaml": false,
    "weights.yaml": false,
  });

  useEffect(() => {
    if (!seeded["filters.yaml"] && filters.data?.content !== undefined) {
      setDrafts((d) => ({ ...d, "filters.yaml": filters.data!.content }));
      setSeeded((s) => ({ ...s, "filters.yaml": true }));
    }
  }, [filters.data, seeded]);
  useEffect(() => {
    if (!seeded["weights.yaml"] && weights.data?.content !== undefined) {
      setDrafts((d) => ({ ...d, "weights.yaml": weights.data!.content }));
      setSeeded((s) => ({ ...s, "weights.yaml": true }));
    }
  }, [weights.data, seeded]);

  const draftErrors = useMemo<Record<EditorState["file"], string | undefined>>(() => {
    return {
      "filters.yaml": draftError(drafts["filters.yaml"]),
      "weights.yaml": draftError(drafts["weights.yaml"]),
    };
  }, [drafts]);

  const yamlDiffs = useMemo(() => {
    return {
      "filters.yaml": filters.data
        ? diffYaml(filters.data.content, drafts["filters.yaml"])
        : { changes: [] as YamlChange[], invalid: false },
      "weights.yaml": weights.data
        ? diffYaml(weights.data.content, drafts["weights.yaml"])
        : { changes: [] as YamlChange[], invalid: false },
    };
  }, [drafts, filters.data, weights.data]);

  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewDiff, setPreviewDiff] = useState<ReturnType<typeof rankingsDryRunDiff> | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  async function runPreview() {
    setPreviewError(null);
    setPreviewLoading(true);
    try {
      // Fetch the current top-N then the dry-run top-N with edited filters.
      const baseUrl = `/api/rankings${buildQuery({ limit: 200, sort: "market_score", order: "desc" })}`;
      const editedUrl = `/api/rankings${buildQuery({
        limit: 200,
        sort: "market_score",
        order: "desc",
        filters_yaml: drafts["filters.yaml"],
      })}`;
      const [base, edited] = await Promise.all([
        apiFetch<RankingsResponse>(baseUrl),
        apiFetch<RankingsResponse>(editedUrl),
      ]);
      const before = base.rows.map((r) => ({ zcta5: r.zcta5, market_score: r.market_score }));
      const after = edited.rows.map((r) => ({ zcta5: r.zcta5, market_score: r.market_score }));
      setPreviewDiff(rankingsDryRunDiff(before, after, 100));
    } catch (e) {
      setPreviewError(e instanceof Error ? e.message : String(e));
    } finally {
      setPreviewLoading(false);
    }
  }

  async function onSave(file: EditorState["file"]) {
    if (draftErrors[file]) {
      toast.push(`Cannot save ${file}: invalid YAML`, "danger");
      return;
    }
    const m = file === "filters.yaml" ? saveFilters : saveWeights;
    try {
      await m.mutateAsync(drafts[file]);
      toast.push(`Saved ${file}`, "success");
    } catch (e) {
      toast.push(
        `Save failed for ${file}: ${e instanceof Error ? e.message : String(e)}`,
        "danger",
      );
    }
  }

  function onDiscard(file: EditorState["file"]) {
    const server = (file === "filters.yaml" ? filters.data?.content : weights.data?.content) ?? "";
    setDrafts((d) => ({ ...d, [file]: server }));
  }

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold">Filters &amp; weights</h1>
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={runPreview} disabled={previewLoading || !!draftErrors["filters.yaml"]}>
            {previewLoading ? "Previewing…" : "Preview"}
          </Button>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {DEFAULT_FILES.map((file) => {
          const server = (file === "filters.yaml" ? filters.data?.content : weights.data?.content) ?? "";
          const dirty = drafts[file] !== server;
          const err = draftErrors[file];
          const yd = yamlDiffs[file];
          return (
            <Card key={file}>
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <h2 className="font-mono font-semibold">{file}</h2>
                <div className="flex items-center gap-2">
                  {dirty ? <Chip tone="warning">unsaved</Chip> : <Chip tone="success">clean</Chip>}
                  {err ? <Chip tone="danger">invalid YAML</Chip> : null}
                </div>
              </div>
              <div className="overflow-hidden rounded-md border border-bg-panel">
                <CodeMirror
                  value={drafts[file]}
                  height="320px"
                  theme="dark"
                  extensions={[yamlLang()]}
                  onChange={(v) => setDrafts((d) => ({ ...d, [file]: v }))}
                  data-testid={`editor-${file}`}
                />
              </div>
              {err ? (
                <p className="mt-2 text-xs text-danger" data-testid={`error-${file}`}>
                  {err}
                </p>
              ) : null}
              <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs text-fg-subtle">
                  {yd.changes.length === 0 ? "No changes" : `${yd.changes.length} change(s)`}
                </span>
                <div className="flex items-center gap-2">
                  <Button size="sm" variant="ghost" onClick={() => onDiscard(file)} disabled={!dirty}>
                    Discard
                  </Button>
                  <Button size="sm" onClick={() => onSave(file)} disabled={!dirty || !!err}>
                    Save
                  </Button>
                </div>
              </div>
              {yd.changes.length > 0 ? <YamlDiffList changes={yd.changes} /> : null}
            </Card>
          );
        })}
      </div>

      <Card>
        <h2 className="mb-2 text-lg font-semibold">Dry-run preview</h2>
        {previewError ? (
          <p className="text-sm text-danger">Preview failed: {previewError}</p>
        ) : previewLoading ? (
          <p className="text-sm text-fg-muted">Running preview…</p>
        ) : previewDiff ? (
          <PreviewDiffPanel diff={previewDiff} />
        ) : (
          <p className="text-sm text-fg-muted">
            Click <strong>Preview</strong> to compute the diff against the current top-100 rankings.
          </p>
        )}
      </Card>
    </div>
  );
}

function YamlDiffList({ changes }: { changes: YamlChange[] }) {
  return (
    <ul className="mt-2 max-h-48 space-y-1 overflow-y-auto rounded-md bg-bg-subtle p-2 text-xs">
      {changes.map((c, i) => (
        <li key={`${c.path}-${i}`} className="flex items-start gap-2 font-mono">
          <Chip
            tone={c.kind === "added" ? "success" : c.kind === "removed" ? "danger" : "warning"}
            className="shrink-0"
          >
            {c.kind === "added" ? "+" : c.kind === "removed" ? "−" : "Δ"}
          </Chip>
          <span className="truncate">
            <span className="text-fg-muted">{c.path || "(root)"}</span>
            {c.kind === "changed" ? (
              <span className="ml-1 text-fg-subtle">
                {JSON.stringify(c.before)} → {JSON.stringify(c.after)}
              </span>
            ) : c.kind === "added" ? (
              <span className="ml-1 text-fg-subtle">{JSON.stringify(c.after)}</span>
            ) : (
              <span className="ml-1 text-fg-subtle">{JSON.stringify(c.before)}</span>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

function PreviewDiffPanel({ diff }: { diff: ReturnType<typeof rankingsDryRunDiff> }) {
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
      <div>
        <h3 className="mb-1 text-xs font-semibold uppercase text-success">
          Added ({diff.added.length})
        </h3>
        <ul className="flex max-h-40 flex-wrap gap-1 overflow-y-auto">
          {diff.added.map((z) => (
            <Chip key={z} tone="success" className="font-mono">
              {z}
            </Chip>
          ))}
          {diff.added.length === 0 ? (
            <li className="text-xs text-fg-subtle">— none</li>
          ) : null}
        </ul>
      </div>
      <div>
        <h3 className="mb-1 text-xs font-semibold uppercase text-danger">
          Removed ({diff.removed.length})
        </h3>
        <ul className="flex max-h-40 flex-wrap gap-1 overflow-y-auto">
          {diff.removed.map((z) => (
            <Chip key={z} tone="danger" className="font-mono">
              {z}
            </Chip>
          ))}
          {diff.removed.length === 0 ? (
            <li className="text-xs text-fg-subtle">— none</li>
          ) : null}
        </ul>
      </div>
      <div>
        <h3 className="mb-1 text-xs font-semibold uppercase text-warning">
          Score deltas ({diff.score_deltas.length})
        </h3>
        <ul className="max-h-40 space-y-1 overflow-y-auto font-mono text-xs">
          {diff.score_deltas.slice(0, 25).map((d) => (
            <li key={d.zcta5} className="flex items-center justify-between gap-2">
              <span>{d.zcta5}</span>
              <span className={cx(d.delta > 0 ? "text-success" : "text-danger")}>
                {d.delta > 0 ? "+" : ""}
                {d.delta.toFixed(2)}
              </span>
            </li>
          ))}
          {diff.score_deltas.length === 0 ? (
            <li className="text-fg-subtle">— none</li>
          ) : null}
        </ul>
      </div>
    </div>
  );
}

function draftError(text: string): string | undefined {
  if (!text || text.trim() === "") return undefined;
  const r = tryParseYaml(text);
  return r.ok ? undefined : r.error;
}
