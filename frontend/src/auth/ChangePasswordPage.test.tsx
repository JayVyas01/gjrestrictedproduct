import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { contract } from "@/test/handlers";
import { renderApp } from "@/test/render";
import { server } from "@/test/server";

const RULE = contract<{ new_password: string[] }>("error_400_password_rules").new_password[0]!;

/** An officer whose password the system issued, until the new one is saved. */
function serveIssued() {
  const posted: Record<string, unknown>[] = [];
  let changed = false;
  server.use(
    http.get("/api/auth/me", () =>
      HttpResponse.json({ ...contract<object>("me_personnel"), must_change_password: !changed }),
    ),
    http.post("/api/auth/password", async ({ request }) => {
      posted.push((await request.json()) as Record<string, unknown>);
      changed = true;
      return HttpResponse.json(contract<object>("password_changed"));
    }),
  );
  return posted;
}

async function fill(
  user: ReturnType<typeof renderApp>["user"],
  {
    current = "issued-pass",
    next = "my-own-pass-2026",
    confirm,
  }: { current?: string; next?: string; confirm?: string } = {},
) {
  await user.type(await screen.findByLabelText("Current password"), current);
  await user.type(screen.getByLabelText("New password"), next);
  await user.type(screen.getByLabelText("Confirm the new password"), confirm ?? next);
  await user.click(screen.getByRole("button", { name: "Save the new password" }));
}

describe("ChangePasswordPage", () => {
  it("explains why, shows the rules, and lands on the role's home once saved", async () => {
    const posted = serveIssued();
    const { user, router } = renderApp("/change-password");
    expect(
      await screen.findByText(/The password you signed in with was issued to you/),
    ).toBeInTheDocument();
    expect(screen.getByText("be at least 12 characters long")).toBeInTheDocument();

    await fill(user);
    await waitFor(() => expect(router.state.location.pathname).toBe("/personnel"));
    expect(posted).toEqual([{ current_password: "issued-pass", new_password: "my-own-pass-2026" }]);
  });

  it("checks the fields before calling the server", async () => {
    const posted = serveIssued();
    const { user } = renderApp("/change-password");
    await user.click(await screen.findByRole("button", { name: "Save the new password" }));
    expect(screen.getByLabelText("Current password")).toHaveAccessibleDescription(
      "Enter your current password.",
    );
    expect(screen.getByLabelText("New password")).toHaveAccessibleDescription(
      "Enter a new password.",
    );
    await fill(user, { next: "short", confirm: "other" });
    expect(screen.getByLabelText("New password")).toHaveAccessibleDescription(
      "Use at least 12 characters.",
    );
    expect(screen.getByLabelText("Confirm the new password")).toHaveAccessibleDescription(
      "The two new passwords don't match.",
    );
    expect(posted).toEqual([]);
  });

  it("puts the server's 400 on the field it names", async () => {
    serveIssued();
    server.use(
      http.post("/api/auth/password", () =>
        HttpResponse.json(contract<object>("error_400_password_rules"), { status: 400 }),
      ),
    );
    const { user, router } = renderApp("/change-password");
    await fill(user, { next: "password1234", confirm: "password1234" });
    await waitFor(() =>
      expect(screen.getByLabelText("New password")).toHaveAccessibleDescription(RULE),
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/change-password");

    server.use(
      http.post("/api/auth/password", () =>
        HttpResponse.json(
          { current_password: ["Your current password is not correct."] },
          { status: 400 },
        ),
      ),
    );
    await user.click(screen.getByRole("button", { name: "Save the new password" }));
    await waitFor(() =>
      expect(screen.getByLabelText("Current password")).toHaveAccessibleDescription(
        "Your current password is not correct.",
      ),
    );
  });

  it("sends a signed-out visitor to sign-in", async () => {
    const { router } = renderApp("/change-password", { signedOut: true });
    await waitFor(() => expect(router.state.location.pathname).toBe("/sign-in"));
  });

  it("has no accessibility violations", async () => {
    serveIssued();
    const { container } = renderApp("/change-password");
    await screen.findByLabelText("Current password");
    expect(await axe(container)).toHaveNoViolations();
  });
});
