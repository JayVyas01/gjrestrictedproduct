import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { BatchSummary, TransactionDetail, TransactionSummary } from "@/api/types";
import { contract, serveContract } from "@/test/handlers";
import { renderApp } from "@/test/render";
import { server } from "@/test/server";

const AS_HEAD = ["me_head_authority", "home_head_authority"];
const AS_OWNER = ["me_software_owner", "home_software_owner"];
const ROW = contract<TransactionSummary[]>("transactions_list")[0]!;
const AUTHORITY_VIEW = contract<TransactionDetail>("transaction_detail_authority");
const BATCH = contract<BatchSummary[]>("oversight_batches")[0]!;

/** Records the query of every list request. */
function serveList() {
  const asked: string[] = [];
  server.use(
    http.get("/api/transactions", ({ request }) => {
      asked.push(new URL(request.url).search);
      return HttpResponse.json([{ ...ROW, your_role: "authority" }]);
    }),
  );
  return asked;
}

describe("OverviewTransactionsPage and the read-only screens", () => {
  it("lists every transaction, and the Superintendent-approved tab sends approved_by", async () => {
    const asked = serveList();
    const { user, router, container } = renderApp("/head/transactions", { contracts: AS_HEAD });
    expect(
      await screen.findByRole("heading", { level: 1, name: "Transactions" }),
    ).toBeInTheDocument();
    const table = await screen.findByRole("table", { name: "Transactions" });
    expect(within(table).getByRole("link", { name: ROW.reference })).toHaveAttribute(
      "href",
      `/head/transactions/${ROW.reference}`,
    );
    expect(table).toHaveTextContent(`${ROW.seller_name} to ${ROW.buyer_name}`);
    expect(await axe(container)).toHaveNoViolations();

    await user.click(screen.getByRole("tab", { name: "Superintendent-approved" }));
    await waitFor(() => expect(asked).toEqual(["", "?approved_by=superintendent"]));
    expect(router.state.location.search).toBe("?approved_by=superintendent");
  });

  it("opens on the filter in the address, for the Software Owner too", async () => {
    const asked = serveList();
    renderApp("/overview/transactions?approved_by=superintendent", { contracts: AS_OWNER });
    expect(
      await screen.findByRole("tab", { name: "Superintendent-approved", selected: true }),
    ).toBeInTheDocument();
    await waitFor(() => expect(asked).toEqual(["?approved_by=superintendent"]));
  });

  it("shows a transaction read-only: no decision and no cancel", async () => {
    server.use(serveContract("transaction_detail_authority"));
    const { container } = renderApp(`/head/transactions/${AUTHORITY_VIEW.reference}`, {
      contracts: AS_HEAD,
    });
    expect(await screen.findByRole("region", { name: "Summary" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to transactions" })).toHaveAttribute(
      "href",
      "/head/transactions",
    );
    expect(screen.queryByRole("region", { name: "Your decision" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Approve|Reject|Cancel sale/ })).toBeNull();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("shows batches read-only under the role's path", async () => {
    const { container } = renderApp("/head/batches", { contracts: AS_HEAD });
    const list = await screen.findByRole("list", { name: "Batches" });
    const link = within(list).getAllByRole("link")[0]!;
    expect(link).toHaveAttribute("href", `/head/batches/${BATCH.id}`);
    expect(await axe(container)).toHaveNoViolations();
  });

  it("shows a batch with no flag or sign-off, even when the server would allow it", async () => {
    renderApp(`/overview/batches/${BATCH.id}`, { contracts: AS_OWNER });
    await screen.findByRole("table", { name: "Transactions in this batch" });
    expect(screen.getByRole("link", { name: "Back to batches" })).toHaveAttribute(
      "href",
      "/overview/batches",
    );
    expect(screen.queryByRole("button", { name: /Flag|Sign off/ })).toBeNull();
  });

  it("shows review periods with no Change button", async () => {
    renderApp("/head/review-periods", { contracts: AS_HEAD });
    await screen.findByRole("table", { name: "Review periods" });
    expect(screen.getByText("Only the Licensing Authority can change review periods.")).toBeVisible();
    expect(screen.queryByRole("button", { name: /Change/ })).toBeNull();
  });

  it("links licences to the role's own licence screen", async () => {
    renderApp("/overview/licences", { contracts: AS_OWNER });
    const table = await screen.findByRole("table", { name: "Licences" });
    const link = within(table).getAllByRole("link")[0]!;
    expect(link.getAttribute("href")).toMatch(/^\/overview\/licences\/\d+$/);
  });
});
