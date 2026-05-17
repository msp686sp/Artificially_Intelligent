import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { ThemeProvider } from "@/layout/ThemeProvider";
import { Shell } from "@/layout/Shell";
import { ToastProvider } from "@/components/Toast";
import { EmptyState } from "@/components/EmptyState";

// IMPORTANT — multi-agent coordination:
// Each frontend page agent (5, 6, 7) replaces one or more <EmptyState>
// placeholders below with a real route component (lazy-imported from
// `@/routes/<page>`). To keep merges mechanical, ONLY edit between the
// "ROUTES START" and "ROUTES END" markers below, and prefer adding
// imports at the top of *this* file with a comment annotating which
// agent owns each one. The Shell, Providers, and 404 catch-all are
// owned by fe-shell (agent 4) and should not be moved.

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
  // The QueryClient must outlive any re-render that would replace it
  // (HMR keeps the cache warm). useState gives us a stable instance.
  const [client] = useState(() => queryClient);

  return (
    <ThemeProvider>
      <QueryClientProvider client={client}>
        <ToastProvider>
          <BrowserRouter>
            <Shell>
              <Routes>
                {/* === ROUTES START === */}
                {/* Agent 5 (fe-sources-dashboard) owns: */}
                <Route
                  path="/"
                  element={<EmptyState pageName="Dashboard" ownedBy="agent 5 (fe-sources-dashboard)" />}
                />
                <Route
                  path="/sources"
                  element={<EmptyState pageName="Sources" ownedBy="agent 5 (fe-sources-dashboard)" />}
                />
                <Route
                  path="/sources/:name"
                  element={<EmptyState pageName="Source detail" ownedBy="agent 5 (fe-sources-dashboard)" />}
                />
                <Route
                  path="/manifest"
                  element={<EmptyState pageName="Manifest" ownedBy="agent 5 (fe-sources-dashboard)" />}
                />
                <Route
                  path="/logs"
                  element={<EmptyState pageName="Logs" ownedBy="agent 5 (fe-sources-dashboard)" />}
                />
                <Route
                  path="/settings"
                  element={<EmptyState pageName="Settings" ownedBy="agent 5 (fe-sources-dashboard)" />}
                />

                {/* Agent 6 (fe-rankings-zips) owns: */}
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

                {/* Agent 7 (fe-sql-backtest) owns: */}
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

                {/* 404 — fe-shell owned. Do not move. */}
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
