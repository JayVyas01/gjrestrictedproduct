import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { renderWithProviders } from "@/test/render";
import { DateText } from "./DateText";

describe("DateText", () => {
  it("shows the date in IST (a UTC evening is the next day in India)", async () => {
    const { container } = renderWithProviders(<DateText iso="2026-10-04T20:00:00+00:00" />);
    const time = await screen.findByText("5 Oct 2026");
    expect(time.tagName).toBe("TIME");
    expect(time).toHaveAttribute("datetime", "2026-10-04T20:00:00+00:00");
    expect(await axe(container)).toHaveNoViolations();
  });

  it("adds the IST time when asked", async () => {
    renderWithProviders(<DateText iso="2026-10-04T11:52:18.867752+00:00" withTime />);
    expect(await screen.findByText("4 Oct 2026, 5:22 pm")).toBeInTheDocument();
  });

  it("shows a plain date as that calendar day", async () => {
    renderWithProviders(<DateText iso="2047-12-31" />);
    expect(await screen.findByText("31 Dec 2047")).toBeInTheDocument();
  });

  it("says Not set for a missing date", async () => {
    renderWithProviders(<DateText iso={null} />);
    expect(await screen.findByText("Not set")).toBeInTheDocument();
  });
});
