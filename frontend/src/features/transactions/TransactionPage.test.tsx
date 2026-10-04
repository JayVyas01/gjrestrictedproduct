import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { keys } from "@/api/hooks/keys";
import type { TransactionDetail } from "@/api/types";
import { contract, serveContract } from "@/test/handlers";
import { renderApp } from "@/test/render";
import { server } from "@/test/server";

const SELLER = contract<TransactionDetail>("transaction_detail_seller");
const BUYER = contract<TransactionDetail>("transaction_detail_buyer");
const STOCK_LIMIT = contract<TransactionDetail>("transaction_detail_buyer_stock_limit");
const CHALLENGE = contract<{ challenge_id: string }>("decision_code").challenge_id;

const at = (tx: TransactionDetail) => `/licensee/transactions/${tx.reference}`;

// Records the bodies posted to one endpoint, answering with `answer`.
function recordPosts(path: string, answer: string) {
  const bodies: unknown[] = [];
  server.use(
    http.post(path, async ({ request }) => {
      bodies.push(await request.json());
      return HttpResponse.json(contract<object>(answer));
    }),
  );
  return bodies;
}

const recordDecisions = () =>
  recordPosts("/api/transactions/:reference/decide", "transaction_detail_authority");

type User = ReturnType<typeof renderApp>["user"];

async function enterCode(user: User) {
  const dialog = await screen.findByRole("dialog");
  await within(dialog).findByText(/The code expires in/);
  await user.click(within(dialog).getByLabelText("Digit 1 of 6"));
  await user.paste("123456");
  await user.click(within(dialog).getByRole("button", { name: "Confirm" }));
}

