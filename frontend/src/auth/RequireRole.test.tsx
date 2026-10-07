import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderApp } from "@/test/render";

const LANDINGS: [string, string[], string][] = [
  ["licensee", ["me_licensee", "home_licensee"], "/licensee"],
  ["officer", ["me_personnel", "home_personnel"], "/personnel"],
  ["superintendent", ["me_superintendent", "home_superintendent"], "/personnel"],
  ["licensing authority", ["me_licensing_authority", "home_licensing_authority"], "/authority"],
  ["head authority", ["me_head_authority", "home_head_authority"], "/head"],
  ["software owner", ["me_software_owner", "home_software_owner"], "/overview"],
];

describe("landing and RequireRole", () => {
  it.each(LANDINGS)("the %s lands on their home", async (_who, contracts, landing) => {
    const { router } = renderApp("/", { contracts });
    await waitFor(() => expect(router.state.location.pathname).toBe(landing));
    expect(await screen.findByRole("heading", { level: 1 })).toBeInTheDocument();
  });

  it("sends a signed-out visitor to sign-in, without an expiry notice", async () => {
    const { router } = renderApp("/licensee/transactions", { signedOut: true });
    await waitFor(() => expect(router.state.location.pathname).toBe("/sign-in"));
    expect(router.state.location.search).toBe("");
    expect(await screen.findByLabelText("GSTIN")).toBeInTheDocument();
  });

  it("sends the wrong role to their own home", async () => {
    const { router } = renderApp("/authority/licences");
    await waitFor(() => expect(router.state.location.pathname).toBe("/licensee"));
  });

  it("lets a role shared screen through (rule changes for personnel)", async () => {
    const { router } = renderApp("/rule-changes", {
      contracts: ["me_superintendent", "home_superintendent"],
    });
    expect(
      await screen.findByRole("heading", { level: 1, name: "Rule changes" }),
    ).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/rule-changes");
  });

  it("sends an unknown path home", async () => {
    const { router } = renderApp("/no-such-page");
    await waitFor(() => expect(router.state.location.pathname).toBe("/licensee"));
  });
});
