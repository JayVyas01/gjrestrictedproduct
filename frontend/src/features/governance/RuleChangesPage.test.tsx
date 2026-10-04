import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { RuleChange } from "@/api/types";
import { contract } from "@/test/handlers";
import { renderApp } from "@/test/render";
import { server } from "@/test/server";

const AS_AUTHORITY = ["me_licensing_authority", "home_licensing_authority"];
const LISTED = contract<RuleChange[]>("rule_changes")[0]!;
const RULE_VERSION = contract<RuleChange>("rule_change_rule_version");

/** Records the `status` filter of every list request and answers with `rows`. */
function serveList(rows: RuleChange[]) {
  const asked: (string | null)[] = [];
  server.use(
    http.get("/api/rule-changes", ({ request }) => {
      const status = new URL(request.url).searchParams.get("status");
      asked.push(status);
      return HttpResponse.json(rows.filter((row) => !status || row.status === status));
    }),
  );
  return asked;
}

describe("RuleChangesPage", () => {
  it("lists the open changes with kind, scope, drafter, date and status", async () => {
    const withoutId: RuleChange = { ...RULE_VERSION, drafted_by: undefined };
    const asked = serveList([LISTED, withoutId]);
    const { container } = renderApp("/rule-changes", { contracts: AS_AUTHORITY });
    expect(
      await screen.findByRole("heading", { level: 1, name: "Rule changes" }),
    ).toBeInTheDocument();
    const table = await screen.findByRole("table", { name: "Rule changes" });
    expect(asked).toEqual(["SUBMITTED"]);
    expect(screen.getByRole("tab", { name: "Open", selected: true })).toBeInTheDocument();

    const rows = within(table).getAllByRole("row").slice(1);
    expect(within(rows[0]!).getByRole("link", { name: "New licence type" })).toHaveAttribute(
      "href",
      `/rule-changes/${LISTED.id}`,
    );
    expect(rows[0]).toHaveTextContent("Beer bar (BEER_BAR)");
    // The drafter's ID appears only when the server sends it (Head and Software Owner).
    expect(rows[0]).toHaveTextContent("Licensing Authority (GJKXZCP97TLW)");
    expect(rows[0]).toHaveTextContent("4 Oct 2026");
    expect(rows[0]).toHaveTextContent("Waiting for a decision");
    expect(rows[1]).toHaveTextContent("New rule version");
    expect(rows[1]).toHaveTextContent("Retail: Spirits (class)");
    expect(rows[1]).toHaveTextContent("Authorised Personnel");
    expect(rows[1]).not.toHaveTextContent("(GJ");

    expect(screen.getByRole("link", { name: "New rule change" })).toHaveAttribute(
      "href",
      "/rule-changes/new",
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("filters by status through the tabs, with an empty state", async () => {
    const asked = serveList([LISTED]);
    const { user, router } = renderApp("/rule-changes", { contracts: AS_AUTHORITY });
    await screen.findByRole("table", { name: "Rule changes" });
    await user.click(screen.getByRole("tab", { name: "Approved" }));
    expect(await screen.findByText("No rule changes here")).toBeInTheDocument();
    expect(router.state.location.search).toBe("?status=APPROVED");
    await waitFor(() => expect(asked).toEqual(["SUBMITTED", "APPROVED"]));
  });

  it("opens on the tab in the address", async () => {
    const asked = serveList([]);
    renderApp("/rule-changes?status=WITHDRAWN", { contracts: AS_AUTHORITY });
    expect(await screen.findByRole("tab", { name: "Withdrawn", selected: true })).toBeVisible();
    await waitFor(() => expect(asked).toEqual(["WITHDRAWN"]));
  });

  it("offers drafting only to drafters", async () => {
    serveList([LISTED]);
    renderApp("/rule-changes", { contracts: ["me_personnel", "home_personnel"] });
    await screen.findByRole("table", { name: "Rule changes" });
    expect(screen.queryByRole("link", { name: "New rule change" })).toBeNull();
  });

  it("is read-only for the Software Owner", async () => {
    serveList([LISTED]);
    const { container } = renderApp("/rule-changes", {
      contracts: ["me_software_owner", "home_software_owner"],
    });
    await screen.findByRole("table", { name: "Rule changes" });
    expect(screen.queryByRole("link", { name: "New rule change" })).toBeNull();
    expect(screen.getByText(/You can follow rule changes here/)).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });
});
