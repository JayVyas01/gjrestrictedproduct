import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { BatchDetail, BatchItem } from "@/api/types";
import { contract } from "@/test/handlers";
import { renderApp, renderWithProviders } from "@/test/render";
import { server } from "@/test/server";
import { BatchPage } from "./BatchPage";

const AS_SUPERINTENDENT = ["me_superintendent", "home_superintendent"];
const DETAIL = contract<BatchDetail>("oversight_batch_detail");
const FLAGGED = DETAIL.items[0]!;
const CHALLENGE = contract<{ challenge_id: string }>("decision_code").challenge_id;
const AT = `/personnel/batches/${DETAIL.id}`;

/** The colour tone named on the badge around a status word. */
const toneOf = (word: HTMLElement) => word.closest("[data-tone]")?.getAttribute("data-tone");

// One item flagged already, one open to a flag, one the superintendent approved themselves.
const UNFLAGGED: BatchItem = { ...FLAGGED, reference: "TXUNFLAGGED1", flag: null };
const OWN: BatchItem = {
  ...FLAGGED,
  reference: "TXOWNAPPROVE",
  flag: null,
  approved_by_superintendent: true,
  approved_by_position: "District Officer, Ahmedabad",
};
const OPEN_BATCH: BatchDetail = { ...DETAIL, items: [FLAGGED, UNFLAGGED, OWN] };
const SIGNED_BATCH: BatchDetail = {
  ...OPEN_BATCH,
  status: "SIGNED",
  can_sign: false,
  signed_by: "GJ5SVTKLEY5X",
  signed_at: "2026-10-04T06:30:00+00:00",
};

/** Serves `batch`; the returned setter changes what later reads see (the server's state). */
function serveBatch(batch: BatchDetail) {
  let current = batch;
  server.use(http.get("/api/oversight/batches/:id", () => HttpResponse.json(current)));
  return (next: BatchDetail) => {
    current = next;
  };
}

function rowFor(reference: string): HTMLElement {
  const table = screen.getByRole("table", { name: "Transactions in this batch" });
  const row = within(table)
    .getAllByRole("row")
    .find((candidate) => within(candidate).queryByText(reference));
  if (!row) throw new Error(`No row for ${reference}`);
  return row;
}

function flagButton(reference: string): HTMLElement {
  return within(rowFor(reference)).getByRole("button", { name: `Flag ${reference}` });
}

type User = ReturnType<typeof renderApp>["user"];

async function enterCode(user: User) {
  const dialog = await screen.findByRole("dialog");
  await within(dialog).findByText(/The code expires in/);
  await user.click(within(dialog).getByLabelText("Digit 1 of 6"));
  await user.paste("123456");
  await user.click(within(dialog).getByRole("button", { name: "Confirm" }));
}

const originalMatchMedia = window.matchMedia.bind(window);