describe("TransactionPage", () => {
  it("shows the summary, transport, officer, approval chain, timeline and next action", async () => {
    const { container } = renderApp(at(SELLER));
    expect(
      await screen.findByRole("heading", { level: 1, name: `Transaction ${SELLER.reference}` }),
    ).toBeInTheDocument();
    expect(await screen.findByText("Waiting for the buyer to confirm.")).toBeInTheDocument();
    expect(screen.getByText("Waiting for the buyer")).toBeInTheDocument();

    const summary = screen.getByRole("region", { name: "Summary" });
    expect(within(summary).getByText("Sanand Spirits Pvt Ltd")).toBeInTheDocument();
    expect(within(summary).getByText("Bopal Bar & Kitchen")).toBeInTheDocument();
    expect(within(summary).getByText("10 L")).toBeInTheDocument();
    expect(within(summary).getByText("Officer")).toBeInTheDocument();
    expect(within(summary).getByText("Area Officer, Sanand")).toBeInTheDocument();

    const transport = screen.getByRole("region", { name: "Transport" });
    expect(within(transport).getByText("Ravi Transport Co")).toBeInTheDocument();
    expect(within(transport).getByText("GJ-TR-4411")).toBeInTheDocument();
    expect(within(transport).getByText("GJ01AB1234")).toBeInTheDocument();
    expect(within(transport).getByText("Sanand to Bopal")).toBeInTheDocument();

    const timeline = screen.getByRole("list", { name: "Progress" });
    expect(within(timeline).getByText("Sale started")).toBeInTheDocument();
    expect(within(timeline).getByText("Next: the buyer confirms or rejects")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to transactions" })).toHaveAttribute(
      "href",
      "/licensee/transactions",
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("says when the transaction is not found", async () => {
    server.use(
      serveContract("error_404_not_found", {
        method: "get",
        path: "/api/transactions/:reference",
      }),
    );
    renderApp("/licensee/transactions/TXNOSUCHREF1");
    expect(await screen.findByRole("alert")).toHaveTextContent("Not found, or not yours to see.");
  });

  describe("the seller", () => {
    it("can cancel while the sale waits for the buyer, after confirming", async () => {
      const posts = recordPosts("/api/transactions/:reference/cancel", "transaction_detail_seller");
      const { user, queryClient } = renderApp(at(SELLER));
      await user.click(await screen.findByRole("button", { name: "Cancel sale" }));

      const dialog = await screen.findByRole("dialog", { name: "Cancel this sale?" });
      expect(await axe(dialog)).toHaveNoViolations();
      await user.click(within(dialog).getByRole("button", { name: "Keep the sale" }));
      await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
      expect(posts).toHaveLength(0);

      const invalidate = vi.spyOn(queryClient, "invalidateQueries");
      await user.click(screen.getByRole("button", { name: "Cancel sale" }));
      const again = await screen.findByRole("dialog", { name: "Cancel this sale?" });
      await user.click(within(again).getByRole("button", { name: "Yes, cancel the sale" }));
      expect(await screen.findByText("Sale cancelled.")).toBeInTheDocument();
      expect(posts).toEqual([{}]);
      expect(invalidate).toHaveBeenCalledWith({ queryKey: keys.home });
      expect(invalidate).toHaveBeenCalledWith({ queryKey: keys.transactions });
    });

    it("cannot cancel once the buyer has acted", async () => {
      server.use(
        http.get("/api/transactions/:reference", () =>
          HttpResponse.json({ ...SELLER, status: "AWAITING_OFFICER" }),
        ),
      );
      renderApp(at(SELLER));
      await screen.findByRole("heading", { level: 1 });
      expect(screen.queryByRole("button", { name: "Cancel sale" })).not.toBeInTheDocument();
    });

    it("never sees the buyer's stock, even if the server sent it", async () => {
      // The contract has none; a leaked sentence must still not be shown to the seller.
      server.use(
        http.get("/api/transactions/:reference", () =>
          HttpResponse.json({ ...SELLER, stock_limit_problem: STOCK_LIMIT.stock_limit_problem }),
        ),
      );
      renderApp(at(SELLER));
      await screen.findByRole("heading", { level: 1 });
      await screen.findByRole("button", { name: "Cancel sale" });
      const page = document.body.textContent ?? "";
      expect(page).not.toMatch(/stock/i);
      expect(page).not.toMatch(/1,?005|1,?000 L/);
      expect(screen.queryByRole("button", { name: /Reject|Confirm/ })).not.toBeInTheDocument();
    });

    it("on the plain contract shows no stock text either", async () => {
      renderApp(at(SELLER));
      await screen.findByRole("button", { name: "Cancel sale" });
      expect(document.body.textContent ?? "").not.toMatch(/stock/i);
    });
  });

  describe("the buyer", () => {
    it("is offered only the server's outcomes and cannot cancel", async () => {
      renderApp(at(BUYER), { contracts: ["transaction_detail_buyer"] });
      const decision = await screen.findByRole("region", { name: "Your decision" });
      expect(
        within(decision)
          .getAllByRole("button")
          .map((button) => button.textContent),
      ).toEqual(["Confirm purchase", "Reject"]);
      expect(screen.queryByRole("button", { name: "Cancel sale" })).not.toBeInTheDocument();
      expect(screen.getByText("Awaiting you")).toBeInTheDocument();
    });

    it("confirms through the code dialog", async () => {
      const { user, queryClient, container } = renderApp(at(BUYER), {
        contracts: ["transaction_detail_buyer"],
      });
      const posts = recordDecisions();
      await screen.findByRole("region", { name: "Your decision" });
      expect(await axe(container)).toHaveNoViolations();
      const invalidate = vi.spyOn(queryClient, "invalidateQueries");
      await user.click(await screen.findByRole("button", { name: "Confirm purchase" }));
      expect(
        await screen.findByRole("dialog", { name: "Confirm this purchase" }),
      ).toBeInTheDocument();
      await enterCode(user);

      expect(await screen.findByText("You confirmed the purchase.")).toBeInTheDocument();
      expect(posts).toEqual([{ challenge_id: CHALLENGE, code: "123456", outcome: "CONFIRM" }]);
      expect(invalidate).toHaveBeenCalledWith({ queryKey: keys.home });
      expect(invalidate).toHaveBeenCalledWith({ queryKey: keys.transactions });
    });

    it("rejects with a reason, the stock limit not among them", async () => {
      const { user } = renderApp(at(BUYER), { contracts: ["transaction_detail_buyer"] });
      const posts = recordDecisions();
      await user.click(await screen.findByRole("button", { name: "Reject" }));
      await screen.findByRole("radio", { name: "Wrong substance" });
      expect(screen.queryByRole("radio", { name: /stock limit/ })).not.toBeInTheDocument();

      // A reason is required before the code.
      await user.click(screen.getByRole("button", { name: "Continue to reject" }));
      expect(screen.getByText("Choose a reason.")).toBeInTheDocument();
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

      await user.click(screen.getByRole("radio", { name: "Other" }));
      await user.type(screen.getByLabelText(/Describe the reason/), "Never agreed the price");
      await user.click(screen.getByRole("button", { name: "Continue to reject" }));
      expect(
        await screen.findByRole("dialog", { name: "Reject this transaction" }),
      ).toBeInTheDocument();
      await enterCode(user);

      expect(await screen.findByText("You rejected the transaction.")).toBeInTheDocument();
      expect(posts).toEqual([
        {
          challenge_id: CHALLENGE,
          code: "123456",
          outcome: "REJECT",
          reason_code: "OTHER",
          comment: "Never agreed the price",
        },
      ]);
    });

    it("sees the server's reasons when the decision is refused", async () => {
      const { user } = renderApp(at(BUYER), { contracts: ["transaction_detail_buyer"] });
      server.use(
        serveContract("error_422_transaction_refused", {
          method: "post",
          path: "/api/transactions/:reference/decide",
        }),
      );
      await user.click(await screen.findByRole("button", { name: "Confirm purchase" }));
      await enterCode(user);

      await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
      const alert = await screen.findByRole("alert");
      expect(alert).toHaveTextContent("This transaction can't go ahead.");
      expect(alert).toHaveTextContent(
        "You have 400 L of Whisky in stock, which is less than 600 L.",
      );
    });

    describe("over their stock limit", () => {
      it("sees why, has no confirm button anywhere, and the reason is preset", async () => {
        const { container } = renderApp(at(STOCK_LIMIT), {
          contracts: ["transaction_detail_buyer_stock_limit"],
        });
        expect(await screen.findByText(STOCK_LIMIT.stock_limit_problem!)).toBeInTheDocument();
        const stockLimit = await screen.findByRole("radio", {
          name: "This would take me over my licence's stock limit",
        });
        expect(stockLimit).toBeChecked();
        expect(screen.queryByRole("button", { name: /confirm/i })).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Continue to reject" })).toBeInTheDocument();
        expect(await axe(container)).toHaveNoViolations();
      });

      it("still has no confirm button if the server listed CONFIRM", async () => {
        server.use(
          http.get("/api/transactions/:reference", () =>
            HttpResponse.json({ ...STOCK_LIMIT, allowed_outcomes: ["CONFIRM", "REJECT"] }),
          ),
        );
        renderApp(at(STOCK_LIMIT));
        await screen.findByText(STOCK_LIMIT.stock_limit_problem!);
        expect(screen.queryByRole("button", { name: /confirm/i })).not.toBeInTheDocument();
      });

      it("rejects with the stock limit, or another reason if changed", async () => {
        const { user } = renderApp(at(STOCK_LIMIT), {
          contracts: ["transaction_detail_buyer_stock_limit"],
        });
        const posts = recordDecisions();
        await screen.findByRole("radio", { name: /stock limit/ });
        await user.click(screen.getByRole("button", { name: "Continue to reject" }));
        await enterCode(user);
        await screen.findByText("You rejected the transaction.");
        expect(posts).toEqual([
          {
            challenge_id: CHALLENGE,
            code: "123456",
            outcome: "REJECT",
            reason_code: "STOCK_LIMIT",
            comment: "",
          },
        ]);
      });

      it("can change the preset reason", async () => {
        const { user } = renderApp(at(STOCK_LIMIT), {
          contracts: ["transaction_detail_buyer_stock_limit"],
        });
        const posts = recordDecisions();
        await user.click(await screen.findByRole("radio", { name: "Quantity does not match" }));
        await user.click(screen.getByRole("button", { name: "Continue to reject" }));
        await enterCode(user);
        await screen.findByText("You rejected the transaction.");
        expect(posts).toMatchObject([{ reason_code: "QUANTITY_WRONG" }]);
      });
    });
  });
});
