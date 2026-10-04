import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import type { LicenceCard } from "@/api/types";
import { contract, serveContract } from "@/test/handlers";
import { renderApp } from "@/test/render";
import { server } from "@/test/server";
import { DRAFT_KEY, emptyDraft, saveDraft, type SaleDraft } from "./draft";

const NEW_SALE = "/licensee/sale/new";
const GSTIN = "24ABCDE1234F1Z5";
const BUYER = contract<{ holder_name: string }>("buyer_lookup").holder_name;
const CREATED = contract<{ reference: string }>("transaction_created").reference;
const REFUSED = contract<{ reasons: string[] }>("transaction_check_refused").reasons;

type User = ReturnType<typeof renderApp>["user"];

interface Posted {
  url: string;
  body: Record<string, unknown>;
}

// Records every POST to `path` (URL and body), answering with `answer` and `status`.
function recordPosts(path: string, answer: string, status = 200) {
  const posts: Posted[] = [];
  server.use(
    http.post(path, async ({ request }) => {
      posts.push({ url: request.url, body: (await request.json()) as Record<string, unknown> });
      return HttpResponse.json(contract<object>(answer), { status });
    }),
  );
  return posts;
}

const next = (user: User) => user.click(screen.getByRole("button", { name: "Next" }));

async function open() {
  const rendered = renderApp(NEW_SALE);
  expect(await screen.findByRole("heading", { level: 1, name: "New sale" })).toBeInTheDocument();
  return rendered;
}

async function findBuyer(user: User) {
  await user.type(screen.getByLabelText("Buyer's GSTIN"), GSTIN.toLowerCase());
  await user.click(screen.getByRole("button", { name: "Find buyer" }));
  await screen.findByText(BUYER);
}

async function toGoods(user: User) {
  await findBuyer(user);
  await user.click(screen.getByRole("button", { name: "Yes, this is the buyer" }));
  await next(user);
  await screen.findByRole("heading", { level: 2, name: "Goods" });
}

async function fillGoods(user: User, quantity = "150") {
  await user.selectOptions(await screen.findByLabelText(/^Substance/), "WHISKY");
  await user.type(screen.getByLabelText(/^Quantity/), quantity);
}

async function toTransport(user: User) {
  await toGoods(user);
  await fillGoods(user);
  await user.click(screen.getByRole("button", { name: "Check" }));
  await screen.findByText("This sale can go ahead.");
  await next(user);
  await screen.findByRole("heading", { level: 2, name: "Transport" });
}

async function fillTransport(user: User) {
  await user.type(screen.getByLabelText("Transporter name"), "Ravi Transport Co");
  await user.type(screen.getByLabelText("ID or licence number"), "GJ-TR-4411");
  await user.type(screen.getByLabelText("Vehicle number"), "gj01ab1234");
  await user.type(screen.getByLabelText("Route"), "Sanand to Bopal via SG Highway");
}

async function toReview(user: User) {
  await toTransport(user);
  await fillTransport(user);
  await next(user);
  await screen.findByRole("heading", { level: 2, name: "Review and send" });
}

