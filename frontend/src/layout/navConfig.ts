// Shared navigation config — single source of truth for the sidebar,
// mobile sheet, and bottom bar. Other agents wire their routes' paths
// up against the `path` values below. When routes change, update this
// file and every nav surface follows.

export interface NavItem {
  label: string;
  /** React Router path. Must match the route registered in App.tsx. */
  path: string;
  /** End={true} means exact-match active state (used for `/`). */
  end?: boolean;
  /** Whether the item shows in the mobile bottom bar (top 5). */
  bottomNav?: boolean;
  /** Two-letter shorthand for compact navigation. */
  short?: string;
  /** Description for tooltips/accessible labels. */
  description?: string;
}

export const NAV_ITEMS: NavItem[] = [
  {
    label: "Dashboard",
    path: "/",
    end: true,
    bottomNav: true,
    short: "DB",
    description: "Top-line health + quick actions",
  },
  {
    label: "Sources",
    path: "/sources",
    bottomNav: true,
    short: "SR",
    description: "Data source status & refresh",
  },
  {
    label: "Rankings",
    path: "/rankings",
    bottomNav: true,
    short: "RK",
    description: "MarketScore rankings",
  },
  {
    label: "Compare",
    path: "/compare",
    short: "CM",
    description: "Side-by-side zip comparison",
  },
  {
    label: "SQL",
    path: "/sql",
    bottomNav: true,
    short: "SQ",
    description: "Read-only SQL workbench",
  },
  {
    label: "Schema",
    path: "/schema",
    short: "SC",
    description: "Browse warehouse tables",
  },
  {
    label: "Filters",
    path: "/filters",
    short: "FL",
    description: "Edit filters & weights",
  },
  {
    label: "Backtest",
    path: "/backtest",
    bottomNav: true,
    short: "BT",
    description: "Backtest runs & comparisons",
  },
  {
    label: "Manifest",
    path: "/manifest",
    short: "MF",
    description: "Manifest viewer",
  },
  {
    label: "Logs",
    path: "/logs",
    short: "LG",
    description: "Refresh log",
  },
  {
    label: "Settings",
    path: "/settings",
    short: "ST",
    description: "Environment & theme",
  },
];

export const BOTTOM_NAV_ITEMS: NavItem[] = NAV_ITEMS.filter((item) => item.bottomNav).slice(0, 5);
