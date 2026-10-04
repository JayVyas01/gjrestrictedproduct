import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { renderWithProviders } from "@/test/render";
import { formatQuantity, Qty } from "./Qty";

describe("Qty", () => {
  it("shows the value with its unit, trailing zeros dropped and Indian grouping", async () => {
    const { container } = renderWithProviders(<Qty value="150000.500" unit="L" />);
    expect(await screen.findByText("1,50,000.5 L")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("formats whole, fractional and zero quantities without losing precision", () => {
    expect(formatQuantity("1000.000")).toBe("1,000");
    expect(formatQuantity("250")).toBe("250");
    expect(formatQuantity("0.125")).toBe("0.125");
    expect(formatQuantity("12345678901234567.001")).toBe("12,34,56,78,90,12,34,567.001");
    expect(formatQuantity("-5.50")).toBe("-5.5");
  });

  it("shows anything that is not a decimal as is", () => {
    expect(formatQuantity("n/a")).toBe("n/a");
  });

  it("leaves the unit out when the scope has none (a class with mixed units)", async () => {
    renderWithProviders(<Qty value="500.000" unit={null} />);
    expect(await screen.findByText("500")).toBeInTheDocument();
  });
});
