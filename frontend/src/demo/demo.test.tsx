// Demo mode (D4 Task 4): the persona picker, the SMS inbox and the ribbon appear only when the
// server answers the persona list; outside demo mode (a 404) nothing demo-related renders.
import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import type { Challenge, DemoInboxMessage, DemoPersona } from "@/api/types";
import { CodeDialog } from "@/components/CodeDialog";
import { contract, serveDemo } from "@/test/handlers";
import { renderApp, renderWithProviders } from "@/test/render";
import { server } from "@/test/server";
import { DemoProvider } from "./DemoProvider";
import { SmsInboxButton } from "./SmsInboxButton";

const PICKER = "Demo: sign in as";
const OPEN_INBOX = "Open the Demo SMS inbox";
const RIBBON = "DEMO — synthetic data";
const HINT = "Your code is in the Demo SMS inbox.";
const EMPTY = "No messages yet. Codes appear here when the app sends them.";

const [SELLER] = contract<DemoPersona[]>("demo_personas");
const [MESSAGE] = contract<DemoInboxMessage[]>("demo_inbox");
const CHALLENGE = contract<Challenge>("login_start").challenge_id;

// Signed out until the code is verified; records what each sign-in step posted.
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

/** Counts the persona-list requests, answering 404 as outside demo mode. */
function serveNotADemo() {
  const asked = { count: 0 };
  server.use(
    http.get("/api/demo/personas", () => {
      asked.count += 1;
      return HttpResponse.json(contract<object>("error_404_not_found"), { status: 404 });
    }),
  );
  return asked;
}

/** Counts the inbox requests, answering with `messages`. */
function serveInbox(messages: DemoInboxMessage[] = [MESSAGE!]) {
  const asked = { count: 0 };
  server.use(
    http.get("/api/demo/inbox", () => {
      asked.count += 1;
      return HttpResponse.json(messages);
    }),
  );
  return asked;
}

afterEach(() => {
  vi.useRealTimers();
});

describe("outside demo mode (the persona list answers 404)", () => {
  it("shows no picker, inbox button or ribbon on sign-in, and asks only once", async () => {
    const asked = serveNotADemo();
    renderApp("/sign-in", { signedOut: true });
    await screen.findByLabelText("User ID");
    await waitFor(() => expect(asked.count).toBe(1));
    await act(() => new Promise((resolve) => setTimeout(resolve, 50)));
    expect(screen.queryByText(PICKER)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: OPEN_INBOX })).not.toBeInTheDocument();
    expect(screen.queryByText(RIBBON)).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(asked.count).toBe(1); // no retry
  });

  it("shows no ribbon or inbox button in the signed-in header", async () => {
    const asked = serveNotADemo();
    renderApp("/licensee");
    const banner = await screen.findByRole("banner");
    await within(banner).findByText("Sanand Spirits Pvt Ltd");
    await waitFor(() => expect(asked.count).toBe(1));
    expect(within(banner).queryByText(RIBBON)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: OPEN_INBOX })).not.toBeInTheDocument();
  });

  it("the code step has no demo hint", async () => {
    const asked = serveNotADemo();
    serveSignIn();
    const { user } = renderApp("/sign-in");
    await user.type(await screen.findByLabelText("User ID"), "GJK2PY48DX3B");
    await user.type(screen.getByLabelText("Password"), "a-password");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await screen.findByText(/Enter the 6-digit code/);
    expect(asked.count).toBe(1);
    expect(screen.queryByText(HINT)).not.toBeInTheDocument();
  });
});

