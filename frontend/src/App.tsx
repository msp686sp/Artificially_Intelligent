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

// Agent 6 (fe-rankings-zips)
import RankingsIndex from "@/routes/rankings/index";
import ZipDetail from "@/routes/rankings/[zcta5]";
import CompareIndex from "@/routes/compare/index";
import FiltersIndex from "@/routes/filters/index";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30_000,
    },
  },
});

export function App() {
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
                <Route path="/rankings" element={<RankingsIndex />} />
                <Route path="/rankings/:zcta5" element={<ZipDetail />} />
                <Route path="/compare" element={<CompareIndex />} />
                <Route path="/filters" element={<FiltersIndex />} />

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
