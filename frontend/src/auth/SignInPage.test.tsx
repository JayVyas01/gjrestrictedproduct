import { act, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { DemoPersona } from "@/api/types";
import { contract, serveDemo } from "@/test/handlers";
import { renderApp } from "@/test/render";
import { server } from "@/test/server";

const WRONG_CODE = "That code didn't match. Check the SMS or send a new code.";
const TOO_MANY = "Too many tries. Wait a minute and try again.";
const GSTIN = "99AAAAA0000A1Z5";
const ROLES = ["Party", "Licensing Authority", "Area Officer", "Superintendent", "Head Authority"];

// Signed out until the code is verified, as on the real server; records what was posted.
// (It serves `me` itself, so these tests don't pass `signedOut`, which would take precedence.)
function serveSignIn({ mustChange = false } = {}) {
  const posted: Record<string, unknown>[] = [];
  let signedIn = false;
  server.use(
    http.post("/api/auth/login", async ({ request }) => {
      posted.push((await request.json()) as Record<string, unknown>);
      return HttpResponse.json(contract<object>("login_start"));
    }),
    http.post("/api/auth/login/verify", async ({ request }) => {
      posted.push((await request.json()) as Record<string, unknown>);
      signedIn = true;
      const verified = { ...contract<object>("login_verify"), must_change_password: mustChange };
      return HttpResponse.json(verified);
    }),
    http.get("/api/auth/me", () =>
      signedIn
        ? HttpResponse.json({
            ...contract<object>("me_licensee"),
            must_change_password: mustChange,
          })
        : HttpResponse.json(contract<object>("error_403_not_signed_in"), { status: 403 }),
    ),
  );
  return posted;
}

async function passwordStep(user: ReturnType<typeof renderApp>["user"]) {
  await user.type(await screen.findByLabelText("GSTIN"), GSTIN.toLowerCase());
  await user.type(screen.getByLabelText("Password"), "a-password");
  await user.click(screen.getByRole("button", { name: "Continue" }));
  return screen.findByText(/Enter the 6-digit code/);
}

describe("SignInPage", () => {
  it("signs a party in with the GSTIN, a password and a pasted code, then lands on its home", async () => {
    const posted = serveSignIn();
    const { user, router } = renderApp("/sign-in");
    await passwordStep(user);

    // Focus moves to the code so the user can paste or type straight away.
    const first = screen.getByLabelText("Digit 1 of 6");
    await waitFor(() => expect(first).toHaveFocus());
    await user.paste("123456");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/licensee"));
    const challenge = contract<{ challenge_id: string }>("login_start").challenge_id;
    expect(posted).toEqual([
      { role: "PARTY", identifier: GSTIN, password: "a-password" }, // the GSTIN in capitals
      { challenge_id: challenge, code: "123456" },
    ]);
    expect(await screen.findByText("Sanand Spirits Pvt Ltd")).toBeInTheDocument();
  });

  it("a successful sign-in removes any draft left in the tab", async () => {
    serveSignIn();
    const { user, router } = renderApp("/sign-in");
    await passwordStep(user);
    sessionStorage.setItem("gj.draft.sale", JSON.stringify({ owner: "SOMEONE-ELSE" }));
    await user.click(screen.getByLabelText("Digit 1 of 6"));
    await user.paste("123456");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/licensee"));
    expect(sessionStorage.getItem("gj.draft.sale")).toBeNull();
  });

  it("asks for the role first: Party by default, then the GSTIN with its format", async () => {
    renderApp("/sign-in", { signedOut: true });
    const group = await screen.findByRole("radiogroup", { name: "Sign in as" });
    for (const role of ROLES)
      expect(within(group).getByRole("radio", { name: role })).toBeVisible();
    expect(within(group).getAllByRole("radio")).toHaveLength(ROLES.length);
    expect(within(group).getByRole("radio", { name: "Party" })).toBeChecked();
    expect(screen.getByLabelText("GSTIN")).toHaveAccessibleDescription(
      "Your business's 15-character GSTIN, for example 24ABCDE1234F1Z5.",
    );
    expect(screen.queryByLabelText("Email")).not.toBeInTheDocument();
  });

  it("asks for every field, and a GSTIN in its format, before calling the server", async () => {
    const posted = serveSignIn();
    const { user } = renderApp("/sign-in");
    await user.click(await screen.findByRole("button", { name: "Continue" }));
    expect(screen.getByLabelText("GSTIN")).toHaveAccessibleDescription(
      expect.stringContaining("Enter your GSTIN."),
    );
    expect(screen.getByLabelText("Password")).toHaveAccessibleDescription("Enter your password.");
    await user.type(screen.getByLabelText("GSTIN"), "24ABC");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(screen.getByLabelText("GSTIN")).toHaveAccessibleDescription(
      expect.stringContaining("Enter a 15-character GSTIN"),
    );
    expect(posted).toEqual([]);
  });

  it("an official signs in by email; an issued password goes to change-password first", async () => {
    const posted = serveSignIn({ mustChange: true });
    const { user, router } = renderApp("/sign-in");
    await user.type(await screen.findByLabelText("GSTIN"), GSTIN);
    await user.click(screen.getByRole("radio", { name: "Area Officer" }));
    // A GSTIN is no email: the identifier starts again.
    const email = screen.getByLabelText("Email");
    expect(email).toHaveValue("");
    expect(screen.queryByLabelText("GSTIN")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(email).toHaveAccessibleDescription("Enter your email.");

    await user.type(email, "officer.sanand@demo.gujarat.example");
    await user.type(screen.getByLabelText("Password"), "issued-pass");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.click(await screen.findByLabelText("Digit 1 of 6"));
    await user.paste("123456");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/change-password"));
    expect(posted[0]).toEqual({
      role: "AREA_OFFICER",
      identifier: "officer.sanand@demo.gujarat.example",
      password: "issued-pass",
    });
  });

  it("preselects Party and the GSTIN from sign-up's router state", async () => {
    renderApp("/sign-in", { signedOut: true, state: { role: "PARTY", identifier: GSTIN } });
    expect(await screen.findByLabelText("GSTIN")).toHaveValue(GSTIN);
    expect(screen.getByRole("radio", { name: "Party" })).toBeChecked();
  });

  it("a persona fills the role as well: an official's goes in with the email", async () => {
    const official: DemoPersona = {
      key: "officer",
      label: "Area Officer, Sanand",
      description: "Decides sales in Sanand.",
      role: "AREA_OFFICER",
      identifier: "officer.sanand@demo.gujarat.example",
      password: "issued-pass-123",
    };
    server.use(...serveDemo());
    server.use(http.get("/api/demo/personas", () => HttpResponse.json([official])));
    const posted = serveSignIn();
    const { user } = renderApp("/sign-in");
    await user.click(await screen.findByRole("button", { name: official.label }));
    await screen.findByText(/Enter the 6-digit code/);
    expect(posted).toEqual([
      { role: "AREA_OFFICER", identifier: official.identifier, password: official.password },
    ]);
    // Back for a new code: the role and email are kept.
    await user.click(screen.getByRole("button", { name: "Send a new code" }));
    expect(screen.getByRole("radio", { name: "Area Officer" })).toBeChecked();
    expect(screen.getByLabelText("Email")).toHaveValue(official.identifier);
  });

  it("offers sign-up in a demo only", async () => {
    server.use(...serveDemo());
    const { user, router } = renderApp("/sign-in", { signedOut: true });
    await user.click(await screen.findByRole("link", { name: "Sign up" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/sign-up"));
  });

  it("has no sign-up link outside a demo", async () => {
    renderApp("/sign-in", { signedOut: true });
    await screen.findByLabelText("GSTIN");
    await act(() => new Promise((resolve) => setTimeout(resolve, 50)));
    expect(screen.queryByRole("link", { name: "Sign up" })).not.toBeInTheDocument();
  });

  it("a wrong password shows the server's detail", async () => {
    server.use(
      http.post("/api/auth/login", () =>
        HttpResponse.json({ detail: "Invalid credentials" }, { status: 401 }),
      ),
    );
    const { user } = renderApp("/sign-in", { signedOut: true });
    await user.type(await screen.findByLabelText("GSTIN"), GSTIN);
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid credentials");
  });

  it("too many tries shows the wait text", async () => {
    server.use(http.post("/api/auth/login", () => new HttpResponse(null, { status: 429 })));
    const { user } = renderApp("/sign-in", { signedOut: true });
    await user.type(await screen.findByLabelText("GSTIN"), GSTIN);
    await user.type(screen.getByLabelText("Password"), "a-password");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(TOO_MANY);
  });

  it("a wrong code shows the 401 text, and Send a new code goes back to step 1", async () => {
    serveSignIn();
    server.use(
      http.post("/api/auth/login/verify", () =>
        HttpResponse.json(contract<object>("error_401_wrong_code"), { status: 401 }),
      ),
    );
    const { user, router } = renderApp("/sign-in");
    await passwordStep(user);
    await user.type(screen.getByLabelText("Digit 1 of 6"), "999999");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(WRONG_CODE);
    expect(router.state.location.pathname).toBe("/sign-in");
    // The error is linked to every digit, and the digits are marked invalid.
    for (const position of [1, 6]) {
      const digit = screen.getByLabelText(`Digit ${position} of 6`);
      expect(digit).toHaveAccessibleDescription(WRONG_CODE);
      expect(digit).toHaveAttribute("aria-invalid", "true");
    }

    await user.click(screen.getByRole("button", { name: "Send a new code" }));
    expect(screen.getByLabelText("GSTIN")).toHaveValue(GSTIN);
    expect(screen.getByLabelText("Password")).toHaveValue("");
  });

  it("shows the session-expired notice after ?expired=1", async () => {
    renderApp("/sign-in?expired=1", { signedOut: true });
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Your session ended after 15 minutes without activity. Sign in again.",
    );
  });

  it("has no expiry notice on a plain visit", async () => {
    renderApp("/sign-in", { signedOut: true });
    await screen.findByLabelText("GSTIN");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("has no accessibility violations on either step", async () => {
    serveSignIn();
    const { container, user } = renderApp("/sign-in?expired=1");
    await screen.findByLabelText("GSTIN");
    expect(await axe(container)).toHaveNoViolations();
    await passwordStep(user);
    expect(await axe(container)).toHaveNoViolations();
  });
});
