import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { App } from "./App";

describe("App", () => {
  it("renders the app name and, signed in, the role's home", async () => {
    render(<App />);
    const banner = await screen.findByRole("banner");
    expect(within(banner).getByText("Gujarat Restricted Goods")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { level: 1, name: "Home" })).toBeInTheDocument();
    expect(window.location.pathname).toBe("/licensee");
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<App />);
    await screen.findByRole("heading", { level: 1 });
    expect(await axe(container)).toHaveNoViolations();
  });
});
