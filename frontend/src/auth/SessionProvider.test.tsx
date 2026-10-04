import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { apiGet } from "@/api/client";
import { keys } from "@/api/hooks/keys";
import { renderApp, serveSignedOut } from "@/test/render";
import { server } from "@/test/server";

const DRAFT = "gj.draft.sale";

describe("SessionProvider", () => {
  it("signing out calls the server, clears drafts and the cache, and goes to sign-in", async () => {
    let loggedOut = false;
    server.use(
      http.post("/api/auth/logout", () => {
        loggedOut = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    sessionStorage.setItem(DRAFT, '{"buyer":"x"}');
    sessionStorage.setItem("gj.mock.as", "seller");
    const { user, router, queryClient } = renderApp("/licensee");
    await screen.findByText("Sanand Spirits Pvt Ltd");
    expect(queryClient.getQueryData(keys.me)).toBeDefined();
    server.use(serveSignedOut());

    await user.click(screen.getByRole("button", { name: "Sign out" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/sign-in"));
    expect(loggedOut).toBe(true);
    expect(sessionStorage.getItem(DRAFT)).toBeNull();
    expect(sessionStorage.getItem("gj.mock.as")).toBe("seller");
    expect(queryClient.getQueryData(keys.me)).toBeUndefined();
    expect(router.state.location.search).toBe("");
  });

  it("when the session ends, clears drafts and the cache and shows the expiry notice", async () => {
    sessionStorage.setItem(DRAFT, '{"buyer":"x"}');
    const { router, queryClient } = renderApp("/licensee");
    await screen.findByText("Sanand Spirits Pvt Ltd");
    expect(queryClient.getQueryData(keys.me)).toBeDefined();

    // The session times out: every call now answers 403, `me` included.
    server.use(
      serveSignedOut(),
      http.get("/api/transactions", () =>
        HttpResponse.json({ detail: "Not signed in." }, { status: 403 }),
      ),
    );
    await expect(apiGet("/api/transactions")).rejects.toMatchObject({ status: 403 });

    await waitFor(() => expect(router.state.location.pathname).toBe("/sign-in"));
    expect(router.state.location.search).toBe("?expired=1");
    expect(await screen.findByRole("status")).toHaveTextContent(/Your session ended/);
    expect(sessionStorage.getItem(DRAFT)).toBeNull();
    expect(queryClient.getQueryData(keys.me)).toBeUndefined();
  });
});
