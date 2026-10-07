import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { DemoSignupCandidate } from "@/api/types";
import { contract, serveDemo } from "@/test/handlers";
import { renderApp } from "@/test/render";
import { server } from "@/test/server";

const [CANDIDATE] = contract<DemoSignupCandidate[]>("demo_signup_candidates");
const NO_MATCH = contract<{ detail: string }>("error_401_signup_failed").detail;
const HINT = "Your code is in the Demo SMS inbox.";

/** A demo; records what each sign-up step posted. */
function serveSignup() {
  const posted: Record<string, unknown>[] = [];
  server.use(...serveDemo());
  server.use(
    http.post("/api/demo/signup/start", async ({ request }) => {
      posted.push((await request.json()) as Record<string, unknown>);
      return HttpResponse.json(contract<object>("demo_signup_start"));
    }),
    http.post("/api/demo/signup/complete", async ({ request }) => {
      posted.push((await request.json()) as Record<string, unknown>);
      return HttpResponse.json(contract<object>("demo_signup_complete"), { status: 201 });
    }),
  );
  return posted;
}

type User = ReturnType<typeof renderApp>["user"];

async function pickAndFill(user: User, { confirm = "our-own-pass-2026" } = {}) {
  const picker = await screen.findByRole("region", { name: "Pick a demo business" });
  await user.click(
    within(picker).getByRole("button", { name: new RegExp(`Use ${CANDIDATE!.business_name}`) }),
  );
  await user.type(screen.getByLabelText("Email"), "owner@kheda.example");
  await user.type(screen.getByLabelText("Address"), "Station Road, Kheda");
  await user.type(screen.getByLabelText("Password"), "our-own-pass-2026");
  await user.type(screen.getByLabelText("Confirm the password"), confirm);
  await user.click(screen.getByRole("button", { name: "Continue" }));
}

describe("SignUpPage", () => {
  it("is for demos only: elsewhere it sends the visitor to sign-in", async () => {
    const { router } = renderApp("/sign-up", { signedOut: true });
    await waitFor(() => expect(router.state.location.pathname).toBe("/sign-in"));
  });

  it("a picked business fills the GSTIN, the phone on file and the name", async () => {
    serveSignup();
    const { user } = renderApp("/sign-up", { signedOut: true });
    const picker = await screen.findByRole("region", { name: "Pick a demo business" });
    await user.click(within(picker).getByRole("button", { name: /Use Kheda Traders/ }));
    expect(screen.getByLabelText("GSTIN")).toHaveValue(CANDIDATE!.gstin);
    expect(screen.getByLabelText("Mobile number on file")).toHaveValue(CANDIDATE!.phone_on_file);
    expect(screen.getByLabelText("Business name")).toHaveValue(CANDIDATE!.business_name);
  });

  it("signs up with the code, then offers sign-in as Party with the GSTIN", async () => {
    const posted = serveSignup();
    const { user, router } = renderApp("/sign-up", { signedOut: true });
    await pickAndFill(user);

    expect(await screen.findByText(HINT)).toBeInTheDocument();
    await user.click(screen.getByLabelText("Digit 1 of 6"));
    await user.paste("123456");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(
      await screen.findByText(
        `Your account is ready. Sign in as Party with GSTIN ${CANDIDATE!.gstin}.`,
      ),
    ).toBeInTheDocument();
    expect(posted).toEqual([
      {
        gstin: CANDIDATE!.gstin,
        phone: CANDIDATE!.phone_on_file,
        email: "owner@kheda.example",
        business_name: CANDIDATE!.business_name,
        address: "Station Road, Kheda",
        password: "our-own-pass-2026",
      },
      {
        challenge_id: contract<{ challenge_id: string }>("demo_signup_start").challenge_id,
        code: "123456",
      },
    ]);

    await user.click(screen.getByRole("button", { name: "Go to sign in" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/sign-in"));
    expect(router.state.location.search).toBe(""); // the GSTIN travels in router state only
    expect(await screen.findByLabelText("GSTIN")).toHaveValue(CANDIDATE!.gstin);
    expect(screen.getByRole("radio", { name: "Party" })).toBeChecked();
  });

  it("checks every field before calling the server", async () => {
    const posted = serveSignup();
    const { user } = renderApp("/sign-up", { signedOut: true });
    await user.click(await screen.findByRole("button", { name: "Continue" }));
    expect(screen.getByLabelText("GSTIN")).toHaveAccessibleDescription(
      expect.stringContaining("Enter the GSTIN."),
    );
    expect(screen.getByLabelText("Email")).toHaveAccessibleDescription("Enter an email address.");
    expect(screen.getByLabelText("Address")).toHaveAccessibleDescription("Enter the address.");
    await pickAndFill(user, { confirm: "something-else" });
    expect(screen.getByLabelText("Confirm the password")).toHaveAccessibleDescription(
      "The two passwords don't match.",
    );
    expect(posted).toEqual([]);
  });

  it("shows the server's one answer when nothing matches", async () => {
    serveSignup();
    server.use(
      http.post("/api/demo/signup/start", () =>
        HttpResponse.json(contract<object>("error_401_signup_failed"), { status: 401 }),
      ),
    );
    const { user } = renderApp("/sign-up", { signedOut: true });
    await pickAndFill(user);
    expect(await screen.findByRole("alert")).toHaveTextContent(NO_MATCH);
  });

  it("puts a 400 on the field it names", async () => {
    serveSignup();
    server.use(
      http.post("/api/demo/signup/start", () =>
        HttpResponse.json({ password: ["This password is too common."] }, { status: 400 }),
      ),
    );
    const { user } = renderApp("/sign-up", { signedOut: true });
    await pickAndFill(user);
    await waitFor(() =>
      expect(screen.getByLabelText("Password")).toHaveAccessibleDescription(
        expect.stringContaining("This password is too common."),
      ),
    );
  });

  it("has no accessibility violations on the details or the code step", async () => {
    serveSignup();
    const { container, user } = renderApp("/sign-up", { signedOut: true });
    await screen.findByRole("region", { name: "Pick a demo business" });
    expect(await axe(container)).toHaveNoViolations();
    await pickAndFill(user);
    await screen.findByText(HINT);
    expect(await axe(container)).toHaveNoViolations();
  });
});
