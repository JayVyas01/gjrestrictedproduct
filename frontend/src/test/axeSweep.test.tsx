// The accessibility sweep (design §7): every route, as the role that sees it, rendered in the
// whole app (session, shell, page) with the captured contracts, must pass axe.
import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { BatchDetail, LicenceDetail, RuleChange, TransactionDetail } from "@/api/types";
import { contract } from "./handlers";
import { renderApp } from "./render";

const LICENSEE: string[] = []; // the default contracts
const OFFICER = ["me_personnel", "home_personnel"];
const SUPERINTENDENT = ["me_superintendent", "home_superintendent"];
const AUTHORITY = ["me_licensing_authority", "home_licensing_authority"];
const HEAD = ["me_head_authority", "home_head_authority"];
const OWNER = ["me_software_owner", "home_software_owner"];

const ref = (name: string) => contract<TransactionDetail>(name).reference;
const ruleChange = (name: string) => contract<RuleChange>(name).id;
const BATCH = contract<BatchDetail>("oversight_batch_detail").id;
const LICENCE = contract<LicenceDetail>("licence_detail").id;

type Case = [name: string, route: string, contracts: string[]];

/** The Head Authority's or the Software Owner's read-only screens under `base`. */
function overview(who: string, base: string, as: string[]): Case[] {
  return [
    [`${who} home`, base, as],
    [`${who} transactions`, `${base}/transactions`, as],
    [
      `${who} transaction`,
      `${base}/transactions/${ref("transaction_detail_authority")}`,
      [...as, "transaction_detail_authority"],
    ],
    [`${who} batches`, `${base}/batches`, as],
    [`${who} batch`, `${base}/batches/${BATCH}`, as],
    [`${who} review periods`, `${base}/review-periods`, as],
    [`${who} licences`, `${base}/licences`, as],
    [`${who} licence`, `${base}/licences/${LICENCE}`, as],
    [`${who} rule changes`, "/rule-changes", as],
    [
      `${who} rule change`,
      `/rule-changes/${ruleChange("rule_change_decided")}`,
      [...as, "rule_change_decided"],
    ],
  ];
}

const CASES: Case[] = [
  ["sign-in", "/sign-in", []],
  ["licensee home", "/licensee", LICENSEE],
  ["licensee transactions", "/licensee/transactions", LICENSEE],
  ["seller's transaction", `/licensee/transactions/${ref("transaction_detail_seller")}`, LICENSEE],
  [
    "buyer's transaction",
    `/licensee/transactions/${ref("transaction_detail_buyer")}`,
    ["transaction_detail_buyer"],
  ],
  [
    "buyer's stock-limit reject",
    `/licensee/transactions/${ref("transaction_detail_buyer_stock_limit")}`,
    ["transaction_detail_buyer_stock_limit"],
  ],
  ["new sale", "/licensee/sale/new", LICENSEE],
  ["officer home", "/personnel", OFFICER],
  ["officer transactions", "/personnel/transactions", OFFICER],
  [
    "officer's decision",
    `/personnel/transactions/${ref("transaction_detail_officer")}`,
    [...OFFICER, "transaction_detail_officer"],
  ],
  [
    "officer's two-step decision",
    `/personnel/transactions/${ref("transaction_detail_officer_two_step")}`,
    [...OFFICER, "transaction_detail_officer_two_step"],
  ],
  ["superintendent home", "/personnel", SUPERINTENDENT],
  [
    "superintendent's final decision",
    `/personnel/transactions/${ref("transaction_detail_superintendent_final")}`,
    [...SUPERINTENDENT, "transaction_detail_superintendent_final"],
  ],
  ["superintendent batches", "/personnel/batches", SUPERINTENDENT],
  ["superintendent batch", `/personnel/batches/${BATCH}`, SUPERINTENDENT],
  ["superintendent rule changes", "/rule-changes", SUPERINTENDENT],
  ["superintendent new rule change", "/rule-changes/new", SUPERINTENDENT],
  ["authority home", "/authority", AUTHORITY],
  ["licence register", "/authority/licences", AUTHORITY],
  ["licence", `/authority/licences/${LICENCE}`, AUTHORITY],
  ["licence types", "/authority/licence-types", AUTHORITY],
  ["review periods", "/authority/review-periods", AUTHORITY],
  ["authority rule changes", "/rule-changes", AUTHORITY],
  ["new rule change", "/rule-changes/new", AUTHORITY],
  ...(
    [
      "rule_change_rule_version",
      "rule_change_new_licence_type",
      "rule_change_threshold",
      "rule_change_decided",
    ] as const
  ).map(
    (name): Case => [
      `rule change (${name})`,
      `/rule-changes/${ruleChange(name)}`,
      [...AUTHORITY, name],
    ],
  ),
  [
    "Head Authority's rule change to decide",
    `/rule-changes/${ruleChange("rule_change_rule_version")}`,
    [...HEAD, "rule_change_rule_version"],
  ],
  ...overview("Head Authority", "/head", HEAD),
  ...overview("Software Owner", "/overview", OWNER),
];

describe("accessibility sweep", () => {
  it.each(CASES)("%s (%s) has no axe violations", async (_name, route, contracts) => {
    const { container, router } = renderApp(route, { contracts });
    expect(await screen.findByRole("heading", { level: 1 }, { timeout: 5000 })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe(route); // not redirected to another page
    await waitFor(
      () => expect(screen.queryByRole("status", { name: "Loading…" })).not.toBeInTheDocument(),
      { timeout: 5000 },
    );
    expect(await axe(container)).toHaveNoViolations();
  }, 20_000);
});
