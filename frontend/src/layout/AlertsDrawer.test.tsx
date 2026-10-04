import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { Alert, AlertList, Home } from "@/api/types";
import { contract, serveContract } from "@/test/handlers";
import { renderApp } from "@/test/render";
import { server } from "@/test/server";

const AS_OFFICER = ["me_personnel", "home_personnel"];
const LIST = contract<AlertList>("alerts");
const ALERT = LIST.alerts[0]!;

type User = ReturnType<typeof renderApp>["user"];

async function openDrawer(user: User) {
  await user.click(await screen.findByRole("button", { name: /^Alerts, \d+ unacknowledged$/ }));
  return screen.findByRole("dialog", { name: "Alerts" });
}

// The server's state: acknowledging flips the alert and drops the home count.
function serveAcknowledging() {
  let acknowledged = false;
  const notes: unknown[] = [];
  server.use(
    http.get("/api/alerts", () => {
      const alert: Alert = acknowledged
        ? { ...ALERT, acknowledged: true, acknowledged_at: ALERT.created_at, note: "Called the seller" }
        : ALERT;
      return HttpResponse.json({ unacknowledged: acknowledged ? 0 : 1, alerts: [alert] });
    }),
    http.get("/api/home", () => {
      const home = contract<Home>("home_personnel");
      home.counts.unacknowledged_alerts = acknowledged ? 0 : 1;
      return HttpResponse.json(home);
    }),
    http.post("/api/alerts/:id/acknowledge", async ({ request, params }) => {
      notes.push({ id: params.id, ...((await request.json()) as object) });
      acknowledged = true;
      return HttpResponse.json(contract<object>("alert_acknowledged"));
    }),
  );
  return notes;
}

