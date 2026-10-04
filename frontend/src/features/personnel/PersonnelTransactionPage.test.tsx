import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { TransactionDetail } from "@/api/types";
import { contract, serveContract } from "@/test/handlers";
import { renderApp } from "@/test/render";
import { server } from "@/test/server";

const OFFICER = contract<TransactionDetail>("transaction_detail_officer");
const TWO_STEP = contract<TransactionDetail>("transaction_detail_officer_two_step");
const FINAL = contract<TransactionDetail>("transaction_detail_superintendent_final");
const AUTHORITY = contract<TransactionDetail>("transaction_detail_authority");
const CHALLENGE = contract<{ challenge_id: string }>("decision_code").challenge_id;

const AS_OFFICER = ["me_personnel", "home_personnel"];
const AS_SUPERINTENDENT = ["me_superintendent", "home_superintendent"];

const at = (tx: TransactionDetail) => `/personnel/transactions/${tx.reference}`;

function serveDetail(tx: TransactionDetail) {
  server.use(http.get("/api/transactions/:reference", () => HttpResponse.json(tx)));
}

function recordDecisions() {
  const bodies: unknown[] = [];
  server.use(
    http.post("/api/transactions/:reference/decide", async ({ request }) => {
      bodies.push(await request.json());
      return HttpResponse.json(contract<object>("transaction_detail_authority"));
    }),
  );
  return bodies;
}

type User = ReturnType<typeof renderApp>["user"];

async function enterCode(user: User) {
  const dialog = await screen.findByRole("dialog");
  await within(dialog).findByText(/The code expires in/);
  await user.click(within(dialog).getByLabelText("Digit 1 of 6"));
  await user.paste("123456");
  await user.click(within(dialog).getByRole("button", { name: "Confirm" }));
}

async function decisionButtons() {
  const decision = await screen.findByRole("region", { name: "Your decision" });
  return within(decision)
    .getAllByRole("button")
    .map((button) => button.textContent);
}

