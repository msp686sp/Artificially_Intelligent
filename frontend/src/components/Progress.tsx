interface ProgressProps {
  /** Fraction in [0, 1]. */
  value: number;
  label?: string;
}

export function Progress({ value, label }: ProgressProps) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100);
  return (
    <div>
      {label && (
        <div
          style={{ fontSize: "0.85rem", marginBottom: "0.25rem" }}
          className="muted"
        >
          {label} ({pct}%)
        </div>
      )}
      <div
        className="progress"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div className="fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
