import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { Me, RuleChange } from "@/api/types";
import { contract } from "@/test/handlers";
import { renderApp } from "@/test/render";
import { server } from "@/test/server";

const AS_HEAD = ["me_head_authority", "home_head_authority"];
const AS_AUTHORITY = ["me_licensing_authority", "home_licensing_authority"];
const HEAD_ID = contract<Me>("me_head_authority").user_id;
const RULE_VERSION = contract<RuleChange>("rule_change_rule_version");
const NEW_TYPE = contract<RuleChange>("rule_change_new_licence_type");
const THRESHOLD = contract<RuleChange>("rule_change_threshold");
const DECIDED = contract<RuleChange>("rule_change_decided");
const CHALLENGE = contract<{ challenge_id: string }>("decision_code").challenge_id;

/** Serves `change` at its detail; the returned setter changes what later reads see. */
function serveChange(change: RuleChange) {
  let current = change;
  server.use(http.get("/api/rule-changes/:id", () => HttpResponse.json(current)));
  return (next: RuleChange) => {
    current = next;
  };
}

/** Records each decision's body and answers with `result` (and serves it from then on). */
function serveDecide(set: (next: RuleChange) => void, result: (body: { outcome: string; note?: string }) => RuleChange) {
  const bodies: unknown[] = [];
  server.use(
    http.post("/api/rule-changes/:id/decide", async ({ request }) => {
      const body = (await request.json()) as { outcome: string; note?: string };
      bodies.push(body);
      const decided = result(body);
      set(decided);
      return HttpResponse.json(decided);
    }),
  );
  return bodies;
}

type User = ReturnType<typeof renderApp>["user"];

async function enterCode(user: User) {
  const dialog = await screen.findByRole("dialog");
  await within(dialog).findByText(/The code expires in/);
  await user.click(within(dialog).getByLabelText("Digit 1 of 6"));
  await user.paste("123456");
  await user.click(within(dialog).getByRole("button", { name: "Confirm" }));
}

function compareRow(field: string): HTMLElement {
  const table = screen.getByRole("table", { name: "Current and proposed values" });
  return within(table).getByRole("rowheader", { name: field }).closest("tr")!;
}

const decidedAs = (outcome: "APPROVED" | "REJECTED", note: string | null): RuleChange => ({
  ...RULE_VERSION,
  status: outcome,
  status_label: outcome === "APPROVED" ? "Approved" : "Rejected",
  current: null,
  can_decide: false,
  decision: { outcome, decided_at: "2026-10-04T12:00:00+00:00", note },
});

