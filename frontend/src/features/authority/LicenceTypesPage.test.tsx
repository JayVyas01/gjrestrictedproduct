import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { LicenceType } from "@/api/types";
import { contract } from "@/test/handlers";
import { renderApp } from "@/test/render";
import { server } from "@/test/server";

const AS_AUTHORITY = ["me_licensing_authority", "home_licensing_authority"];

describe("LicenceTypesPage", () => {
  it("shows each type's rules in an accordion, and the approval thresholds", async () => {
    const types = contract<LicenceType[]>("catalogue_licence_types");
    types[0]!.description = "Shops selling to the public.";
    types[0]!.rules.push({
      ...types[0]!.rules[0]!,
      scope: "Whisky",
      scope_code: "WHISKY",
      scope_kind: "substance",
      may_sell: false,
      validity_months: 1,
      version: 3,
    });
    server.use(http.get("/api/catalogue/licence-types", () => HttpResponse.json(types)));
    const { user, container } = renderApp("/authority/licence-types", { contracts: AS_AUTHORITY });
    expect(
      await screen.findByRole("heading", { level: 1, name: "Licence types" }),
    ).toBeInTheDocument();

    const retail = await screen.findByRole("button", { name: /Retail/ });
    expect(screen.getByRole("button", { name: /Wholesale/ })).toBeInTheDocument();
    await user.click(retail);
    expect(await screen.findByText("Shops selling to the public.")).toBeVisible();
    const rules = screen.getByRole("table", { name: "Rules for Retail" });
    const [, spirits, whisky] = within(rules).getAllByRole("row");
    expect(spirits).toHaveTextContent("Spirits (class)");
    expect(spirits).toHaveTextContent("Buy, sell");
    expect(spirits).toHaveTextContent("1,000 L");
    expect(spirits).toHaveTextContent("500 L");
    expect(spirits).toHaveTextContent("12 months");
    expect(whisky).toHaveTextContent("Whisky (substance)");
    expect(whisky).toHaveTextContent("Buy");
    expect(whisky).not.toHaveTextContent("sell");
    expect(whisky).toHaveTextContent("1 month");
    expect(whisky).toHaveTextContent("3");

    const thresholds = screen.getByRole("table", { name: "Approval thresholds" });
    expect(within(thresholds).getByText("Spirits (class)")).toBeInTheDocument();
    expect(within(thresholds).getByText("200 L")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("says when there are no approval thresholds", async () => {
    server.use(http.get("/api/catalogue/approval-thresholds", () => HttpResponse.json([])));
    renderApp("/authority/licence-types", { contracts: AS_AUTHORITY });
    expect(
      await screen.findByText(
        "No approval thresholds yet, so the officer alone approves every sale.",
      ),
    ).toBeInTheDocument();
  });
});
