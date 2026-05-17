import { Route, Routes } from "react-router-dom";
import { Shell } from "./layout/Shell";

// Pages owned by fe-sources-dashboard (agent 5).
import DashboardPage from "./routes/dashboard";
import SourcesPage from "./routes/sources";
import SourceDetailPage from "./routes/sources/detail";
import ManifestPage from "./routes/manifest";
import LogsPage from "./routes/logs";
import SettingsPage from "./routes/settings";

function EmptyState({ title }: { title: string }) {
  return (
    <div className="empty-state">
      <h2 style={{ marginTop: 0 }}>{title}</h2>
      <p>This route is owned by another agent and not yet wired up.</p>
    </div>
  );
}

export function App() {
  return (
    <Shell>
      <Routes>
        {/* === ROUTES START === */}
        {/* Agent 5 (fe-sources-dashboard) — claimed routes: */}
        <Route path="/" element={<DashboardPage />} />
        <Route path="/sources" element={<SourcesPage />} />
        <Route path="/sources/:name" element={<SourceDetailPage />} />
        <Route path="/manifest" element={<ManifestPage />} />
        <Route path="/logs" element={<LogsPage />} />
        <Route path="/settings" element={<SettingsPage />} />

        {/* Agent 6 (fe-rankings-zips) placeholders */}
        <Route path="/rankings" element={<EmptyState title="Rankings" />} />
        <Route
          path="/rankings/:zcta5"
          element={<EmptyState title="Zip detail" />}
        />
        <Route path="/compare" element={<EmptyState title="Compare" />} />
        <Route path="/filters" element={<EmptyState title="Filters & weights" />} />

        {/* Agent 7 (fe-sql-backtest) placeholders */}
        <Route path="/sql" element={<EmptyState title="SQL workbench" />} />
        <Route path="/schema" element={<EmptyState title="Schema browser" />} />
        <Route path="/backtest" element={<EmptyState title="Backtest" />} />
        <Route
          path="/backtest/compare"
          element={<EmptyState title="Backtest compare" />}
        />

        {/* 404 */}
        <Route path="*" element={<EmptyState title="Not found" />} />
        {/* === ROUTES END === */}
      </Routes>
    </Shell>
  );
}