describe("RuleChangePage", () => {
  it("compares current and proposed, marking each changed value in words", async () => {
    serveChange(RULE_VERSION);
    const { container } = renderApp(`/rule-changes/${RULE_VERSION.id}`, { contracts: AS_HEAD });
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: `New rule version (rule change ${RULE_VERSION.id})`,
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to rule changes" })).toHaveAttribute(
      "href",
      "/rule-changes",
    );
    expect(screen.getByText("Retail")).toBeInTheDocument();
    expect(screen.getByText("Spirits (class)")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Now (version 1)" })).toBeInTheDocument();

    const changed = ["May sell", "Stock limit", "Limit per transaction", "Validity"];
    for (const field of changed) {
      expect(compareRow(field)).toHaveAttribute("data-changed", "true");
      expect(within(compareRow(field)).getByText("Changed")).toBeInTheDocument();
    }
    for (const field of ["May buy", "May transport"]) {
      expect(compareRow(field)).not.toHaveAttribute("data-changed");
      expect(within(compareRow(field)).queryByText("Changed")).toBeNull();
    }
    expect(compareRow("Stock limit")).toHaveTextContent("1,000 L");
    expect(compareRow("Stock limit")).toHaveTextContent("2,000 L");
    expect(compareRow("May sell")).toHaveTextContent("YesNo");
    expect(compareRow("Validity")).toHaveTextContent("12 months24 months");

    expect(screen.getByText(RULE_VERSION.justification)).toBeInTheDocument();
    // The Head Authority sees the drafter's user ID.
    expect(screen.getByText("Authorised Personnel (GJTJ8M2CSMTK)")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("says a new licence type has nothing to compare", async () => {
    serveChange({ ...NEW_TYPE, can_withdraw: false });
    renderApp(`/rule-changes/${NEW_TYPE.id}`, { contracts: AS_AUTHORITY });
    expect(await screen.findByText("New, nothing to compare.")).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: /^Now/ })).toBeNull();
    expect(compareRow("Code")).toHaveTextContent("BEER_BAR");
    expect(compareRow("Code")).not.toHaveAttribute("data-changed");
    // Not the Head Authority or the Software Owner: the role only.
    const details = screen.getByRole("region", { name: "Details" });
    expect(within(details).getByText("Licensing Authority")).toBeInTheDocument();
    expect(details).not.toHaveTextContent("(GJ");
  });

  it("shows a threshold's change with its unit", async () => {
    serveChange(THRESHOLD);
    renderApp(`/rule-changes/${THRESHOLD.id}`, { contracts: AS_HEAD });
    const row = await waitFor(() => compareRow("Superintendent approves above"));
    expect(row).toHaveTextContent("200 L");
    expect(row).toHaveTextContent("500 L");
    expect(within(row).getByText("Changed")).toBeInTheDocument();
  });

  it("lets the Head Authority approve someone else's change with a code", async () => {
    const set = serveChange(RULE_VERSION);
    const bodies = serveDecide(set, () => decidedAs("APPROVED", null));
    const { user } = renderApp(`/rule-changes/${RULE_VERSION.id}`, { contracts: AS_HEAD });
    await user.click(await screen.findByRole("button", { name: "Approve" }));
    const dialog = await screen.findByRole("dialog", { name: "Approve this rule change" });
    await within(dialog).findByText(/The code expires in/);
    expect(await axe(document.body)).toHaveNoViolations();
    await enterCode(user);

    expect(await screen.findByText("You approved the rule change.")).toBeInTheDocument();
    expect(bodies).toEqual([{ challenge_id: CHALLENGE, code: "123456", outcome: "APPROVE" }]);
    const decision = await screen.findByRole("region", { name: "Decision" });
    expect(decision).toHaveTextContent("Approved");
    expect(decision).toHaveTextContent("No note.");
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
  });

  it("asks for a note of at least 10 characters before rejecting", async () => {
    const set = serveChange(RULE_VERSION);
    const bodies = serveDecide(set, (body) => decidedAs("REJECTED", body.note ?? null));
    const { user } = renderApp(`/rule-changes/${RULE_VERSION.id}`, { contracts: AS_HEAD });
    await user.click(await screen.findByRole("button", { name: "Reject" }));
    const note = screen.getByLabelText("Why are you rejecting it?");
    await user.type(note, "Too high");
    await user.click(screen.getByRole("button", { name: "Continue to reject" }));
    expect(await screen.findByText("Write at least 10 characters, up to 500.")).toBeInTheDocument();
    expect(note).toHaveAttribute("aria-invalid", "true");
    expect(screen.queryByRole("dialog")).toBeNull();

    await user.type(note, " for retail outlets.");
    await user.click(screen.getByRole("button", { name: "Continue to reject" }));
    expect(await screen.findByRole("dialog", { name: "Reject this rule change" })).toBeVisible();
    await enterCode(user);
    expect(await screen.findByText("You rejected the rule change.")).toBeInTheDocument();
    expect(bodies).toEqual([
      {
        challenge_id: CHALLENGE,
        code: "123456",
        outcome: "REJECT",
        note: "Too high for retail outlets.",
      },
    ]);
    expect(await screen.findByRole("region", { name: "Decision" })).toHaveTextContent(
      "Too high for retail outlets.",
    );
  });

  it("shows the server's text when the change was decided meanwhile (409)", async () => {
    serveChange(RULE_VERSION);
    const conflict = contract<{ detail: string }>("error_409_conflict");
    conflict.detail = "This change has already been decided.";
    server.use(
      http.post("/api/rule-changes/:id/decide", () => HttpResponse.json(conflict, { status: 409 })),
    );
    const { user } = renderApp(`/rule-changes/${RULE_VERSION.id}`, { contracts: AS_HEAD });
    await user.click(await screen.findByRole("button", { name: "Approve" }));
    await enterCode(user);
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(await screen.findByText("This change has already been decided.")).toBeInTheDocument();
  });

  it("offers no decision on the Head Authority's own draft, and says who decides", async () => {
    serveChange({ ...NEW_TYPE, drafted_by: HEAD_ID, drafted_by_role: "Head Authority" });
    const { container } = renderApp(`/rule-changes/${NEW_TYPE.id}`, { contracts: AS_HEAD });
    expect(
      await screen.findByText("Another Head Authority officer must decide this change."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Reject" })).toBeNull();
    expect(screen.getByRole("button", { name: "Withdraw" })).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("lets the drafter withdraw after confirming", async () => {
    const set = serveChange(NEW_TYPE);
    let withdrawn = 0;
    server.use(
      http.post("/api/rule-changes/:id/withdraw", () => {
        withdrawn += 1;
        const next: RuleChange = {
          ...NEW_TYPE,
          status: "WITHDRAWN",
          status_label: "Withdrawn",
          can_withdraw: false,
          decision: { outcome: "WITHDRAWN", decided_at: null, note: null },
        };
        set(next);
        return HttpResponse.json(next);
      }),
    );
    const { user } = renderApp(`/rule-changes/${NEW_TYPE.id}`, { contracts: AS_AUTHORITY });
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
    await user.click(await screen.findByRole("button", { name: "Withdraw" }));
    const dialog = await screen.findByRole("dialog", { name: "Withdraw this rule change?" });
    expect(await axe(document.body)).toHaveNoViolations();
    await user.click(within(dialog).getByRole("button", { name: "Keep it" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(withdrawn).toBe(0);

    await user.click(screen.getByRole("button", { name: "Withdraw" }));
    await user.click(
      within(await screen.findByRole("dialog")).getByRole("button", { name: "Yes, withdraw it" }),
    );
    expect(await screen.findByText("Rule change withdrawn.")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toHaveFocus());
    expect(withdrawn).toBe(1);
    expect(screen.getAllByText("Withdrawn").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Withdraw" })).toBeNull();
  });

  it("shows a decided change's decision and note, with no actions", async () => {
    serveChange(DECIDED);
    renderApp(`/rule-changes/${DECIDED.id}`, { contracts: AS_HEAD });
    const decision = await screen.findByRole("region", { name: "Decision" });
    expect(decision).toHaveTextContent("Approved");
    expect(decision).toHaveTextContent("Agreed with the district.");
    expect(screen.queryByRole("button", { name: /Approve|Reject|Withdraw/ })).toBeNull();
    expect(screen.queryByText("Another Head Authority officer must decide this change.")).toBeNull();
  });

  it("says when a change isn't there", async () => {
    renderApp("/rule-changes/abc", { contracts: AS_HEAD });
    expect(await screen.findByText("Not found, or not yours to see.")).toBeInTheDocument();
  });
});
