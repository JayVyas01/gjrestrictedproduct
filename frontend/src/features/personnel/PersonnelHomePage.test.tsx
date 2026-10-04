import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { AlertList, Home, TransactionSummary } from "@/api/types";
import { contract } from "@/test/handlers";
import { renderApp } from "@/test/render";
import { server } from "@/test/server";

const AS_OFFICER = ["me_personnel", "home_personnel"];
const AS_SUPERINTENDENT = ["me_superintendent", "home_superintendent"];
const ROW = contract<TransactionSummary[]>("transactions_list")[0]!;

function serveHome(name: string, counts: Home["counts"]) {
  const home = contract<Home>(name);
  home.counts = { ...home.counts, ...counts };
  server.use(http.get("/api/home", () => HttpResponse.json(home)));
}

// The decision queue: one row on the officer chain, one waiting for the final approval.
function serveQueue() {
  const searches: string[] = [];
  const queue: TransactionSummary[] = [
    { ...ROW, reference: "TXOFFICER001", status: "AWAITING_OFFICER", your_role: "officer" },
    {
      ...ROW,
      reference: "TXFINAL00002",
      status: "AWAITING_SUPERINTENDENT",
      approval_chain: "OFFICER_THEN_SUPERINTENDENT",
      approval_chain_label: "Officer, then superintendent",
      your_role: "superintendent",
    },
  ];
  server.use(
    http.get("/api/transactions", ({ request }) => {
      searches.push(new URL(request.url).search);
      return HttpResponse.json(queue);
    }),
  );
  return searches;
}

describe("PersonnelHomePage", () => {
  it("shows what waits, the decision queue and the latest alerts", async () => {
    const searches = serveQueue();
    const { container } = renderApp("/personnel", { contracts: AS_OFFICER });
    expect(await screen.findByRole("heading", { level: 1, name: "Home" })).toBeInTheDocument();

    expect(await screen.findByText("1 transaction waits for your decision.")).toBeInTheDocument();
    expect(screen.getByText("1 unacknowledged alert.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Review the queue" })).toHaveAttribute(
      "href",
      "/personnel/transactions?awaiting=me",
    );
    // An area officer has no batches.
    expect(screen.queryByText(/Batch due|overdue/)).not.toBeInTheDocument();

    const queue = await screen.findByRole("table", { name: "Decision queue" });
    await waitFor(() => expect(searches).toEqual(["?awaiting=me"]));
    const [, officerRow, finalRow] = within(queue).getAllByRole("row");
    expect(within(officerRow!).getByRole("link", { name: "TXOFFICER001" })).toHaveAttribute(
      "href",
      "/personnel/transactions/TXOFFICER001",
    );
    expect(within(officerRow!).getByText("Officer")).toBeInTheDocument();
    expect(within(officerRow!).queryByText("Final approval")).not.toBeInTheDocument();
    expect(within(officerRow!).getByText("Awaiting you")).toBeInTheDocument();
    expect(within(finalRow!).getByText("Officer, then superintendent")).toBeInTheDocument();
    expect(within(finalRow!).getByText("Final approval")).toBeInTheDocument();

    const alerts = screen.getByRole("region", { name: "Unacknowledged alerts" });
    expect(await within(alerts).findByText("Buyer rejected a transaction")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("opens the alerts drawer from the home page", async () => {
    const { user } = renderApp("/personnel", { contracts: AS_OFFICER });
    const alerts = await screen.findByRole("region", { name: "Unacknowledged alerts" });
    await within(alerts).findByText("Buyer rejected a transaction");
    await user.click(within(alerts).getByRole("button", { name: "Open alerts" }));
    expect(await screen.findByRole("dialog", { name: "Alerts" })).toBeInTheDocument();
  });

  it("shows only the latest 3 unacknowledged alerts", async () => {
    const list = contract<AlertList>("alerts");
    const base = list.alerts[0]!;
    list.alerts = [1, 2, 3, 4].map((id) => ({
      ...base,
      id,
      transaction_reference: `TXALERT0000${id}`,
    }));
    list.alerts.push({ ...base, id: 9, acknowledged: true, transaction_reference: "TXACKED00009" });
    server.use(http.get("/api/alerts", () => HttpResponse.json(list)));
    renderApp("/personnel", { contracts: AS_OFFICER });
    const alerts = await screen.findByRole("region", { name: "Unacknowledged alerts" });
    await within(alerts).findByText("TXALERT00001", { exact: false });
    expect(within(alerts).getAllByRole("listitem")).toHaveLength(3);
    expect(within(alerts).queryByText(/TXALERT00004|TXACKED00009/)).not.toBeInTheDocument();
  });

  it("tells a superintendent when the next batch is due", async () => {
    renderApp("/personnel", { contracts: AS_SUPERINTENDENT });
    expect(await screen.findByText("Batch due on 28 Oct 2026.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Review batches" })).toHaveAttribute(
      "href",
      "/personnel/batches",
    );
  });

  it("tells a superintendent about overdue batches, in red", async () => {
    serveHome("home_superintendent", { overdue_batches: 2 });
    renderApp("/personnel", { contracts: AS_SUPERINTENDENT });
    const overdue = await screen.findByText("2 batches overdue.");
    expect(overdue).toHaveAttribute("data-tone", "overdue");
    expect(screen.queryByText(/Batch due on/)).not.toBeInTheDocument();
  });

  it("says when nothing waits", async () => {
    serveHome("home_personnel", { awaiting_your_decision: 0, unacknowledged_alerts: 0 });
    server.use(
      http.get("/api/transactions", () => HttpResponse.json([])),
      http.get("/api/alerts", () => HttpResponse.json({ unacknowledged: 0, alerts: [] })),
    );
    renderApp("/personnel", { contracts: AS_OFFICER });
    expect(await screen.findByText("Nothing waits for you.")).toBeInTheDocument();
    expect(await screen.findByText("Nothing waits for your decision.")).toBeInTheDocument();
    expect(await screen.findByText("No unacknowledged alerts.")).toBeInTheDocument();
  });
});

describe("PersonnelTransactionsPage", () => {
  it("lists the transactions with their approval chain, filtered by tab", async () => {
    const searches = serveQueue();
    const { user, container } = renderApp("/personnel/transactions", { contracts: AS_OFFICER });
    expect(
      await screen.findByRole("heading", { level: 1, name: "Transactions" }),
    ).toBeInTheDocument();
    const table = await screen.findByRole("table", { name: "Transactions" });
    expect(within(table).getByText("Final approval")).toBeInTheDocument();
    // Officers see both parties.
    expect(
      within(table).getAllByText("Sanand Spirits Pvt Ltd to Bopal Bar & Kitchen"),
    ).toHaveLength(2);
    expect(await axe(container)).toHaveNoViolations();

    await user.click(screen.getByRole("tab", { name: "Waiting for you" }));
    await waitFor(() => expect(searches).toEqual(["", "?awaiting=me"]));
  });

  it("opens on the queue from the home link", async () => {
    const searches = serveQueue();
    renderApp("/personnel/transactions?awaiting=me", { contracts: AS_OFFICER });
    await waitFor(() => expect(searches).toEqual(["?awaiting=me"]));
    expect(screen.getByRole("tab", { name: "Waiting for you" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });
});
