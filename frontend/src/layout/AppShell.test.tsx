import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { renderApp } from "@/test/render";

const OFFICER = ["me_personnel", "home_personnel"];

describe("AppShell", () => {
  it("shows the app name, who is signed in, a skip link and the licensee's links", async () => {
    renderApp("/licensee");
    const banner = await screen.findByRole("banner");
    expect(within(banner).getByText("Gujarat Restricted Goods")).toBeInTheDocument();
    expect(await within(banner).findByText("Sanand Spirits Pvt Ltd")).toBeInTheDocument();
    expect(within(banner).getByText("Licensee")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Skip to main content" })).toHaveAttribute(
      "href",
      "#main",
    );
    expect(screen.getByRole("main")).toHaveAttribute("id", "main");

    const nav = screen.getByRole("navigation", { name: "Main navigation" });
    const links = within(nav).getAllByRole("link").map((link) => link.textContent);
    expect(links).toEqual(["Home", "Transactions", "New sale"]);
    expect(within(nav).getByRole("link", { name: "Home" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("has no bell for a licensee", async () => {
    renderApp("/licensee");
    await screen.findByText("Sanand Spirits Pvt Ltd");
    expect(screen.queryByRole("button", { name: /Alerts/ })).not.toBeInTheDocument();
  });

  it("shows the bell with the unacknowledged count to personnel and opens the drawer", async () => {
    const { user } = renderApp("/personnel", { contracts: OFFICER });
    const bell = await screen.findByRole("button", { name: "Alerts, 1 unacknowledged" });
    await user.click(bell);
    expect(await screen.findByRole("dialog", { name: "Alerts" })).toBeInTheDocument();
  });

  it("shows the bell to the Head Authority", async () => {
    renderApp("/head", { contracts: ["me_head_authority", "home_head_authority"] });
    expect(await screen.findByRole("button", { name: /^Alerts/ })).toBeInTheDocument();
  });

  it("gives a superintendent the batch and rule-change links", async () => {
    renderApp("/personnel", { contracts: ["me_superintendent", "home_superintendent"] });
    const nav = await screen.findByRole("navigation", { name: "Main navigation" });
    expect(await within(nav).findByRole("link", { name: "Batches" })).toBeInTheDocument();
    const links = within(nav).getAllByRole("link").map((link) => link.textContent);
    expect(links).toEqual(["Home", "Transactions", "Batches", "Rule changes"]);
  });

  it("gives an area officer no batch links", async () => {
    renderApp("/personnel", { contracts: OFFICER });
    const nav = await screen.findByRole("navigation", { name: "Main navigation" });
    await screen.findByText("Area Officer, Sanand", { selector: "header *" });
    expect(within(nav).getAllByRole("link").map((link) => link.textContent)).toEqual([
      "Home",
      "Transactions",
    ]);
  });

  it("has a burger to open the navigation on small screens", async () => {
    renderApp("/licensee");
    expect(
      await screen.findByRole("button", { name: "Open navigation" }),
    ).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    const { container } = renderApp("/personnel", { contracts: OFFICER });
    await screen.findByRole("button", { name: "Alerts, 1 unacknowledged" });
    expect(await axe(container)).toHaveNoViolations();
  });
});
