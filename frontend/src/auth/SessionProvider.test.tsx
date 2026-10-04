import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiGet } from "@/api/client";
import { keys } from "@/api/hooks/keys";
import { contract } from "@/test/handlers";
import { renderApp, serveSignedOut } from "@/test/render";
import { server } from "@/test/server";
import { IDLE_SIGN_OUT_MS, IDLE_WARNING_MS, KEEP_ALIVE_MS } from "./SessionProvider";

const DRAFT = "gj.draft.sale";
const SELLER = contract<{ user_id: string }>("me_licensee").user_id;
const WARNING = "You'll be signed out in 1 minute because of inactivity.";
const MINUTE = 60_000;

/** Counts the requests to `me` (answered as signed in) and to logout. */
function countSessionCalls() {
  const calls = { me: 0, logout: 0 };
  server.use(
    http.get("/api/auth/me", () => {
      calls.me += 1;
      return HttpResponse.json(contract<object>("me_licensee"));
    }),
    http.post("/api/auth/logout", () => {
      calls.logout += 1;
      return new HttpResponse(null, { status: 204 });
    }),
  );
  return calls;
}

/** Moves the fake clock on by `ms`, letting React and the timers it starts catch up. */
async function idle(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

async function openSignedIn() {
  const rendered = renderApp("/licensee");
  await screen.findByText("Sanand Spirits Pvt Ltd");
  return rendered;
}

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

describe("idle timeout", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("warns after 14 minutes without input, in an accessible dialog", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    countSessionCalls();
    await openSignedIn();

    await idle(IDLE_WARNING_MS - MINUTE);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await idle(MINUTE);
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent(WARNING);
    await waitFor(() =>
      expect(within(dialog).getByRole("button", { name: "Stay signed in" })).toHaveFocus(),
    );
  });

  it("any input starts the 14 minutes again", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    countSessionCalls();
    await openSignedIn();

    await idle(10 * MINUTE);
    fireEvent.keyDown(document.body, { key: "a" });
    await idle(10 * MINUTE);
    fireEvent.pointerDown(document.body);
    await idle(IDLE_WARNING_MS - MINUTE);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    fireEvent.scroll(window);
    await idle(IDLE_WARNING_MS);
    expect(await screen.findByRole("dialog")).toHaveTextContent(WARNING);
  });

  it("input while active keeps the server session alive too", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const calls = countSessionCalls();
    await openSignedIn();
    const before = calls.me;

    fireEvent.pointerDown(document.body);
    expect(calls.me).toBe(before); // a request was made only just now
    await idle(KEEP_ALIVE_MS + 1);
    fireEvent.pointerDown(document.body);
    await waitFor(() => expect(calls.me).toBe(before + 1));
  });

  it("Stay signed in makes an ordinary request and starts the timer again", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const calls = countSessionCalls();
    const { user, router } = await openSignedIn();
    await idle(IDLE_WARNING_MS);
    const dialog = await screen.findByRole("dialog");
    const before = calls.me;

    await user.click(within(dialog).getByRole("button", { name: "Stay signed in" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(calls.me).toBe(before + 1);

    // Past the old sign-out time: still signed in.
    await idle(2 * MINUTE);
    expect(router.state.location.pathname).toBe("/licensee");
    expect(calls.logout).toBe(0);
  });

  it("signs out at 15 minutes: to the expiry notice, with the cache and drafts cleared", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const calls = countSessionCalls();
    const { router, queryClient } = await openSignedIn();
    sessionStorage.setItem(DRAFT, JSON.stringify({ owner: SELLER }));

    await idle(IDLE_WARNING_MS);
    await screen.findByRole("dialog");
    await idle(IDLE_SIGN_OUT_MS - IDLE_WARNING_MS);

    await waitFor(() => expect(router.state.location.pathname).toBe("/sign-in"));
    expect(router.state.location.search).toBe("?expired=1");
    expect(calls.logout).toBe(1);
    expect(sessionStorage.getItem(DRAFT)).toBeNull();
    expect(queryClient.getQueryData(keys.home)).toBeUndefined();
  });

  it("does not run while signed out", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { router } = renderApp("/sign-in", { signedOut: true });
    await screen.findByLabelText("User ID");
    await idle(IDLE_SIGN_OUT_MS + MINUTE);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(router.state.location.search).toBe("");
  });
});

describe("a session that ended before the page loaded", () => {
  it("removes a left-over draft and shows the expiry notice", async () => {
    sessionStorage.setItem(DRAFT, JSON.stringify({ owner: SELLER, step: 0 }));
    const { router } = renderApp("/licensee/sale/new", { signedOut: true });

    await waitFor(() => expect(router.state.location.pathname).toBe("/sign-in"));
    await waitFor(() => expect(router.state.location.search).toBe("?expired=1"));
    expect(sessionStorage.getItem(DRAFT)).toBeNull();
    expect(await screen.findByRole("status")).toHaveTextContent(/Your session ended/);
  });

  it("with nothing left behind, is a plain sign-in", async () => {
    const { router } = renderApp("/licensee", { signedOut: true });
    await waitFor(() => expect(router.state.location.pathname).toBe("/sign-in"));
    await screen.findByLabelText("User ID");
    expect(router.state.location.search).toBe("");
  });
});
