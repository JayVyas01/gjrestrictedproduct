import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { contract } from "@/test/handlers";
import { renderApp } from "@/test/render";
import { server } from "@/test/server";

const WRONG_CODE = "That code didn't match. Check the SMS or send a new code.";
const TOO_MANY = "Too many tries. Wait a minute and try again.";

// Signed out until the code is verified, as on the real server; records what was posted.
// (It serves `me` itself, so these tests don't pass `signedOut`, which would take precedence.)
function serveSignIn() {
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
      return HttpResponse.json(contract<object>("login_verify"));
    }),
    http.get("/api/auth/me", () =>
      signedIn
        ? HttpResponse.json(contract<object>("me_licensee"))
        : HttpResponse.json(contract<object>("error_403_not_signed_in"), { status: 403 }),
    ),
  );
  return posted;
}

async function passwordStep(user: ReturnType<typeof renderApp>["user"]) {
  await user.type(await screen.findByLabelText("User ID"), "GJK2PY48DX3B");
  await user.type(screen.getByLabelText("Password"), "a-password");
  await user.click(screen.getByRole("button", { name: "Continue" }));
  return screen.findByText(/Enter the 6-digit code/);
}

describe("SignInPage", () => {
  it("signs in with a password and a pasted code, then lands on the role's home", async () => {
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
      { user_id: "GJK2PY48DX3B", password: "a-password" },
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

  it("asks for both fields before calling the server", async () => {
    const { user } = renderApp("/sign-in", { signedOut: true });
    await user.click(await screen.findByRole("button", { name: "Continue" }));
    expect(screen.getByLabelText("User ID")).toHaveAccessibleDescription("Enter your user ID.");
    expect(screen.getByLabelText("Password")).toHaveAccessibleDescription("Enter your password.");
  });

  it("a wrong password shows the server's detail", async () => {
    server.use(
      http.post("/api/auth/login", () =>
        HttpResponse.json({ detail: "Invalid credentials" }, { status: 401 }),
      ),
    );
    const { user } = renderApp("/sign-in", { signedOut: true });
    await user.type(await screen.findByLabelText("User ID"), "GJK2PY48DX3B");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid credentials");
  });

  it("too many tries shows the wait text", async () => {
    server.use(http.post("/api/auth/login", () => new HttpResponse(null, { status: 429 })));
    const { user } = renderApp("/sign-in", { signedOut: true });
    await user.type(await screen.findByLabelText("User ID"), "GJK2PY48DX3B");
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
    expect(screen.getByLabelText("User ID")).toHaveValue("GJK2PY48DX3B");
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
    await screen.findByLabelText("User ID");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("has no accessibility violations on either step", async () => {
    serveSignIn();
    const { container, user } = renderApp("/sign-in?expired=1");
    await screen.findByLabelText("User ID");
    expect(await axe(container)).toHaveNoViolations();
    await passwordStep(user);
    expect(await axe(container)).toHaveNoViolations();
  });
});