describe("BatchPage", () => {
  afterEach(() => {
    window.matchMedia = originalMatchMedia;
  });

  it("lists the items with their approval, the own-approval tag and any flag", async () => {
    serveBatch(OPEN_BATCH);
    const { container } = renderApp(AT, { contracts: AS_SUPERINTENDENT });
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Batch 14 Sept 2026 to 28 Sept 2026",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to batches" })).toHaveAttribute(
      "href",
      "/personnel/batches",
    );
    await screen.findByRole("table", { name: "Transactions in this batch" });

    const flagged = rowFor(FLAGGED.reference);
    expect(flagged).toHaveTextContent("Whisky");
    expect(flagged).toHaveTextContent("10 L");
    expect(flagged).toHaveTextContent("Sanand Spirits Pvt Ltd to Bopal Bar & Kitchen");
    expect(flagged).toHaveTextContent("Area Officer, Sanand");
    expect(flagged).toHaveTextContent("4 Oct 2026");
    expect(flagged).toHaveTextContent("Quantity unusually high");
    expect(flagged).toHaveTextContent("Comment: Check");
    // Already flagged: no second flag.
    expect(within(flagged).queryByRole("button", { name: /Flag/ })).toBeNull();

    expect(flagButton(UNFLAGGED.reference)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign off batch" })).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("offers no flag on the superintendent's own approvals", async () => {
    serveBatch(OPEN_BATCH);
    renderApp(AT, { contracts: AS_SUPERINTENDENT });
    await screen.findByRole("table", { name: "Transactions in this batch" });
    const own = rowFor(OWN.reference);
    expect(within(own).getByText("Approved by you")).toBeInTheDocument();
    expect(within(own).queryByRole("button", { name: /Flag/ })).toBeNull();
    expect(within(rowFor(UNFLAGGED.reference)).queryByText("Approved by you")).toBeNull();
  });

  it("flags an item with a reason and a comment", async () => {
    const setBatch = serveBatch(OPEN_BATCH);
    const bodies: unknown[] = [];
    server.use(
      http.post("/api/oversight/batches/:id/flag", async ({ request }) => {
        bodies.push(await request.json());
        const items = OPEN_BATCH.items.map((item) =>
          item.reference === UNFLAGGED.reference
            ? { ...item, flag: { ...FLAGGED.flag!, reason: "Transport details need checking" } }
            : item,
        );
        const flagged = { ...OPEN_BATCH, items, flag_count: 2 };
        setBatch(flagged);
        return HttpResponse.json(flagged);
      }),
    );
    const { user } = renderApp(AT, { contracts: AS_SUPERINTENDENT });
    await screen.findByRole("table", { name: "Transactions in this batch" });
    await user.click(flagButton(UNFLAGGED.reference));
    const dialog = await screen.findByRole("dialog", { name: `Flag ${UNFLAGGED.reference}` });
    // Nothing chosen yet: the reason is asked for.
    await user.click(within(dialog).getByRole("button", { name: "Flag transaction" }));
    expect(await within(dialog).findByText("Choose a reason.")).toBeInTheDocument();
    expect(bodies).toEqual([]);

    await user.click(
      await within(dialog).findByRole("radio", { name: "Transport details need checking" }),
    );
    await user.type(within(dialog).getByLabelText("Comment (optional)"), "Vehicle not seen");
    expect(await axe(dialog)).toHaveNoViolations();
    await user.click(within(dialog).getByRole("button", { name: "Flag transaction" }));

    expect(await screen.findByText("Flag recorded. The officer is alerted.")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    // The item's Flag button is gone: focus goes to the page heading.
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toHaveFocus());
    expect(bodies).toEqual([
      {
        reference: UNFLAGGED.reference,
        reason_code: "TRANSPORT_CONCERN",
        comment: "Vehicle not seen",
      },
    ]);
    expect(rowFor(UNFLAGGED.reference)).toHaveTextContent("Transport details need checking");
  });

  it("shows the server's text when a flag is refused", async () => {
    serveBatch(OPEN_BATCH);
    server.use(
      http.post("/api/oversight/batches/:id/flag", () =>
        HttpResponse.json(
          { detail: "This transaction is already flagged in this batch." },
          { status: 403 },
        ),
      ),
    );
    const { user } = renderApp(AT, { contracts: AS_SUPERINTENDENT });
    await screen.findByRole("table", { name: "Transactions in this batch" });
    await user.click(flagButton(UNFLAGGED.reference));
    const dialog = await screen.findByRole("dialog", { name: `Flag ${UNFLAGGED.reference}` });
    await user.click(await within(dialog).findByRole("radio", { name: "Quantity unusually high" }));
    await user.click(within(dialog).getByRole("button", { name: "Flag transaction" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "This transaction is already flagged in this batch.",
    );
    expect(screen.queryByText("Flag recorded. The officer is alerted.")).toBeNull();
  });

  it("signs the batch off with a one-time code", async () => {
    const setBatch = serveBatch(OPEN_BATCH);
    const bodies: unknown[] = [];
    server.use(
      http.post("/api/oversight/batches/:id/sign-off", async ({ request }) => {
        bodies.push(await request.json());
        setBatch(SIGNED_BATCH);
        return HttpResponse.json(SIGNED_BATCH);
      }),
    );
    const { user } = renderApp(AT, { contracts: AS_SUPERINTENDENT });
    await user.click(await screen.findByRole("button", { name: "Sign off batch" }));
    const dialog = await screen.findByRole("dialog", { name: "Sign off this batch" });
    expect(await axe(dialog)).toHaveNoViolations();
    await enterCode(user);

    expect(await screen.findByText("Batch signed off.")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toHaveFocus());
    expect(bodies).toEqual([{ challenge_id: CHALLENGE, code: "123456" }]);
    expect(
      await screen.findByText("Signed by GJ5SVTKLEY5X on 4 Oct 2026, 12:00 pm"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Sign off batch" })).toBeNull();
  });

  it("shows who signed a signed batch, with no actions left", async () => {
    serveBatch(SIGNED_BATCH);
    const { container } = renderApp(AT, { contracts: AS_SUPERINTENDENT });
    expect(
      await screen.findByText("Signed by GJ5SVTKLEY5X on 4 Oct 2026, 12:00 pm"),
    ).toBeInTheDocument();
    await screen.findByRole("table", { name: "Transactions in this batch" });
    expect(toneOf(screen.getByText("Signed"))).toBe("approved");
    expect(screen.queryByRole("button", { name: /Flag|Sign off/ })).toBeNull();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("is read-only when asked, even for a batch the viewer could sign", async () => {
    serveBatch(OPEN_BATCH);
    renderWithProviders(<BatchPage listPath="/overview/batches" readOnly />, {
      route: "/overview/batches/2",
      path: "/overview/batches/:id",
    });
    await screen.findByRole("table", { name: "Transactions in this batch" });
    expect(screen.getByRole("link", { name: "Back to batches" })).toHaveAttribute(
      "href",
      "/overview/batches",
    );
    expect(screen.queryByRole("button", { name: /Flag|Sign off/ })).toBeNull();
    // Not the viewer's own approval: the superintendent's final approval is named as such.
    const own = rowFor(OWN.reference);
    expect(within(own).getByText("Final approval by the superintendent")).toBeInTheDocument();
    expect(screen.queryByText("Approved by you")).toBeNull();
  });

  it.each(["abc", "1e3", "-2", "2.5"])(
    "shows not found for the id %s without asking the server",
    async (id) => {
      let requests = 0;
      server.use(
        http.get("/api/oversight/batches/:id", () => {
          requests += 1;
          return HttpResponse.json(OPEN_BATCH);
        }),
      );
      renderWithProviders(<BatchPage listPath="/overview/batches" readOnly />, {
        route: `/overview/batches/${id}`,
        path: "/overview/batches/:id",
      });
      expect(await screen.findByText("Not found, or not yours to see.")).toBeInTheDocument();
      expect(requests).toBe(0);
    },
  );

  it("becomes stacked cards under 768 px, keeping the tag and the flag action", async () => {
    window.matchMedia = (query: string) => ({
      ...originalMatchMedia(query),
      matches: query.includes("max-width"),
    });
    serveBatch(OPEN_BATCH);
    const { container } = renderApp(AT, { contracts: AS_SUPERINTENDENT });
    const list = await screen.findByRole("list", { name: "Transactions in this batch" });
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    const [flagged, open, own] = within(list).getAllByRole("listitem") as [
      HTMLElement,
      HTMLElement,
      HTMLElement,
    ];
    expect(flagged).toHaveTextContent("Quantity unusually high");
    expect(
      within(open).getByRole("button", { name: `Flag ${UNFLAGGED.reference}` }),
    ).toBeInTheDocument();
    expect(within(own).getByText("Approved by you")).toBeInTheDocument();
    expect(within(own).queryByRole("button")).toBeNull();
    expect(await axe(container)).toHaveNoViolations();
  });
});
