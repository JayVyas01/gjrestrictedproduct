import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { LicenceCard } from "@/api/types";
import { contract } from "@/test/handlers";
import { renderWithProviders } from "@/test/render";
import { PermissionCard } from "./PermissionCard";

function licence(changes: Partial<LicenceCard> = {}): LicenceCard {
  return { ...contract<LicenceCard[]>("licences_mine")[0]!, ...changes };
}

describe("PermissionCard", () => {
  it("shows the type and scope, the allowances in words, the limits and validity", async () => {
    const { container } = renderWithProviders(<PermissionCard licence={licence()} />);
    expect(await screen.findByRole("heading", { name: "Retail: Spirits" })).toBeInTheDocument();
    expect(screen.getByText("Licence GJ/TEST/0001")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    const allowances = screen.getByRole("list", { name: "What this licence allows" });
    expect(
      within(allowances)
        .getAllByRole("listitem")
        .map((item) => item.textContent),
    ).toEqual(["Can buy", "Can sell", "Cannot transport"]);
    // A class licence carries its class's unit (L for Spirits).
    expect(screen.getByText("1,000 L")).toBeInTheDocument();
    expect(screen.getByText("500 L")).toBeInTheDocument();
    expect(screen.getByText("1 Jan 2026")).toBeInTheDocument();
    expect(screen.getByText("31 Dec 2047")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("shows limits without a unit when the scope has none (a class with no substances)", async () => {
    renderWithProviders(<PermissionCard licence={licence({ unit: null })} />);
    expect(await screen.findByText("1,000")).toBeInTheDocument();
  });

  it("warns about a suspended licence", async () => {
    const { container } = renderWithProviders(
      <PermissionCard licence={licence({ status: "SUSPENDED", trading_permitted: false })} />,
    );
    expect(await screen.findByText(/This licence is suspended/)).toBeInTheDocument();
    expect(screen.getByText("Suspended")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("warns about a revoked licence", async () => {
    renderWithProviders(
      <PermissionCard licence={licence({ status: "REVOKED", trading_permitted: false })} />,
    );
    expect(await screen.findByText(/This licence has been revoked/)).toBeInTheDocument();
  });

  it("warns about an active licence outside its validity (expired)", async () => {
    renderWithProviders(
      <PermissionCard licence={licence({ trading_permitted: false, valid_to: "2025-12-31" })} />,
    );
    expect(await screen.findByText(/This licence is not valid today/)).toBeInTheDocument();
  });
});