describe("AlertsDrawer", () => {
  it("lists each alert with its kind, reference, goods, parties, reason and pattern", async () => {
    const { user } = renderApp("/personnel", { contracts: AS_OFFICER });
    const drawer = await openDrawer(user);
    const item = (await within(drawer).findAllByRole("listitem"))[0]!;
    expect(within(item).getByText("Buyer rejected a transaction")).toBeInTheDocument();
    expect(within(item).getByRole("link", { name: ALERT.transaction_reference })).toHaveAttribute(
      "href",
      `/personnel/transactions/${ALERT.transaction_reference}`,
    );
    expect(item).toHaveTextContent("Whisky, 10 L");
    expect(
      within(item).getByText("Sanand Spirits Pvt Ltd to Bopal Bar & Kitchen"),
    ).toBeInTheDocument();
    expect(within(item).getByText("Reason: I did not place this order")).toBeInTheDocument();
    expect(within(item).getByText(ALERT.pattern!)).toBeInTheDocument();
    // The first rejection is not a repeat.
    expect(within(item).queryByText("Repeat")).not.toBeInTheDocument();
    expect(within(item).getByRole("button", { name: "Acknowledge" })).toBeInTheDocument();
    expect(await axe(document.body)).toHaveNoViolations();
  });

  it("highlights a repeated pattern and shows the comment", async () => {
    const repeat: Alert = {
      ...ALERT,
      pattern_count: 3,
      pattern: "3rd buyer rejection for this seller in the last 30 days",
      comment: "Driver had no papers",
    };
    server.use(
      http.get("/api/alerts", () => HttpResponse.json({ unacknowledged: 1, alerts: [repeat] })),
    );
    const { user } = renderApp("/personnel", { contracts: AS_OFFICER });
    const drawer = await openDrawer(user);
    const pattern = await within(drawer).findByText(repeat.pattern!);
    expect(within(drawer).getByText("Repeat")).toBeInTheDocument();
    expect(pattern.closest("[data-repeat]")).toHaveAttribute("data-repeat", "true");
    expect(within(drawer).getByText("Comment: Driver had no papers")).toBeInTheDocument();
    expect(await axe(document.body)).toHaveNoViolations();
  });

  it("acknowledges with an optional note, and the bell count drops", async () => {
    const posts = serveAcknowledging();
    const { user } = renderApp("/personnel", { contracts: AS_OFFICER });
    const drawer = await openDrawer(user);
    await user.click(await within(drawer).findByRole("button", { name: "Acknowledge" }));
    const note = within(drawer).getByLabelText("Note (optional)");
    expect(note).toHaveAttribute("maxlength", "500");
    await user.type(note, "Called the seller");
    expect(await axe(document.body)).toHaveNoViolations();
    await user.click(within(drawer).getByRole("button", { name: "Acknowledge alert" }));

    expect(await screen.findByText("Alert acknowledged.")).toBeInTheDocument();
    expect(posts).toEqual([{ id: String(ALERT.id), note: "Called the seller" }]);
    expect(await within(drawer).findByText("Note: Called the seller")).toBeInTheDocument();
    expect(within(drawer).queryByRole("button", { name: "Acknowledge" })).not.toBeInTheDocument();
    expect(
      await screen.findByRole("button", { name: "Alerts, 0 unacknowledged", hidden: true }),
    ).toBeInTheDocument();
  });

  it("acknowledges without a note", async () => {
    const posts = serveAcknowledging();
    const { user } = renderApp("/personnel", { contracts: AS_OFFICER });
    const drawer = await openDrawer(user);
    await user.click(await within(drawer).findByRole("button", { name: "Acknowledge" }));
    await user.click(within(drawer).getByRole("button", { name: "Acknowledge alert" }));
    await screen.findByText("Alert acknowledged.");
    expect(posts).toEqual([{ id: String(ALERT.id), note: "" }]);
  });

  it("shows the server's message when the alert was already acknowledged", async () => {
    server.use(
      serveContract("error_409_conflict", {
        method: "post",
        path: "/api/alerts/:id/acknowledge",
      }),
    );
    const { user } = renderApp("/personnel", { contracts: AS_OFFICER });
    const drawer = await openDrawer(user);
    await user.click(await within(drawer).findByRole("button", { name: "Acknowledge" }));
    await user.click(within(drawer).getByRole("button", { name: "Acknowledge alert" }));
    expect(await within(drawer).findByRole("alert")).toHaveTextContent(
      "This alert is already acknowledged.",
    );
  });

  it("closes when the reference is followed", async () => {
    const { user, router } = renderApp("/personnel", { contracts: AS_OFFICER });
    const drawer = await openDrawer(user);
    await user.click(
      await within(drawer).findByRole("link", { name: ALERT.transaction_reference }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(router.state.location.pathname).toBe(
      `/personnel/transactions/${ALERT.transaction_reference}`,
    );
  });

  it("takes focus and closes on Escape", async () => {
    const { user } = renderApp("/personnel", { contracts: AS_OFFICER });
    const drawer = await openDrawer(user);
    await waitFor(() => expect(drawer).toContainElement(document.activeElement as HTMLElement));
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("says when there are no alerts", async () => {
    server.use(http.get("/api/alerts", () => HttpResponse.json({ unacknowledged: 0, alerts: [] })));
    const { user } = renderApp("/personnel", { contracts: AS_OFFICER });
    const drawer = await openDrawer(user);
    expect(await within(drawer).findByText("No alerts")).toBeInTheDocument();
  });

  it("is read-only for the Head Authority", async () => {
    const { user } = renderApp("/head", {
      contracts: ["me_head_authority", "home_head_authority"],
    });
    const drawer = await openDrawer(user);
    await within(drawer).findByText("Buyer rejected a transaction");
    expect(within(drawer).queryByRole("button", { name: "Acknowledge" })).not.toBeInTheDocument();
    expect(
      within(drawer).getByText("Only the officer holding the position can acknowledge an alert."),
    ).toBeInTheDocument();
    // No transaction screen for this role yet: the reference is plain text.
    expect(within(drawer).getByText(ALERT.transaction_reference)).toBeInTheDocument();
    expect(within(drawer).queryByRole("link", { name: ALERT.transaction_reference })).toBeNull();
    expect(await axe(document.body)).toHaveNoViolations();
  });
});
