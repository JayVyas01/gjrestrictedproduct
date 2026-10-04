import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { ErrorBody, RuleChange } from "@/api/types";
import { contract } from "@/test/handlers";
import { renderApp } from "@/test/render";
import { server } from "@/test/server";

const AS_AUTHORITY = ["me_licensing_authority", "home_licensing_authority"];
const DRAFTED = contract<RuleChange>("rule_change_new_licence_type");
const WHY = "Retail outlets now stock beer in larger volumes.";

/** Records each draft's body and answers 201 with the drafted change. */
function serveDraft() {
  const bodies: unknown[] = [];
  server.use(
    http.post("/api/rule-changes", async ({ request }) => {
      bodies.push(await request.json());
      return HttpResponse.json(DRAFTED, { status: 201 });
    }),
  );
  return bodies;
}

type User = ReturnType<typeof renderApp>["user"];

async function pick(user: User, kind: string) {
  await user.click(await screen.findByRole("radio", { name: kind }));
}

const submit = () => screen.getByRole("button", { name: "Send for approval" });

describe("NewRuleChangePage", () => {
  it("drafts a new licence type: checks the fields, then sends and opens the change", async () => {
    const bodies = serveDraft();
    const { user, router, container } = renderApp("/rule-changes/new", {
      contracts: AS_AUTHORITY,
    });
    expect(
      await screen.findByRole("heading", { level: 1, name: "New rule change" }),
    ).toBeInTheDocument();
    await pick(user, "A new licence type");

    await user.click(submit());
    expect(
      await screen.findByText("Enter 2 to 32 capital letters, digits or underscores, starting with a letter."),
    ).toBeInTheDocument();
    expect(screen.getByText("Enter a name.")).toBeInTheDocument();
    expect(screen.getByText("Explain the change in 10 to 1000 characters.")).toBeInTheDocument();
    expect(screen.getByLabelText("Code")).toHaveAttribute("aria-invalid", "true");
    expect(bodies).toEqual([]);
    expect(await axe(container)).toHaveNoViolations();

    await user.type(screen.getByLabelText("Code"), "beer_bar");
    expect(screen.getByLabelText("Code")).toHaveValue("BEER_BAR");
    await user.type(screen.getByLabelText("Name"), "Beer bar");
    await user.type(screen.getByLabelText("Description (optional)"), "On-premises beer");
    await user.type(screen.getByLabelText("Justification"), WHY);
    expect(screen.getByText(/48 of 1000 characters/)).toBeInTheDocument();
    await user.click(submit());

    await waitFor(() => expect(router.state.location.pathname).toBe(`/rule-changes/${DRAFTED.id}`));
    expect(bodies).toEqual([
      {
        kind: "NEW_LICENCE_TYPE",
        payload: { code: "BEER_BAR", name: "Beer bar", description: "On-premises beer" },
        justification: WHY,
      },
    ]);
    expect(
      await screen.findByText("Rule change sent for a Head Authority decision."),
    ).toBeInTheDocument();
  });

  it("drafts a rule version: limits in the scope's unit, per-transaction at most the stock", async () => {
    const bodies = serveDraft();
    const { user, container } = renderApp("/rule-changes/new", { contracts: AS_AUTHORITY });
    await pick(user, "A licence type's rule for a substance or class");

    await user.click(submit());
    expect(await screen.findByText("Choose a licence type.")).toBeInTheDocument();
    expect(screen.getByText("Choose a substance class.")).toBeInTheDocument();
    expect(screen.getAllByText("Enter a quantity greater than 0, like 150 or 12.5.")).toHaveLength(2);
    expect(screen.getByText("Enter a whole number of months from 1 to 120.")).toBeInTheDocument();

    await user.selectOptions(await screen.findByLabelText("Licence type"), "RETAIL");
    await user.selectOptions(await screen.findByLabelText("Substance class"), "SPIRITS");
    await user.click(screen.getByLabelText("May buy"));
    await user.click(screen.getByLabelText("May sell"));
    await user.type(screen.getByLabelText("Stock limit in L"), "2000");
    await user.type(screen.getByLabelText("Limit per transaction in L"), "2500");
    await user.type(screen.getByLabelText("Validity in months"), "121");
    await user.type(screen.getByLabelText("Justification"), WHY);
    await user.click(submit());
    expect(
      await screen.findByText("The per-transaction limit can't be above the stock limit."),
    ).toBeInTheDocument();
    expect(screen.getByText("Enter a whole number of months from 1 to 120.")).toBeInTheDocument();
    expect(bodies).toEqual([]);
    expect(await axe(container)).toHaveNoViolations();

    await user.clear(screen.getByLabelText("Limit per transaction in L"));
    await user.type(screen.getByLabelText("Limit per transaction in L"), "300");
    await user.clear(screen.getByLabelText("Validity in months"));
    await user.type(screen.getByLabelText("Validity in months"), "24");
    await user.click(submit());
    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]).toEqual({
      kind: "RULE_VERSION",
      payload: {
        licence_type_code: "RETAIL",
        class_code: "SPIRITS",
        may_buy: true,
        may_sell: true,
        may_transport: false,
        max_stock_qty: "2000",
        max_per_transaction_qty: "300",
        validity_months: 24,
      },
      justification: WHY,
    });
  });

  it("drafts an approval threshold for one substance", async () => {
    const bodies = serveDraft();
    const { user } = renderApp("/rule-changes/new", { contracts: AS_AUTHORITY });
    await pick(user, "An approval threshold");
    await user.click(screen.getByLabelText("One substance"));
    await user.selectOptions(await screen.findByLabelText("Substance"), "WHISKY");
    await user.type(screen.getByLabelText("Superintendent approves above (in L)"), "500");
    await user.type(screen.getByLabelText("Justification"), WHY);
    await user.click(submit());
    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]).toEqual({
      kind: "APPROVAL_THRESHOLD",
      payload: { substance_code: "WHISKY", superintendent_above_qty: "500" },
      justification: WHY,
    });
  });

  it("shows the server's reasons when it refuses the draft (422)", async () => {
    const refused = contract<ErrorBody>("error_422_review_setting");
    refused.detail = "This rule change can't be saved.";
    refused.reasons = ["A licence type with code BEER_BAR already exists."];
    server.use(http.post("/api/rule-changes", () => HttpResponse.json(refused, { status: 422 })));
    const { user, router } = renderApp("/rule-changes/new", { contracts: AS_AUTHORITY });
    await pick(user, "A new licence type");
    await user.type(screen.getByLabelText("Code"), "BEER_BAR");
    await user.type(screen.getByLabelText("Name"), "Beer bar");
    await user.type(screen.getByLabelText("Justification"), WHY);
    await user.click(submit());
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("This rule change can't be saved.");
    expect(alert).toHaveTextContent("A licence type with code BEER_BAR already exists.");
    expect(router.state.location.pathname).toBe("/rule-changes/new");
  });

  it("tells personnel without a district position that they can't draft", async () => {
    renderApp("/rule-changes/new", { contracts: ["me_personnel", "home_personnel"] });
    expect(
      await screen.findByText(
        "Only the Licensing Authority, the Head Authority and officers holding a district position can draft rule changes.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("radio")).toBeNull();
  });

  it("lets a district officer draft", async () => {
    renderApp("/rule-changes/new", { contracts: ["me_superintendent", "home_superintendent"] });
    expect(await screen.findByRole("radio", { name: "A new licence type" })).toBeInTheDocument();
  });

  it("sends the Software Owner home: drafting isn't theirs", async () => {
    const { router } = renderApp("/rule-changes/new", {
      contracts: ["me_software_owner", "home_software_owner"],
    });
    await waitFor(() => expect(router.state.location.pathname).toBe("/overview"));
  });
});
