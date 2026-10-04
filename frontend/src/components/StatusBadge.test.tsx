import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { BatchStatus, ProposalStatus, TransactionStatus } from "@/api/types";
import { renderWithProviders } from "@/test/render";
import {
  BatchStatusBadge,
  ProposalStatusBadge,
  StatusBadge,
  batchTone,
  proposalTone,
  statusTone,
} from "./StatusBadge";

/** The colour tone named on the badge around a status word. */
const toneOf = (word: HTMLElement) => word.closest("[data-tone]")?.getAttribute("data-tone");

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

  it("words and colours a batch's status: open waits, overdue is red, signed green", async () => {
    const tones: Record<BatchStatus, string> = {
      OPEN: "waiting",
      OVERDUE: "rejected",
      SIGNED: "approved",
    };
    for (const [status, tone] of Object.entries(tones)) {
      expect(batchTone(status as BatchStatus)).toBe(tone);
    }
    const { container } = renderWithProviders(<BatchStatusBadge status="OVERDUE" />);
    expect(toneOf(await screen.findByText("Overdue"))).toBe("rejected");
    expect(await axe(container)).toHaveNoViolations();
  });

  it("words and colours a rule change's status: open waits, withdrawn is grey", async () => {
    const tones: Record<ProposalStatus, string> = {
      SUBMITTED: "waiting",
      APPROVED: "approved",
      REJECTED: "rejected",
      WITHDRAWN: "cancelled",
    };
    for (const [status, tone] of Object.entries(tones)) {
      expect(proposalTone(status as ProposalStatus)).toBe(tone);
    }
    const { container } = renderWithProviders(<ProposalStatusBadge status="SUBMITTED" />);
    expect(toneOf(await screen.findByText("Waiting for a decision"))).toBe("waiting");
    expect(await axe(container)).toHaveNoViolations();
  });
});
