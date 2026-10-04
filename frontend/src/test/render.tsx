import { render, type RenderResult } from "@testing-library/react";
import userEvent, { type UserEvent } from "@testing-library/user-event";
import type { ReactElement } from "react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { AppProviders, createQueryClient } from "@/App";

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
}

// Renders `ui` inside the app's real providers (theme, i18n, a fresh query cache)
// and a memory router at `route`. Task 3 adds a signed-in session option.
export function renderWithProviders(
  ui: ReactElement,
  { route = "/", path = "*" }: RenderOptions = {},
): RenderWithProvidersResult {
  const router = createMemoryRouter([{ path, element: ui }], { initialEntries: [route] });
  const result = render(
    <AppProviders queryClient={createQueryClient()}>
      <RouterProvider router={router} />
    </AppProviders>,
  );
  return { ...result, user: userEvent.setup(), router };
}
