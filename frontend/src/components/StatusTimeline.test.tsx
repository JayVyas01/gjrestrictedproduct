import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { TimelineEvent, TransactionDetail } from "@/api/types";
import { contract } from "@/test/handlers";
import { renderWithProviders } from "@/test/render";
import { StatusTimeline } from "./StatusTimeline";

function timelineOf(name: string): TimelineEvent[] {
  return contract<TransactionDetail>(name).timeline;
}

describe("StatusTimeline", () => {
  it("shows each step's title, who acted, when (IST) and the holder for authorities", async () => {
    const { container } = renderWithProviders(
      <StatusTimeline events={timelineOf("transaction_detail_authority")} />,
    );
    const list = await screen.findByRole("list", { name: "Progress" });
    expect(list).toHaveAttribute("aria-live", "polite");
    const items = within(list).getAllByRole("listitem");
    expect(items.map((item) => item.querySelector("[data-title]")?.textContent)).toEqual([
      "Sale started",
      "Buyer confirmed",
      "Officer recommended approval",
      "Superintendent approved",
    ]);
    expect(items[2]).toHaveTextContent("Area Officer, Sanand");
    expect(items[2]).toHaveTextContent("Held by GJWX9P3LEP7L");
    expect(items[0]).toHaveTextContent("4 Oct 2026, 5:22 pm");
    expect(items[0]).not.toHaveTextContent("Held by");
    expect(await axe(container)).toHaveNoViolations();
  });

  it("shows the reason and comment of a rejection", async () => {
    const events: TimelineEvent[] = [
      ...timelineOf("transaction_detail_buyer").slice(0, 1),
      {
        step: "BUYER",
        outcome: "REJECT",
        at: "2026-10-04T12:00:00+00:00",
        by: "Buyer",
        reason: "Other",
        comment: "Ordered 200 L, not 250 L.",
        held_by: null,
      },
    ];
    renderWithProviders(<StatusTimeline events={events} />);
    const items = await screen.findAllByRole("listitem");
    expect(items[1]).toHaveTextContent("Buyer rejected");
    expect(items[1]).toHaveTextContent("Reason: Other");
    expect(items[1]).toHaveTextContent("Comment: Ordered 200 L, not 250 L.");
  });

  it("maps every step and outcome the server sends", async () => {
    const at = "2026-10-04T12:00:00+00:00";
    const pairs: [TimelineEvent["step"], TimelineEvent["outcome"], string][] = [
      ["SELLER", "CANCEL", "Seller cancelled the sale"],
      ["OFFICER", "APPROVE", "Officer approved"],
      ["OFFICER", "REJECT", "Officer rejected"],
      ["SUPERINTENDENT", "REJECT", "Superintendent rejected"],
    ];
    const events = pairs.map(([step, outcome]) => ({
      step,
      outcome,
      at,
      by: "Someone",
      reason: null,
      comment: null,
      held_by: null,
    }));
    renderWithProviders(<StatusTimeline events={events} />);
    const items = await screen.findAllByRole("listitem");
    expect(items.map((item) => item.querySelector("[data-title]")?.textContent)).toEqual(
      pairs.map(([, , title]) => title),
    );
  });

  it("shows the pending step greyed out after the events", async () => {
    const { container } = renderWithProviders(
      <StatusTimeline
        events={timelineOf("transaction_detail_superintendent_final")}
        pending="SUPERINTENDENT"
      />,
    );
    const items = await screen.findAllByRole("listitem");
    expect(items).toHaveLength(4);
    const pending = items[3]!;
    expect(pending).toHaveTextContent("Next: the superintendent's decision");
    expect(pending).toHaveAttribute("data-pending", "true");
    expect(await axe(container)).toHaveNoViolations();
  });
});
