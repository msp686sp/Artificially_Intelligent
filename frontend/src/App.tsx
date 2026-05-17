import { Link, NavLink, Route, Routes } from "react-router-dom";
import SqlWorkbench from "@/routes/sql";
import SchemaBrowser from "@/routes/schema";
import BacktestHub from "@/routes/backtest";
import BacktestDetail from "@/routes/backtest/[id]";
import BacktestCompare from "@/routes/backtest/compare";

/**
 * App shell. fe-shell (agent 4) owns the polished Shell/Sidebar/MobileNav and
 * may replace this in integration. Until then, this minimal layout boots the
 * router and renders the routes my agent owns plus placeholders for the rest.
 */
function Placeholder({ name }: { name: string }) {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-semibold">{name}</h1>
      <p className="mt-2 text-fg-muted">
        Owned by another agent. Placeholder until integration.
      </p>
    </div>
  );
}

const NAV: Array<{ to: string; label: string }> = [
  { to: "/", label: "Dashboard" },
  { to: "/sources", label: "Sources" },
  { to: "/rankings", label: "Rankings" },
  { to: "/sql", label: "SQL" },
  { to: "/schema", label: "Schema" },
  { to: "/filters", label: "Filters" },
  { to: "/backtest", label: "Backtest" },
  { to: "/manifest", label: "Manifest" },
  { to: "/settings", label: "Settings" },
];

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-bg text-fg lg:flex-row">
      <header className="border-b border-bg-subtle bg-bg-panel px-4 py-3 lg:hidden">
        <Link to="/" className="text-lg font-semibold">
          Rental Market Analysis
        </Link>
        <nav className="mt-2 flex flex-wrap gap-2 text-sm">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `rounded-md px-3 py-2 ${
                  isActive
                    ? "bg-accent text-white"
                    : "text-fg-muted hover:bg-bg-subtle"
                }`
              }
              end={item.to === "/"}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <aside className="hidden w-56 shrink-0 border-r border-bg-subtle bg-bg-panel p-4 lg:block">
        <Link to="/" className="block text-lg font-semibold">
          Rental Market
        </Link>
        <nav className="mt-4 flex flex-col gap-1 text-sm">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `rounded-md px-3 py-2 ${
                  isActive
                    ? "bg-accent text-white"
                    : "text-fg-muted hover:bg-bg-subtle"
                }`
              }
              end={item.to === "/"}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="min-w-0 flex-1">{children}</main>
    </div>
  );
}

export default function App() {
  return (
    <Shell>
      <Routes>
        {/* === ROUTES START === */}
        {/* fe-sql-backtest (agent 7) */}
        <Route path="/sql" element={<SqlWorkbench />} />
        <Route path="/schema" element={<SchemaBrowser />} />
        <Route path="/backtest" element={<BacktestHub />} />
        <Route path="/backtest/compare" element={<BacktestCompare />} />
        <Route path="/backtest/:id" element={<BacktestDetail />} />
        {/* === ROUTES END === */}

        {/* Placeholders for routes owned by other agents */}
        <Route path="/" element={<Placeholder name="Dashboard" />} />
        <Route path="/sources" element={<Placeholder name="Sources" />} />
        <Route
          path="/sources/:name"
          element={<Placeholder name="Source detail" />}
        />
        <Route path="/rankings" element={<Placeholder name="Rankings" />} />
        <Route
          path="/rankings/:zcta5"
          element={<Placeholder name="Zip detail" />}
        />
        <Route path="/compare" element={<Placeholder name="Compare" />} />
        <Route path="/filters" element={<Placeholder name="Filters" />} />
        <Route path="/manifest" element={<Placeholder name="Manifest" />} />
        <Route path="/settings" element={<Placeholder name="Settings" />} />
        <Route path="/logs" element={<Placeholder name="Refresh log" />} />
        <Route path="*" element={<Placeholder name="Not found" />} />
      </Routes>
    </Shell>
  );
}
