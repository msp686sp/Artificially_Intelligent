import type { ReactNode } from "react";

interface StatProps {
  label: ReactNode;
  value: ReactNode;
  hint?: ReactNode;
}

export function Stat({ label, value, hint }: StatProps) {
  return (
    <div className="stat" role="group" aria-label={typeof label === "string" ? label : undefined}>
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {hint && <div className="muted" style={{ fontSize: "0.8rem" }}>{hint}</div>}
    </div>
  );
}
