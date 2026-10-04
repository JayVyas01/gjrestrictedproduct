import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { Home, StockRow } from "@/api/types";
import { contract } from "@/test/handlers";
import { renderApp } from "@/test/render";
import { server } from "@/test/server";

function serveHome(awaiting: number) {
  const home = contract<Home>("home_licensee");
  home.counts.awaiting_your_decision = awaiting;
  server.use(http.get("/api/home", () => HttpResponse.json(home)));
}

describe("LicenseeHomePage", () => {
  it("shows what waits, the licences, the stock and recent transactions", async () => {
    serveHome(2);
    const { container } = renderApp("/licensee");
    expect(await screen.findByRole("heading", { level: 1, name: "Home" })).toBeInTheDocument();

    expect(
      await screen.findByText("2 purchases wait for your confirmation."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Review purchases" })).toHaveAttribute(
      "href",
      "/licensee/transactions?side=purchases&awaiting=me",
    );

    // The licence card, the stock table and the latest transactions.
    expect(await screen.findByRole("heading", { name: "Retail: Spirits" })).toBeInTheDocument();
    const stock = await screen.findByRole("table", { name: "Your stock" });
    expect(within(stock).getByRole("cell", { name: "Whisky" })).toBeInTheDocument();
    expect(within(stock).getByRole("cell", { name: "400 L" })).toBeInTheDocument();
    const recent = await screen.findByRole("table", { name: "Recent transactions" });
    expect(within(recent).getByRole("link", { name: "TXGTPGD3K3KZ" })).toHaveAttribute(
      "href",
      "/licensee/transactions/TXGTPGD3K3KZ",
    );
    expect(within(recent).getByText("Bopal Bar & Kitchen")).toBeInTheDocument();

    const main = screen.getByRole("main");
    expect(within(main).getByRole("link", { name: "New sale" })).toHaveAttribute(
      "href",
      "/licensee/sale/new",
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("uses the singular for one purchase", async () => {
    serveHome(1);
    renderApp("/licensee");
    expect(
      await screen.findByText("1 purchase waits for your confirmation."),
    ).toBeInTheDocument();
  });

  it("suggests a new sale when nothing waits", async () => {
    renderApp("/licensee"); // the contract has awaiting_your_decision: 0
    expect(
      await screen.findByText("Nothing waits for you. Start a new sale when you're ready."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Start a new sale" })).toHaveAttribute(
      "href",
      "/licensee/sale/new",
    );
  });

  it("says so when there is no stock", async () => {
    server.use(http.get("/api/stock/mine", () => HttpResponse.json([] as StockRow[])));
    renderApp("/licensee");
    expect(await screen.findByText("You hold no stock.")).toBeInTheDocument();
  });
});
