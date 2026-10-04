import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { contract } from "@/test/handlers";
import { renderApp } from "@/test/render";
import { server } from "@/test/server";

// Records the query string of every list request.
function recordListQueries() {
  const searches: string[] = [];
  server.use(
    http.get("/api/transactions", ({ request }) => {
      searches.push(new URL(request.url).search);
      return HttpResponse.json(contract<object>("transactions_list"));
    }),
  );
  return searches;
}

const originalMatchMedia = window.matchMedia.bind(window);

describe("LicenseeTransactionsPage", () => {
  afterEach(() => {
    window.matchMedia = originalMatchMedia;
  });

  it("lists the transactions with reference, substance, quantity, other party, status and date", async () => {
    const { container } = renderApp("/licensee/transactions");
    expect(
      await screen.findByRole("heading", { level: 1, name: "Transactions" }),
    ).toBeInTheDocument();
    const table = await screen.findByRole("table", { name: "Transactions" });
    const row = within(table).getAllByRole("row")[1]!;
    expect(within(row).getByRole("link", { name: "TXGTPGD3K3KZ" })).toHaveAttribute(
      "href",
      "/licensee/transactions/TXGTPGD3K3KZ",
    );
    expect(within(row).getByText("Whisky")).toBeInTheDocument();
    expect(within(row).getByText("10 L")).toBeInTheDocument();
    // The viewer sold it, so the other party is the buyer.
    expect(within(row).getByText("Bopal Bar & Kitchen")).toBeInTheDocument();
    expect(within(row).getByText("Approved")).toBeInTheDocument();
    expect(within(row).getByText("4 Oct 2026")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("each tab sends its filter", async () => {
    const searches = recordListQueries();
    const { user, router } = renderApp("/licensee/transactions");
    await screen.findByRole("table", { name: "Transactions" });
    expect(screen.getByRole("tab", { name: "All" })).toHaveAttribute("aria-selected", "true");

    await user.click(screen.getByRole("tab", { name: "Sales" }));
    await waitFor(() => expect(searches).toContain("?side=sales"));
    expect(router.state.location.search).toBe("?side=sales");

    await user.click(screen.getByRole("tab", { name: "Purchases" }));
    await waitFor(() => expect(searches).toContain("?side=purchases"));

    await user.click(screen.getByRole("tab", { name: "Waiting for you" }));
    await waitFor(() => expect(searches).toContain("?awaiting=me"));

    await user.click(screen.getByRole("tab", { name: "All" }));
    expect(searches[0]).toBe("");
    expect(router.state.location.search).toBe("");
  });

  it("opens on the purchases waiting for the viewer from the home link", async () => {
    const searches = recordListQueries();
    renderApp("/licensee/transactions?side=purchases&awaiting=me");
    await waitFor(() => expect(searches).toEqual(["?awaiting=me&side=purchases"]));
    expect(screen.getByRole("tab", { name: "Waiting for you" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("ignores unknown filter values in the address", async () => {
    const searches = recordListQueries();
    renderApp("/licensee/transactions?side=everything&awaiting=you");
    await waitFor(() => expect(searches).toEqual([""]));
  });

  it("shows an empty state when nothing matches", async () => {
    server.use(http.get("/api/transactions", () => HttpResponse.json([])));
    renderApp("/licensee/transactions?awaiting=me");
    expect(await screen.findByText("Nothing waits for your decision.")).toBeInTheDocument();
  });

  it("becomes stacked cards under 768 px", async () => {
    window.matchMedia = (query: string) => ({
      ...originalMatchMedia(query),
      matches: query.includes("max-width"),
    });
    const { container } = renderApp("/licensee/transactions");
    const list = await screen.findByRole("list", { name: "Transactions" });
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    const card = within(list).getAllByRole("listitem")[0]!;
    expect(within(card).getByRole("link", { name: "TXGTPGD3K3KZ" })).toBeInTheDocument();
    expect(within(card).getByText("Approved")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });
});
