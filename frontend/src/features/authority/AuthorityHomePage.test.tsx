import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { Home } from "@/api/types";
import { contract } from "@/test/handlers";
import { renderApp } from "@/test/render";
import { server } from "@/test/server";

const AS_AUTHORITY = ["me_licensing_authority", "home_licensing_authority"];

function serveCounts(counts: Home["counts"]) {
  const home = contract<Home>("home_licensing_authority");
  home.counts = { ...home.counts, ...counts };
  server.use(http.get("/api/home", () => HttpResponse.json(home)));
}

describe("AuthorityHomePage", () => {
  it("says what's next from the counts, with a link to each screen", async () => {
    serveCounts({
      expiring_licences_30d: 3,
      districts_without_review_period: 1,
      your_open_rule_changes: 2,
      rule_changes_submitted: 4,
    });
    const { container } = renderApp("/authority", { contracts: AS_AUTHORITY });
    expect(await screen.findByRole("heading", { level: 1, name: "Home" })).toBeInTheDocument();

    expect(await screen.findByText("3 licences expire within 30 days.")).toBeInTheDocument();
    expect(screen.getByText("1 district position has no review period.")).toBeInTheDocument();
    expect(screen.getByText("2 of your rule changes are waiting for a decision.")).toBeInTheDocument();
    expect(screen.getByText("4 rule changes wait for a Head Authority decision.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open the register" })).toHaveAttribute(
      "href",
      "/authority/licences",
    );
    expect(screen.getByRole("link", { name: "Set review periods" })).toHaveAttribute(
      "href",
      "/authority/review-periods",
    );

    const links = screen.getByRole("region", { name: "Go to" });
    for (const [name, href] of [
      ["Licences", "/authority/licences"],
      ["Licence types", "/authority/licence-types"],
      ["Review periods", "/authority/review-periods"],
      ["Rule changes", "/rule-changes"],
    ]) {
      expect(within(links).getByRole("link", { name })).toHaveAttribute("href", href);
    }
    expect(await axe(container)).toHaveNoViolations();
  });

  it("says when nothing waits", async () => {
    serveCounts({
      expiring_licences_30d: 0,
      districts_without_review_period: 0,
      your_open_rule_changes: 0,
      rule_changes_submitted: 0,
    });
    renderApp("/authority", { contracts: AS_AUTHORITY });
    expect(await screen.findByText("Nothing waits for you.")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Open the register" })).not.toBeInTheDocument();
  });
});
