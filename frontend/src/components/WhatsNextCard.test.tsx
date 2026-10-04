import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { renderWithProviders } from "@/test/render";
import { WhatsNextCard } from "./WhatsNextCard";

describe("WhatsNextCard", () => {
  it("shows the title, the sentence and one action that navigates", async () => {
    const { container, user, router } = renderWithProviders(
      <WhatsNextCard
        title="What's next"
        body="2 sales are waiting for your decision."
        action={{ label: "Review them", to: "/personnel/transactions" }}
      />,
    );
    expect(await screen.findByRole("heading", { name: "What's next" })).toBeInTheDocument();
    expect(screen.getByText("2 sales are waiting for your decision.")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
    await user.click(screen.getByRole("link", { name: "Review them" }));
    expect(router.state.location.pathname).toBe("/personnel/transactions");
  });

  it("can run a callback instead", async () => {
    const onClick = vi.fn();
    const { user } = renderWithProviders(
      <WhatsNextCard
        title="What's next"
        body="Start a sale."
        action={{ label: "New sale", onClick }}
      />,
    );
    await user.click(await screen.findByRole("button", { name: "New sale" }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("has no button without an action", async () => {
    renderWithProviders(<WhatsNextCard title="What's next" body="Nothing needs you today." />);
    await screen.findByText("Nothing needs you today.");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
