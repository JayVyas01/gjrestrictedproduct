import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { Home } from "@/api/types";
import { contract } from "@/test/handlers";
import { renderApp } from "@/test/render";
import { server } from "@/test/server";

const AS_HEAD = ["me_head_authority", "home_head_authority"];
const AS_OWNER = ["me_software_owner", "home_software_owner"];

function serveCounts(name: string, counts: Home["counts"]) {
  const home = contract<Home>(name);
  home.counts = { ...home.counts, ...counts };
  server.use(http.get("/api/home", () => HttpResponse.json(home)));
}

describe("OverviewHomePage", () => {
  it("tells the Head Authority what waits, with a link to each read-only list", async () => {
    serveCounts("home_head_authority", {
      rule_changes_awaiting_you: 2,
      your_open_rule_changes: 1,
      unacknowledged_alerts: 3,
      awaiting_superintendent: 4,
    });
    const { user, container } = renderApp("/head", { contracts: AS_HEAD });
    expect(await screen.findByRole("heading", { level: 1, name: "Home" })).toBeInTheDocument();
    expect(await screen.findByText("2 rule changes wait for your approval.")).toBeInTheDocument();
    expect(screen.getByText("1 of your rule changes is waiting for a decision.")).toBeInTheDocument();
    expect(screen.getByText("3 unacknowledged alerts.")).toBeInTheDocument();
    expect(
      screen.getByText("4 transactions wait for a superintendent's final approval."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Review rule changes" })).toHaveAttribute(
      "href",
      "/rule-changes",
    );
    expect(screen.getByRole("link", { name: "View transactions" })).toHaveAttribute(
      "href",
      "/head/transactions",
    );

    const links = screen.getByRole("region", { name: "Go to" });
    for (const [name, href] of [
      ["Rule changes", "/rule-changes"],
      ["Transactions", "/head/transactions"],
      ["Batches", "/head/batches"],
      ["Review periods", "/head/review-periods"],
      ["Licences", "/head/licences"],
    ]) {
      expect(within(links).getByRole("link", { name })).toHaveAttribute("href", href);
    }
    expect(await axe(container)).toHaveNoViolations();

    await user.click(screen.getByRole("button", { name: "Open alerts" }));
    expect(await screen.findByRole("dialog", { name: "Alerts" })).toBeInTheDocument();
  });

  it("gives the Software Owner the same lists under their own path, and no rule-change line", async () => {
    serveCounts("home_software_owner", { unacknowledged_alerts: 1, awaiting_superintendent: 0 });
    const { user, container } = renderApp("/overview", { contracts: AS_OWNER });
    expect(
      await screen.findByRole("heading", { level: 1, name: "Overview" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("1 unacknowledged alert.")).toBeInTheDocument();
    expect(screen.queryByText(/wait for your approval/)).toBeNull();
    const links = screen.getByRole("region", { name: "Go to" });
    expect(within(links).getByRole("link", { name: "Transactions" })).toHaveAttribute(
      "href",
      "/overview/transactions",
    );
    expect(within(links).getByRole("link", { name: "Licences" })).toHaveAttribute(
      "href",
      "/overview/licences",
    );
    expect(await axe(container)).toHaveNoViolations();
    await user.click(within(links).getByRole("button", { name: "View alerts" }));
    expect(await screen.findByRole("dialog", { name: "Alerts" })).toBeInTheDocument();
  });

  it("says when nothing waits", async () => {
    serveCounts("home_head_authority", {
      rule_changes_awaiting_you: 0,
      your_open_rule_changes: 0,
      unacknowledged_alerts: 0,
      awaiting_superintendent: 0,
    });
    renderApp("/head", { contracts: AS_HEAD });
    expect(await screen.findByText("Nothing waits for you.")).toBeInTheDocument();
  });
});
