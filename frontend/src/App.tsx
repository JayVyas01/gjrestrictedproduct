import "@mantine/core/styles.css";
import "@mantine/dates/styles.css";
import "@mantine/notifications/styles.css";
import "@/i18n";

import { MantineProvider } from "@mantine/core";
import { Notifications } from "@mantine/notifications";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { ApiError } from "@/api/client";
import { routes } from "@/routes";
import { cssVariablesResolver, theme } from "@/theme";

// A refusal (4xx: not found, not allowed, a bad filter) won't change on a second try; only
// server and network failures are retried, once.
function retryOnce(failures: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status < 500) return false;
  return failures < 1;
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: retryOnce, refetchOnWindowFocus: false },
    },
  });
}

// Everything except the router, so tests can supply a memory router instead.
export function AppProviders({
  queryClient,
  children,
}: {
  queryClient: QueryClient;
  children: ReactNode;
}) {
  return (
    <MantineProvider theme={theme} cssVariablesResolver={cssVariablesResolver}>
      <Notifications />
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </MantineProvider>
  );
}

export function App() {
  const [queryClient] = useState(createQueryClient);
  const [router] = useState(() => createBrowserRouter(routes));
  return (
    <AppProviders queryClient={queryClient}>
      <RouterProvider router={router} />
    </AppProviders>
  );
}
