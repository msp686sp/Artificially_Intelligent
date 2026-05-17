import type { PropsWithChildren } from "react";

interface BadgeProps {
  status?: "ok" | "stale" | "error" | "never" | "neutral";
}

export function Badge({ status = "neutral", children }: PropsWithChildren<BadgeProps>) {
  const cls = status === "neutral" ? "" : status;
  return <span className={`badge ${cls}`}>{children}</span>;
}
