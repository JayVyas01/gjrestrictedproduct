import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { App } from "./App";

describe("App", () => {
  it("renders the app name", async () => {
    render(<App />);
    expect(
      await screen.findByRole("heading", { level: 1, name: "Gujarat Restricted Goods" }),
    ).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<App />);
    await screen.findByRole("heading", { level: 1 });
    expect(await axe(container)).toHaveNoViolations();
  });
});
