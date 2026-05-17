import type { SourceStatus } from "@/api/types";
import { Badge, type BadgeTone } from "./Badge";

const TONE_MAP: Record<SourceStatus, BadgeTone> = {
  ok: "success",
  stale: "warning",
  error: "danger",
  never: "neutral",
};

const LABEL_MAP: Record<SourceStatus, string> = {
  ok: "Fresh",
  stale: "Stale",
  error: "Errored",
  never: "Not loaded",
};

interface StatusPillProps {
  status: SourceStatus;
  className?: string;
}

/** Color-coded pill for source/manifest status. Pulls from API types. */
export function StatusPill({ status, className }: StatusPillProps) {
  return (
    <Badge tone={TONE_MAP[status]} className={className}>
      <span
        aria-hidden
        className={
          {
            ok: "h-1.5 w-1.5 rounded-full bg-success",
            stale: "h-1.5 w-1.5 rounded-full bg-warning",
            error: "h-1.5 w-1.5 rounded-full bg-danger",
            never: "h-1.5 w-1.5 rounded-full bg-fg-subtle",
          }[status]
        }
      />
      {LABEL_MAP[status]}
    </Badge>
  );
}
