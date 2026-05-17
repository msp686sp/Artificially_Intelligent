import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { ThemeProvider } from "@/layout/ThemeProvider";
import { Shell } from "@/layout/Shell";
import { ToastProvider } from "@/components/Toast";
import { EmptyState } from "@/components/EmptyState";

// Agent 5 (fe-sources-dashboard)
import DashboardPage from "@/routes/dashboard";
import SourcesPage from "@/routes/sources";
import SourceDetailPage from "@/routes/sources/detail";
import ManifestPage from "@/routes/manifest";
import LogsPage from "@/routes/logs";
import SettingsPage from "@/routes/settings";

// IMPORTANT — multi-agent coordination:
// Page agents (5, 6, 7) replace the <EmptyState> placeholders below
// with imports from `@/routes/<page>`. Add new imports at the top of
// this file with a comment annotating which agent owns each.
// Only edit between the ROUTES START/END markers. Shell + Providers +
// 404 catch-all are owned by fe-shell (agent 4) and should not move.

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Single-user, local-first: refetch on focus is unnecessary.
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30_000,
    },
  },
});

export function App() {
  // useState keeps the QueryClient stable across HMR re-renders.
  const [client] = useState(() => queryClient);

  return (
    <ThemeProvider>
      <QueryClientProvider client={client}>
        <ToastProvider>
          <BrowserRouter>
            <Shell>
              <Routes>
                {/* === ROUTES START === */}
                {/* Agent 5 (fe-sources-dashboard) */}
                <Route path="/" element={<DashboardPage />} />
                <Route path="/sources" element={<SourcesPage />} />
                <Route path="/sources/:name" element={<SourceDetailPage />} />
                <Route path="/manifest" element={<ManifestPage />} />
                <Route path="/logs" element={<LogsPage />} />
                <Route path="/settings" element={<SettingsPage />} />

                {/* Agent 6 (fe-rankings-zips) */}
                <Route
                  path="/rankings"
                  element={<EmptyState pageName="Rankings" ownedBy="agent 6 (fe-rankings-zips)" />}
                />
                <Route
                  path="/rankings/:zcta5"
                  element={<EmptyState pageName="Zip detail" ownedBy="agent 6 (fe-rankings-zips)" />}
                />
                <Route
                  path="/compare"
                  element={<EmptyState pageName="Compare" ownedBy="agent 6 (fe-rankings-zips)" />}
                />
                <Route
                  path="/filters"
                  element={<EmptyState pageName="Filters & weights" ownedBy="agent 6 (fe-rankings-zips)" />}
                />

                {/* Agent 7 (fe-sql-backtest) */}
                <Route
                  path="/sql"
                  element={<EmptyState pageName="SQL workbench" ownedBy="agent 7 (fe-sql-backtest)" />}
                />
                <Route
                  path="/schema"
                  element={<EmptyState pageName="Schema" ownedBy="agent 7 (fe-sql-backtest)" />}
                />
                <Route
                  path="/backtest"
                  element={<EmptyState pageName="Backtest" ownedBy="agent 7 (fe-sql-backtest)" />}
                />
                <Route
                  path="/backtest/compare"
                  element={<EmptyState pageName="Backtest compare" ownedBy="agent 7 (fe-sql-backtest)" />}
                />
                {/* === ROUTES END === */}

                {/* 404 — fe-shell owned. */}
                <Route
                  path="*"
                  element={
                    <EmptyState
                      title="Page not found"
                      description="The route you requested doesn't exist. Use the sidebar to navigate."
                    />
                  }
                />
              </Routes>
            </Shell>
          </BrowserRouter>
        </ToastProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}

export default App;
