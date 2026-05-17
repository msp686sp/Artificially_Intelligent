import { Routes, Route, Link, NavLink } from "react-router-dom";
import RankingsIndex from "./routes/rankings/index";
import ZipDetail from "./routes/rankings/[zcta5]";
import CompareIndex from "./routes/compare/index";
import FiltersIndex from "./routes/filters/index";

/**
 * App shell. Agent 4 (fe-shell) owns the polished Shell/Sidebar/MobileNav.
 * Until then, we render a minimal navigation harness so this agent's routes
 * are reachable and testable end-to-end. Other agents append their routes
 * inside the ROUTES START/END block.
 */
export default function App() {
  return (
    <div className="min-h-screen bg-bg text-fg">
      <header className="border-b border-bg-panel bg-bg-subtle">
        <nav className="flex flex-wrap items-center gap-4 px-4 py-3">
          <Link to="/" className="font-mono text-lg font-semibold">
            rental-gooey
          </Link>
          <div className="flex flex-wrap gap-2">
            <NavTab to="/rankings">Rankings</NavTab>
            <NavTab to="/compare">Compare</NavTab>
            <NavTab to="/filters">Filters</NavTab>
          </div>
        </nav>
      </header>
      <main className="p-4 md:p-6">
        <Routes>
          {/* === ROUTES START === */}
          <Route path="/" element={<HomePlaceholder />} />
          <Route path="/rankings" element={<RankingsIndex />} />
          <Route path="/rankings/:zcta5" element={<ZipDetail />} />
          <Route path="/compare" element={<CompareIndex />} />
          <Route path="/filters" element={<FiltersIndex />} />
          {/* === ROUTES END === */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </div>
  );
}

function NavTab({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `touch-target inline-flex items-center rounded-md px-3 py-2 text-sm font-medium ${
          isActive ? "bg-accent text-white" : "text-fg-muted hover:bg-bg-panel hover:text-fg"
        }`
      }
    >
      {children}
    </NavLink>
  );
}

function HomePlaceholder() {
  return (
    <div className="space-y-2">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <p className="text-fg-muted">
        Pick a section from the nav. Rankings, Compare, and Filters are wired up.
      </p>
    </div>
  );
}

function NotFound() {
  return <div className="text-fg-muted">Not found.</div>;
}
