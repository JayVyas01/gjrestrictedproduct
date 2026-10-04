import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { renderWithProviders } from "@/test/render";
import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  it("shows the title, the body and an optional action", async () => {
    const { container } = renderWithProviders(
      <EmptyState
        title="No sales yet"
        body="Sales you start appear here."
        action={{ label: "New sale", to: "/licensee/sales/new" }}
      />,
    );
    expect(await screen.findByRole("heading", { name: "No sales yet" })).toBeInTheDocument();
    expect(screen.getByText("Sales you start appear here.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "New sale" })).toHaveAttribute(
      "href",
      "/licensee/sales/new",
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("works without an action", async () => {
    renderWithProviders(<EmptyState title="No alerts" body="You're all caught up." />);
    expect(await screen.findByText("You're all caught up.")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
