import { useHealth } from "@/hooks/useVersion";

export function HealthPill() {
  const { data, isLoading, isError } = useHealth();
  let dotClass = "";
  let label = "unknown";
  if (isLoading) {
    label = "loading…";
  } else if (isError || !data) {
    dotClass = "down";
    label = "down";
  } else {
    dotClass = data.status;
    label = data.status;
  }
  return (
    <span data-testid="shell-status-pill" className="health-pill" title="API health">
      <span className={`dot ${dotClass}`} />
      <span>API: {label}</span>
    </span>
  );
}
