import { TimeSeriesLine } from "./TimeSeriesLine";
import type { RedfinSeriesResponse } from "../api/types";

export interface RedfinTrioProps {
  data: RedfinSeriesResponse | undefined | null;
  /** Optional override for layout direction on small screens. */
  forceVertical?: boolean;
}

/**
 * Three mini-charts in a row: DOM, sale-to-list, inventory.
 * Collapses to a vertical stack at < md.
 */
export function RedfinTrio({ data, forceVertical = false }: RedfinTrioProps) {
  const containerCls = forceVertical
    ? "flex flex-col gap-3"
    : "grid grid-cols-1 gap-3 md:grid-cols-3";
  return (
    <div className={containerCls} data-testid="redfin-trio">
      <MiniPanel title="Days on market" subtitle="DOM">
        <TimeSeriesLine
          series={[{ name: "DOM", data: data?.dom, color: "#5b8def" }]}
          height={140}
          compact
        />
      </MiniPanel>
      <MiniPanel title="Sale-to-list ratio" subtitle="">
        <TimeSeriesLine
          series={[{ name: "Sale/list", data: data?.sale_to_list, color: "#3aaf85" }]}
          height={140}
          compact
        />
      </MiniPanel>
      <MiniPanel title="Inventory" subtitle="units">
        <TimeSeriesLine
          series={[{ name: "Inventory", data: data?.inventory, color: "#d9a441" }]}
          height={140}
          compact
        />
      </MiniPanel>
    </div>
  );
}

function MiniPanel({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-bg-panel bg-bg-subtle p-3">
      <div className="mb-1 flex items-baseline justify-between">
        <h4 className="text-xs font-semibold text-fg">{title}</h4>
        {subtitle ? <span className="text-[10px] text-fg-subtle">{subtitle}</span> : null}
      </div>
      {children}
    </div>
  );
}

export default RedfinTrio;
