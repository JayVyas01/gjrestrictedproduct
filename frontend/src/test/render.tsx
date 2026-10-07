import type { QueryClient } from "@tanstack/react-query";
import { render, type RenderResult } from "@testing-library/react";
import userEvent, { type UserEvent } from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import type { ReactElement } from "react";
import { createMemoryRouter, parsePath, RouterProvider } from "react-router-dom";
import { AppProviders, createQueryClient } from "@/App";
import { routes } from "@/routes";
import { contract, createHandlers, handlers } from "./handlers";
import { server } from "./server";

export interface RenderOptions {
  /** The URL the component is rendered at (default "/"). */
  route?: string;
  /** The route pattern, so the component can read params (default "*"). */
  path?: string;
}

export interface RenderWithProvidersResult extends RenderResult {
  /** A user-event instance for realistic typing and clicking. */
  user: UserEvent;
  router: ReturnType<typeof createMemoryRouter>;
  queryClient: QueryClient;
}

function renderRouter(router: ReturnType<typeof createMemoryRouter>): RenderWithProvidersResult {
  const queryClient = createQueryClient();
  const result = render(
    <AppProviders queryClient={queryClient}>
      <RouterProvider router={router} />
    </AppProviders>,
  );
  return { ...result, user: userEvent.setup(), router, queryClient };
}

// Renders `ui` inside the app's real providers (theme, i18n, a fresh query cache)
// and a memory router at `route`.
export function renderWithProviders(
  ui: ReactElement,
  { route = "/", path = "*" }: RenderOptions = {},
): RenderWithProvidersResult {
  return renderRouter(createMemoryRouter([{ path, element: ui }], { initialEntries: [route] }));
}

export interface RenderAppOptions {
  /** Contract variants to serve, e.g. ["me_personnel", "home_personnel"] for an officer. */
  contracts?: string[];
  /** Nobody is signed in: `me` answers 403. */
  signedOut?: boolean;
  /** Router state for the first entry (as `navigate(route, { state })` would leave). */
  state?: unknown;
}

/** `me` answers 403, as it does when nobody is signed in. */
export function serveSignedOut() {
  return http.get("/api/auth/me", () =>
    HttpResponse.json(contract<object>("error_403_not_signed_in"), { status: 403 }),
  );
}

// The whole app (session, guards, shell and pages) at `route`, signed in as the person the
// contracts describe (the licensee by default), or signed out.
// A handler the test set with `server.use(...)` before calling renderApp still wins: MSW
// puts the newest handlers first, so the test's own handlers are put back in front.
export function renderApp(
  route = "/",
  { contracts = [], signedOut = false, state }: RenderAppOptions = {},
): RenderWithProvidersResult {
  const defaults: readonly unknown[] = handlers;
  const overrides = server.listHandlers().filter((handler) => !defaults.includes(handler));
  if (contracts.length) server.use(...createHandlers(contracts));
  if (signedOut) server.use(serveSignedOut());
  if (overrides.length && (contracts.length || signedOut)) server.use(...overrides);
  const entry = state === undefined ? route : { ...parsePath(route), state };
  return renderRouter(createMemoryRouter(routes, { initialEntries: [entry] }));
}
