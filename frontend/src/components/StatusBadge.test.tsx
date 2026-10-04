import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { TransactionStatus } from "@/api/types";
import { renderWithProviders } from "@/test/render";
import { StatusBadge, statusTone } from "./StatusBadge";

describe("StatusBadge", () => {
  it("shows the status label", async () => {
    const { container } = renderWithProviders(<StatusBadge status="AWAITING_OFFICER" />);
    expect(await screen.findByText("Waiting for the officer")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("shows Awaiting you instead when the viewer can decide", async () => {
    renderWithProviders(<StatusBadge status="AWAITING_OFFICER" awaitingYou />);
    expect(await screen.findByText("Awaiting you")).toBeInTheDocument();
    expect(screen.queryByText("Waiting for the officer")).not.toBeInTheDocument();
  });

  it("gives each status its tone", () => {
    const tones: Record<TransactionStatus, string> = {
      AWAITING_BUYER: "waiting",
      AWAITING_OFFICER: "waiting",
      AWAITING_SUPERINTENDENT: "waiting",
      APPROVED: "approved",
      REJECTED_BY_BUYER: "rejected",
      REJECTED_BY_OFFICER: "rejected",
      REJECTED_BY_SUPERINTENDENT: "rejected",
      CANCELLED: "cancelled",
    };
    for (const [status, tone] of Object.entries(tones)) {
      expect(statusTone(status as TransactionStatus)).toBe(tone);
    }
  });

  it("labels a rejection in words, not colour alone", async () => {
    renderWithProviders(<StatusBadge status="REJECTED_BY_BUYER" />);
    expect(await screen.findByText("Rejected by the buyer")).toBeInTheDocument();
  });
});