describe("NewSalePage", () => {
  describe("step 1, buyer", () => {
    it("shows the progress, labels the GSTIN with format help and passes axe", async () => {
      const { container } = await open();
      expect(screen.getByText("Step 1 of 4")).toBeInTheDocument();
      expect(screen.getByRole("heading", { level: 2, name: "Buyer" })).toBeInTheDocument();
      const gstin = screen.getByLabelText("Buyer's GSTIN");
      expect(gstin).toHaveAccessibleDescription(/15-character GSTIN, like 24ABCDE1234F1Z5/);
      expect(await axe(container)).toHaveNoViolations();
    });

    it("won't go on until the buyer is found and confirmed; errors are linked", async () => {
      const { user } = await open();
      await next(user);
      const gstin = screen.getByLabelText("Buyer's GSTIN");
      expect(gstin).toHaveAttribute("aria-invalid", "true");
      expect(gstin).toHaveAccessibleDescription(/Enter all 15 characters/);

      await user.type(gstin, GSTIN);
      await next(user);
      expect(gstin).toHaveAccessibleDescription(/Find the buyer, then confirm/);
      expect(screen.getByText("Step 1 of 4")).toBeInTheDocument();
    });

    it("refuses a malformed GSTIN without asking the server", async () => {
      const posts = recordPosts("/api/transactions/buyer-lookup", "buyer_lookup");
      const { user } = await open();
      await user.type(screen.getByLabelText("Buyer's GSTIN"), "24ABCDE");
      await user.click(screen.getByRole("button", { name: "Find buyer" }));
      expect(screen.getByLabelText("Buyer's GSTIN")).toHaveAccessibleDescription(
        /Enter all 15 characters/,
      );
      expect(posts).toHaveLength(0);
    });

    it("finds the buyer by a POST body (never the URL), uppercased; Change starts again", async () => {
      const posts = recordPosts("/api/transactions/buyer-lookup", "buyer_lookup");
      const { user, container } = await open();
      await findBuyer(user);

      expect(posts).toHaveLength(1);
      expect(posts[0]?.body).toEqual({ gstin: GSTIN });
      expect(posts[0]?.url).not.toContain(GSTIN);
      expect(screen.getByLabelText("Buyer's GSTIN")).toHaveValue(GSTIN);
      expect(screen.getByText("Is this the right business?")).toBeInTheDocument();
      expect(await axe(container)).toHaveNoViolations();

      await user.click(screen.getByRole("button", { name: "Change" }));
      expect(screen.queryByText(BUYER)).not.toBeInTheDocument();
      expect(screen.getByLabelText("Buyer's GSTIN")).toHaveFocus();
    });

    it("shows the server's words when no buyer is found", async () => {
      server.use(
        serveContract("error_404_not_found", {
          method: "post",
          path: "/api/transactions/buyer-lookup",
        }),
      );
      const { user } = await open();
      await user.type(screen.getByLabelText("Buyer's GSTIN"), GSTIN);
      await user.click(screen.getByRole("button", { name: "Find buyer" }));
      expect(await screen.findByRole("alert")).toHaveTextContent(
        contract<{ detail: string }>("error_404_not_found").detail,
      );
    });

    it("moves focus to the next step's heading", async () => {
      const { user } = await open();
      await toGoods(user);
      expect(screen.getByRole("heading", { level: 2, name: "Goods" })).toHaveFocus();
      expect(screen.getByText("Step 2 of 4")).toBeInTheDocument();
    });
  });

  describe("step 2, goods", () => {
    it("offers only the substances the seller's licences let them sell", async () => {
      const whiskyOnly: LicenceCard = {
        ...(contract<LicenceCard[]>("licences_mine")[0] as LicenceCard),
        scope: "Whisky",
        scope_kind: "substance",
      };
      server.use(http.get("/api/licences/mine", () => HttpResponse.json([whiskyOnly])));
      const { user } = await open();
      await toGoods(user);
      const select = await screen.findByLabelText(/^Substance/);
      await waitFor(() =>
        expect(
          within(select)
            .getAllByRole("option")
            .map((o) => o.textContent),
        ).toEqual(["Choose a substance", "Whisky (L)"]),
      );
    });

    it("says when no licence lets the seller sell", async () => {
      const cannotSell: LicenceCard = {
        ...(contract<LicenceCard[]>("licences_mine")[0] as LicenceCard),
        may_sell: false,
      };
      server.use(http.get("/api/licences/mine", () => HttpResponse.json([cannotSell])));
      const { user } = await open();
      await toGoods(user);
      expect(
        await screen.findByText(
          "None of your licences lets you sell today, so you can't start a sale.",
        ),
      ).toBeInTheDocument();
    });

    it("validates the substance and quantity before Next, and needs a check", async () => {
      const { user } = await open();
      await toGoods(user);
      await next(user);
      expect(await screen.findByLabelText(/^Substance/)).toHaveAccessibleDescription(
        /Choose a substance\./,
      );
      expect(screen.getByLabelText(/^Quantity/)).toHaveAccessibleDescription(
        /Enter a quantity greater than 0/,
      );

      await fillGoods(user);
      expect(screen.getByLabelText("Quantity in L")).toBeInTheDocument();
      await next(user);
      expect(screen.getByRole("button", { name: "Check" })).toHaveAccessibleDescription(
        /Check the sale before you continue/,
      );
      expect(screen.getByText("Step 2 of 4")).toBeInTheDocument();
    });

    it("checks the sale: ok lets Next through, and posts the right body", async () => {
      const posts = recordPosts("/api/transactions/check", "transaction_check_ok");
      const { user, container } = await open();
      await toGoods(user);
      await fillGoods(user);
      await user.click(screen.getByRole("button", { name: "Check" }));
      expect(await screen.findByText("This sale can go ahead.")).toBeInTheDocument();
      expect(
        screen.queryByText("Above the threshold: the superintendent gives final approval."),
      ).not.toBeInTheDocument();
      expect(posts[0]?.body).toEqual({
        buyer_gstin: GSTIN,
        substance_code: "WHISKY",
        quantity: "150",
      });
      expect(await axe(container)).toHaveNoViolations();
      await next(user);
      expect(await screen.findByRole("heading", { level: 2, name: "Transport" })).toHaveFocus();
    });

    it("says when the superintendent gives final approval", async () => {
      server.use(
        http.post("/api/transactions/check", () =>
          HttpResponse.json({
            ok: true,
            reasons: [],
            approval_chain: "OFFICER_THEN_SUPERINTENDENT",
          }),
        ),
      );
      const { user } = await open();
      await toGoods(user);
      await fillGoods(user);
      await user.click(screen.getByRole("button", { name: "Check" }));
      expect(
        await screen.findByText("Above the threshold: the superintendent gives final approval."),
      ).toBeInTheDocument();
    });

    it("lists the reasons when refused, and Next stays blocked", async () => {
      server.use(serveContract("transaction_check_refused"));
      const { user, container } = await open();
      await toGoods(user);
      await fillGoods(user, "600");
      await user.click(screen.getByRole("button", { name: "Check" }));
      expect(await screen.findByText("This sale can't go ahead:")).toBeInTheDocument();
      for (const reason of REFUSED) expect(screen.getByText(reason)).toBeInTheDocument();
      expect(await axe(container)).toHaveNoViolations();
      await next(user);
      expect(screen.getByText("Step 2 of 4")).toBeInTheDocument();
    });

    it("a change to the quantity or substance needs a new check", async () => {
      const { user } = await open();
      await toGoods(user);
      await fillGoods(user);
      await user.click(screen.getByRole("button", { name: "Check" }));
      await screen.findByText("This sale can go ahead.");

      await user.type(screen.getByLabelText(/^Quantity/), "0");
      expect(screen.queryByText("This sale can go ahead.")).not.toBeInTheDocument();
      await next(user);
      expect(screen.getByText("Step 2 of 4")).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "Check" }));
      await screen.findByText("This sale can go ahead.");
      await user.selectOptions(screen.getByLabelText(/^Substance/), "RUM");
      expect(screen.queryByText("This sale can go ahead.")).not.toBeInTheDocument();
    });

    it("Back returns to the buyer with the buyer kept", async () => {
      const { user } = await open();
      await toGoods(user);
      await user.click(screen.getByRole("button", { name: "Back" }));
      expect(await screen.findByRole("heading", { level: 2, name: "Buyer" })).toHaveFocus();
      expect(screen.getByText(BUYER)).toBeInTheDocument();
    });
  });

  describe("step 3, transport", () => {
    it("labels every field with help, validates before Next and passes axe", async () => {
      const { user, container } = await open();
      await toTransport(user);
      for (const label of ["Transporter name", "ID or licence number", "Vehicle number", "Route"]) {
        expect(screen.getByLabelText(label)).toHaveAccessibleDescription(/.+/);
      }
      expect(await axe(container)).toHaveNoViolations();

      await next(user);
      expect(screen.getByLabelText("Transporter name")).toHaveAttribute("aria-invalid", "true");
      expect(screen.getByLabelText("Route")).toHaveAccessibleDescription(/Fill this in\./);

      await user.type(screen.getByLabelText("Vehicle number"), "gj-01");
      await next(user);
      expect(screen.getByLabelText("Vehicle number")).toHaveValue("GJ-01");
      expect(screen.getByLabelText("Vehicle number")).toHaveAccessibleDescription(
        /Enter the vehicle number like GJ01AB1234\./,
      );
      expect(screen.getByText("Step 3 of 4")).toBeInTheDocument();
    });
  });

  describe("step 4, review and send", () => {
    it("shows everything, sends, then opens the new transaction and clears the draft", async () => {
      const posts = recordPosts("/api/transactions", "transaction_created", 201);
      const { user, container, router } = await open();
      await toReview(user);

      const review = screen.getByRole("region", { name: "Review and send" });
      for (const text of [
        BUYER,
        GSTIN,
        "Whisky",
        "150 L",
        "Ravi Transport Co",
        "GJ-TR-4411",
        "GJ01AB1234",
        "Sanand to Bopal via SG Highway",
      ]) {
        expect(within(review).getByText(text)).toBeInTheDocument();
      }
      expect(await axe(container)).toHaveNoViolations();
      await waitFor(() => expect(sessionStorage.getItem(DRAFT_KEY)).not.toBeNull());

      await user.click(screen.getByRole("button", { name: "Send to buyer" }));
      expect(
        await screen.findByRole("heading", { level: 1, name: `Transaction ${CREATED}` }),
      ).toBeInTheDocument();
      expect(router.state.location.pathname).toBe(`/licensee/transactions/${CREATED}`);
      expect(await screen.findByText("Sent to the buyer for confirmation.")).toBeInTheDocument();
      expect(posts[0]?.body).toEqual({
        buyer_gstin: GSTIN,
        substance_code: "WHISKY",
        quantity: "150",
        transporter_name: "Ravi Transport Co",
        transporter_id_number: "GJ-TR-4411",
        vehicle_number: "GJ01AB1234",
        route: "Sanand to Bopal via SG Highway",
      });
      expect(posts[0]?.url).not.toContain(GSTIN);
      expect(sessionStorage.getItem(DRAFT_KEY)).toBeNull();
      // The debounce must not write the draft back after it was cleared.
      await new Promise((resolve) => setTimeout(resolve, 400));
      expect(sessionStorage.getItem(DRAFT_KEY)).toBeNull();
    });

    it("on a refusal shows the reasons and a way back to the goods", async () => {
      server.use(
        serveContract("error_422_transaction_refused", {
          method: "post",
          path: "/api/transactions",
        }),
      );
      const { user, container } = await open();
      await toReview(user);
      await user.click(screen.getByRole("button", { name: "Send to buyer" }));
      const alert = await screen.findByRole("alert");
      expect(alert).toHaveTextContent("This transaction can't go ahead.");
      for (const reason of REFUSED) expect(within(alert).getByText(reason)).toBeInTheDocument();
      expect(await axe(container)).toHaveNoViolations();

      await user.click(screen.getByRole("button", { name: "Change the goods" }));
      expect(await screen.findByRole("heading", { level: 2, name: "Goods" })).toHaveFocus();
      // The refused check no longer counts: the seller checks again.
      expect(screen.queryByText("This sale can go ahead.")).not.toBeInTheDocument();
    });
  });

  describe("drafts", () => {
    it("saves to sessionStorage as the seller types, and restores it", async () => {
      const first = await open();
      await first.user.type(screen.getByLabelText("Buyer's GSTIN"), GSTIN);
      await waitFor(() =>
        expect(JSON.parse(sessionStorage.getItem(DRAFT_KEY) ?? "{}")).toMatchObject({
          gstin: GSTIN,
        }),
      );
      first.unmount();

      const { container } = await open();
      expect(screen.getByText("Draft restored")).toBeInTheDocument();
      expect(screen.getByLabelText("Buyer's GSTIN")).toHaveValue(GSTIN);
      expect(await axe(container)).toHaveNoViolations();
    });

    it("restores the step it was on", async () => {
      const draft: SaleDraft = {
        ...emptyDraft(),
        step: 2,
        gstin: GSTIN,
        buyerName: BUYER,
        substanceCode: "WHISKY",
        quantity: "150",
        check: { key: `${GSTIN}|WHISKY|150`, approval_chain: "OFFICER" },
        transporterName: "Ravi Transport Co",
      };
      saveDraft(draft);
      await open();
      expect(screen.getByText("Step 3 of 4")).toBeInTheDocument();
      expect(screen.getByLabelText("Transporter name")).toHaveValue("Ravi Transport Co");
    });

    it("Start over empties the form and removes the draft", async () => {
      saveDraft({ ...emptyDraft(), gstin: GSTIN });
      const { user } = await open();
      await user.click(screen.getByRole("button", { name: "Start over" }));
      expect(screen.getByLabelText("Buyer's GSTIN")).toHaveValue("");
      expect(screen.queryByText("Draft restored")).not.toBeInTheDocument();
      expect(sessionStorage.getItem(DRAFT_KEY)).toBeNull();
    });

    it("Discard draft removes it and goes home", async () => {
      saveDraft({ ...emptyDraft(), gstin: GSTIN });
      const { user, router } = await open();
      await user.click(screen.getByRole("button", { name: "Discard draft" }));
      await waitFor(() => expect(router.state.location.pathname).toBe("/licensee"));
      expect(sessionStorage.getItem(DRAFT_KEY)).toBeNull();
    });

    it("is cleared on sign-out", async () => {
      const { user, router } = await open();
      await user.type(screen.getByLabelText("Buyer's GSTIN"), GSTIN);
      await waitFor(() => expect(sessionStorage.getItem(DRAFT_KEY)).not.toBeNull());
      await user.click(screen.getByRole("button", { name: "Sign out" }));
      await waitFor(() => expect(router.state.location.pathname).toBe("/sign-in"));
      expect(sessionStorage.getItem(DRAFT_KEY)).toBeNull();
    });

    it("never writes to localStorage during the whole flow", async () => {
      // Storage methods live on the prototype, shared by both storages: every call's `this`
      // must be sessionStorage, so nothing reaches localStorage.
      const setItem = vi.spyOn(Storage.prototype, "setItem");
      const { user } = await open();
      await toReview(user);
      await waitFor(() => expect(sessionStorage.getItem(DRAFT_KEY)).not.toBeNull());
      await user.click(screen.getByRole("button", { name: "Send to buyer" }));
      await screen.findByText("Sent to the buyer for confirmation.");
      expect(setItem).toHaveBeenCalled();
      expect(setItem.mock.contexts.every((storage) => storage === window.sessionStorage)).toBe(
        true,
      );
    });
  });
});