describe("Personnel transaction detail", () => {
  it("an officer on the officer chain sees Approve and Reject", async () => {
    serveDetail(OFFICER);
    const { container } = renderApp(at(OFFICER), { contracts: AS_OFFICER });
    expect(await decisionButtons()).toEqual(["Approve", "Reject"]);
    expect(screen.getByRole("link", { name: "Back to transactions" })).toHaveAttribute(
      "href",
      "/personnel/transactions",
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("an officer on the two-step chain sees only Recommend and Reject, and recommends with a code", async () => {
    serveDetail(TWO_STEP);
    const posts = recordDecisions();
    const { user, container } = renderApp(at(TWO_STEP), { contracts: AS_OFFICER });
    expect(await decisionButtons()).toEqual(["Recommend for approval", "Reject"]);
    expect(screen.queryByRole("button", { name: /^Approve|final approval/ })).toBeNull();
    expect(screen.getByText("Officer, then superintendent")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();

    await user.click(screen.getByRole("button", { name: "Recommend for approval" }));
    expect(
      await screen.findByRole("dialog", { name: "Recommend this transaction" }),
    ).toBeInTheDocument();
    await enterCode(user);
    expect(await screen.findByText("You recommended the transaction.")).toBeInTheDocument();
    expect(posts).toEqual([{ challenge_id: CHALLENGE, code: "123456", outcome: "RECOMMEND" }]);
  });

  it("a dual holder on the two-step chain sees Approve", async () => {
    // Holding both positions, the server allows the approval at both levels at once.
    serveDetail({ ...TWO_STEP, allowed_outcomes: ["APPROVE", "REJECT"] });
    renderApp(at(TWO_STEP), { contracts: AS_OFFICER });
    expect(await decisionButtons()).toEqual(["Approve", "Reject"]);
    expect(screen.queryByRole("button", { name: /Recommend/ })).toBeNull();
  });

  it("a superintendent sees Give final approval, with the officer's recommendation", async () => {
    serveDetail(FINAL);
    const posts = recordDecisions();
    const { user, container } = renderApp(at(FINAL), { contracts: AS_SUPERINTENDENT });
    expect(await decisionButtons()).toEqual(["Give final approval", "Reject"]);

    const timeline = screen.getByRole("list", { name: "Progress" });
    expect(within(timeline).getByText("Officer recommended approval")).toBeInTheDocument();
    expect(within(timeline).getByText("Held by GJ22NFMMPLZF")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();

    await user.click(screen.getByRole("button", { name: "Give final approval" }));
    expect(await screen.findByRole("dialog", { name: "Give final approval" })).toBeInTheDocument();
    await enterCode(user);
    expect(await screen.findByText("You gave final approval.")).toBeInTheDocument();
    expect(posts).toEqual([{ challenge_id: CHALLENGE, code: "123456", outcome: "APPROVE" }]);
  });

  it("a superintendent rejects with an officer-rejection reason", async () => {
    serveDetail(FINAL);
    const posts = recordDecisions();
    const reasonKinds: string[] = [];
    server.use(
      http.get("/api/reason-codes", ({ request }) => {
        reasonKinds.push(new URL(request.url).searchParams.get("kind") ?? "");
        return HttpResponse.json(contract<object>("reason_codes_officer_rejection"));
      }),
    );
    const { user } = renderApp(at(FINAL), { contracts: AS_SUPERINTENDENT });
    await user.click(await screen.findByRole("button", { name: "Reject" }));
    await user.click(
      await screen.findByRole("radio", { name: "Quantity mismatch (expected vs found)" }),
    );
    await user.click(screen.getByRole("button", { name: "Continue to reject" }));
    expect(
      await screen.findByRole("dialog", { name: "Reject this transaction" }),
    ).toBeInTheDocument();
    await enterCode(user);
    expect(await screen.findByText("You rejected the transaction.")).toBeInTheDocument();
    expect(reasonKinds).toEqual(["OFFICER_REJECTION"]);
    expect(posts).toEqual([
      {
        challenge_id: CHALLENGE,
        code: "123456",
        outcome: "REJECT",
        reason_code: "QUANTITY_MISMATCH",
        comment: "",
      },
    ]);
  });

  it("never offers an outcome the server did not allow", async () => {
    serveDetail({ ...FINAL, allowed_outcomes: ["REJECT"] });
    renderApp(at(FINAL), { contracts: AS_SUPERINTENDENT });
    expect(await decisionButtons()).toEqual(["Reject"]);
  });

  it("shows a 422 refusal's reasons", async () => {
    serveDetail(OFFICER);
    server.use(
      serveContract("error_422_transaction_refused", {
        method: "post",
        path: "/api/transactions/:reference/decide",
      }),
    );
    const { user } = renderApp(at(OFFICER), { contracts: AS_OFFICER });
    await user.click(await screen.findByRole("button", { name: "Approve" }));
    await enterCode(user);
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("This transaction can't go ahead.");
    expect(alert).toHaveTextContent(
      "Quantity 600 L exceeds your licence's per-transaction limit of 500 L.",
    );
  });

  it("shows the authority fields the server sends, with no decision", async () => {
    const timeline = AUTHORITY.timeline.map((event) =>
      event.step === "SUPERINTENDENT" ? { ...event, comment: "Checked the stock register" } : event,
    );
    serveDetail({ ...AUTHORITY, timeline });
    const { container } = renderApp(at(AUTHORITY), { contracts: AS_OFFICER });
    const progress = await screen.findByRole("list", { name: "Progress" });
    expect(within(progress).getByText("Officer recommended approval")).toBeInTheDocument();
    expect(within(progress).getByText("Comment: Checked the stock register")).toBeInTheDocument();
    expect(within(progress).getByText("Held by GJ5SVTKLEY5X")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Your decision" })).not.toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });
});
