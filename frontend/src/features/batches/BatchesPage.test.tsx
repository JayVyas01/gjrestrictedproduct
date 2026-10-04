import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { BatchSummary } from "@/api/types";
import { contract } from "@/test/handlers";
import { renderApp } from "@/test/render";
import { server } from "@/test/server";

const AS_SUPERINTENDENT = ["me_superintendent", "home_superintendent"];
const BATCH = contract<BatchSummary[]>("oversight_batches")[0]!;

/** The colour tone named on the badge around a status word. */
const toneOf = (word: HTMLElement) => word.closest("[data-tone]")?.getAttribute("data-tone");

function serveBatches(batches: BatchSummary[]) {
  server.use(http.get("/api/oversight/batches", () => HttpResponse.json(batches)));
}

describe("BatchesPage", () => {
  it("shows a card per batch with its period, due date, status and counts", async () => {
    serveBatches([
      { ...BATCH, id: 3 },
      { ...BATCH, id: 2, status: "OVERDUE", item_count: 4, flag_count: 2 },
      {
        ...BATCH,
        id: 1,
        status: "SIGNED",
        signed_by: "GJ5SVTKLEY5X",
        signed_at: "2026-10-01T06:30:00+00:00",
      },
    ]);
    const { container } = renderApp("/personnel/batches", { contracts: AS_SUPERINTENDENT });
    expect(await screen.findByRole("heading", { level: 1, name: "Batches" })).toBeInTheDocument();

    const cards = await screen.findAllByRole("listitem");
    expect(cards).toHaveLength(3);
    const [open, overdue, signed] = cards as [HTMLElement, HTMLElement, HTMLElement];

    expect(
      within(open).getByRole("link", { name: "14 Sept 2026 to 28 Sept 2026" }),
    ).toHaveAttribute("href", "/personnel/batches/3");
    expect(open).toHaveTextContent("District Officer, Ahmedabad");
    expect(open).toHaveTextContent("Due on 28 Oct 2026");
    expect(open).toHaveTextContent("1 transaction, 0 flags");
    expect(toneOf(within(open).getByText("Open"))).toBe("waiting");

    expect(toneOf(within(overdue).getByText("Overdue"))).toBe("rejected");
    expect(overdue).toHaveTextContent("4 transactions, 2 flags");

    expect(toneOf(within(signed).getByText("Signed"))).toBe("approved");
    expect(signed).toHaveTextContent("Signed by GJ5SVTKLEY5X on 1 Oct 2026");
    expect(await axe(container)).toHaveNoViolations();
  });

  it("says when there are no batches yet", async () => {
    serveBatches([]);
    const { container } = renderApp("/personnel/batches", { contracts: AS_SUPERINTENDENT });
    expect(await screen.findByText("No batches yet")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });
});