describe("the persona picker", () => {
  it("lists the personas with their descriptions under the ribbon", async () => {
    server.use(...serveDemo());
    renderApp("/sign-in", { signedOut: true });
    const picker = await screen.findByRole("region", { name: PICKER });
    const buttons = within(picker).getAllByRole("button");
    expect(buttons.map((button) => button.getAttribute("aria-label"))).toEqual(["Seller", "Buyer"]);
    expect(within(picker).getByRole("button", { name: "Seller" })).toHaveAccessibleDescription(
      SELLER!.description,
    );
    expect(screen.getByText(RIBBON)).toBeInTheDocument();
  });

  it("fills the user ID and password, submits step 1, and the code step shows the hint", async () => {
    server.use(...serveDemo());
    const posted = serveSignIn();
    const { user } = renderApp("/sign-in");
    await user.click(await screen.findByRole("button", { name: "Seller" }));

    expect(await screen.findByText(HINT)).toBeInTheDocument();
    expect(posted).toEqual([{ user_id: SELLER!.user_id, password: SELLER!.password }]);
    // The picker belongs to step 1 only.
    expect(screen.queryByText(PICKER)).not.toBeInTheDocument();
  });

  it("passes axe on the sign-in page with the picker", async () => {
    server.use(...serveDemo());
    const { container } = renderApp("/sign-in", { signedOut: true });
    await screen.findByRole("region", { name: PICKER });
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("the SMS inbox", () => {
  it("lists each code with the name, the last 4 digits and the time, and announces the newest", async () => {
    server.use(...serveDemo());
    const older: DemoInboxMessage = {
      display_name: "Bopal Bar & Kitchen",
      contact_last4: "0202",
      code: "246810",
      created_at: "2026-10-04T05:00:00Z",
    };
    serveInbox([MESSAGE!, older]);
    const { user, container } = renderApp("/sign-in", { signedOut: true });
    await user.click(await screen.findByRole("button", { name: OPEN_INBOX }));

    const drawer = await screen.findByRole("dialog", { name: "Demo SMS inbox" });
    const items = await within(drawer).findAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(within(items[0]!).getByText(MESSAGE!.display_name)).toBeInTheDocument();
    expect(within(items[0]!).getByText(`••••${MESSAGE!.contact_last4}`)).toBeInTheDocument();
    expect(within(items[0]!).getByText(MESSAGE!.code)).toBeInTheDocument();
    expect(within(items[0]!).getByRole("time")).toHaveAttribute("dateTime", MESSAGE!.created_at);
    expect(within(items[1]!).getByText("246810")).toBeInTheDocument();
    // Never the full number.
    expect(drawer).not.toHaveTextContent(/98000/);

    const spoken = MESSAGE!.code.split("").join(" ");
    expect(within(drawer).getByRole("status")).toHaveTextContent(
      `Newest code ${spoken}, for ${MESSAGE!.display_name}.`,
    );
    expect(await axe(container.ownerDocument.body)).toHaveNoViolations();
  });

  it("says so when there are no messages", async () => {
    server.use(...serveDemo());
    serveInbox([]);
    const { user } = renderApp("/sign-in", { signedOut: true });
    await user.click(await screen.findByRole("button", { name: OPEN_INBOX }));
    expect(await screen.findByText(EMPTY)).toBeInTheDocument();
  });

  it("'Use this code' fills the code step, focuses Sign in, and the sign-in completes", async () => {
    server.use(...serveDemo());
    serveInbox();
    const posted = serveSignIn();
    const { user, router } = renderApp("/sign-in");
    await user.click(await screen.findByRole("button", { name: "Seller" }));
    await screen.findByText(HINT);

    await user.click(screen.getByRole("button", { name: OPEN_INBOX }));
    const drawer = await screen.findByRole("dialog", { name: "Demo SMS inbox" });
    await user.click(await within(drawer).findByRole("button", { name: "Use this code" }));

    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "Demo SMS inbox" })).not.toBeInTheDocument(),
    );
    const digits = [1, 2, 3, 4, 5, 6].map(
      (position) => screen.getByLabelText<HTMLInputElement>(`Digit ${position} of 6`).value,
    );
    expect(digits.join("")).toBe(MESSAGE!.code);
    const signIn = screen.getByRole("button", { name: "Sign in" });
    await waitFor(() => expect(signIn).toHaveFocus());

    await user.click(signIn);
    await waitFor(() => expect(router.state.location.pathname).toBe("/licensee"));
    expect(posted[1]).toEqual({ challenge_id: CHALLENGE, code: MESSAGE!.code });
  });

  it("polls every 3 seconds only while open", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    server.use(...serveDemo());
    const asked = serveInbox();
    renderWithProviders(
      <DemoProvider>
        <SmsInboxButton variant="text" />
      </DemoProvider>,
    );
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const advance = (ms: number) => act(() => vi.advanceTimersByTimeAsync(ms));

    await screen.findByRole("button", { name: OPEN_INBOX });
    await advance(10_000);
    expect(asked.count).toBe(0); // closed: not asked at all

    await user.click(screen.getByRole("button", { name: OPEN_INBOX }));
    await screen.findByText(MESSAGE!.code);
    expect(asked.count).toBe(1);
    await advance(3_000);
    await waitFor(() => expect(asked.count).toBe(2));
    await advance(3_000);
    await waitFor(() => expect(asked.count).toBe(3));

    await user.click(screen.getByRole("button", { name: "Close" }));
    await advance(500);
    const whenClosed = asked.count;
    await advance(15_000);
    expect(asked.count).toBe(whenClosed);
  });

  it("copies the code when no code input is open", async () => {
    server.use(...serveDemo());
    serveInbox();
    const { user } = renderApp("/sign-in", { signedOut: true });
    const writeText = vi.spyOn(navigator.clipboard, "writeText");
    await user.click(await screen.findByRole("button", { name: OPEN_INBOX }));
    await user.click(await screen.findByRole("button", { name: "Use this code" }));
    expect(writeText).toHaveBeenCalledWith(MESSAGE!.code);
    expect(await screen.findByText(`Code ${MESSAGE!.code} copied.`)).toBeInTheDocument();
  });

  it("shows the code to type when the browser cannot copy", async () => {
    server.use(...serveDemo());
    serveInbox();
    const { user } = renderApp("/sign-in", { signedOut: true });
    const original = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", { value: undefined, configurable: true });
    try {
      await user.click(await screen.findByRole("button", { name: OPEN_INBOX }));
      await user.click(await screen.findByRole("button", { name: "Use this code" }));
      expect(
        await screen.findByText(`Couldn't copy the code. Type it in: ${MESSAGE!.code}`),
      ).toBeInTheDocument();
    } finally {
      if (original) Object.defineProperty(navigator, "clipboard", original);
      else Reflect.deleteProperty(navigator, "clipboard");
    }
  });

  it("'Use this code' fills a code dialog; Escape in the inbox leaves the dialog open", async () => {
    server.use(...serveDemo());
    serveInbox();
    const requestCode = vi.fn().mockResolvedValue(contract<Challenge>("decision_code"));
    const submit = vi.fn().mockResolvedValue("done");
    function Harness() {
      const [opened, setOpened] = useState(true);
      return (
        <CodeDialog
          opened={opened}
          onClose={() => setOpened(false)}
          title="Confirm your decision"
          requestCode={requestCode}
          submit={submit}
          onDone={() => setOpened(false)}
        />
      );
    }
    const { user } = renderWithProviders(
      <DemoProvider>
        <Harness />
      </DemoProvider>,
    );
    const dialog = await screen.findByRole("dialog", { name: "Confirm your decision" });
    expect(await within(dialog).findByText(HINT)).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: OPEN_INBOX }));
    await screen.findByRole("dialog", { name: "Demo SMS inbox" });
    await user.keyboard("{Escape}");
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "Demo SMS inbox" })).not.toBeInTheDocument(),
    );
    expect(screen.getByRole("dialog", { name: "Confirm your decision" })).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: OPEN_INBOX }));
    await user.click(await screen.findByRole("button", { name: "Use this code" }));
    const confirm = within(dialog).getByRole("button", { name: "Confirm" });
    await waitFor(() => expect(confirm).toHaveFocus());
    await user.click(confirm);
    await waitFor(() =>
      expect(submit).toHaveBeenCalledWith({
        challenge_id: contract<Challenge>("decision_code").challenge_id,
        code: MESSAGE!.code,
      }),
    );
  });
});

describe("the signed-in header in demo mode", () => {
  it("shows the ribbon and an inbox button that opens the drawer", async () => {
    server.use(...serveDemo());
    serveInbox();
    const { user } = renderApp("/licensee");
    const banner = await screen.findByRole("banner");
    expect(await within(banner).findByText(RIBBON)).toBeInTheDocument();
    await user.click(within(banner).getByRole("button", { name: OPEN_INBOX }));
    expect(await screen.findByRole("dialog", { name: "Demo SMS inbox" })).toBeInTheDocument();
  });
});
