// Each contract captured from the real backend must carry the keys its hand-written type
// requires. `satisfies (keyof T)[]` ties each key list to its type, so renaming a field in a type
// fails the type check, and a contract that lost the field fails here.

import { describe, expect, it } from "vitest";
import { contracts } from "@/test/handlers";
import type * as T from "./types";

const keysOf = <K extends string>(keys: K[]) => keys;

const ME = keysOf(["user_id", "role", "display_name", "positions"] satisfies (keyof T.Me)[]);
const HOME = keysOf(["role", "counts"] satisfies (keyof T.Home)[]);
const CHALLENGE = keysOf(["challenge_id"] satisfies (keyof T.Challenge)[]);
const SUMMARY = keysOf([
  "reference",
  "status",
  "status_label",
  "substance",
  "quantity",
  "unit",
  "seller_name",
  "buyer_name",
  "created_at",
  "your_role",
  "approval_chain",
  "approval_chain_label",
] satisfies (keyof T.TransactionSummary)[]);
const DETAIL = keysOf([
  ...SUMMARY,
  "transport",
  "designated_officer",
  "timeline",
  "next_action",
  "can_decide",
  "allowed_outcomes",
  "stock_limit_problem",
] satisfies (keyof T.TransactionDetail)[]);
const BATCH = keysOf([
  "id",
  "position",
  "period_start",
  "period_end",
  "due_on",
  "status",
  "item_count",
  "flag_count",
  "signed_at",
  "signed_by",
] satisfies (keyof T.BatchSummary)[]);
const ALERT = keysOf([
  "id",
  "kind",
  "kind_label",
  "transaction_reference",
  "reason",
  "pattern",
  "pattern_count",
  "comment",
  "created_at",
  "seller_name",
  "buyer_name",
  "acknowledged",
  "note",
] satisfies (keyof T.Alert)[]);
const RULE_CHANGE = keysOf([
  "id",
  "kind",
  "status",
  "justification",
  "drafted_by_role",
  "proposed",
  "current",
  "decision",
  "can_withdraw",
  "can_decide",
] satisfies (keyof T.RuleChange)[]);
const LICENCE_ROW = keysOf([
  "id",
  "licence_number",
  "holder_name",
  "licence_type",
  "scope",
  "area",
  "status",
  "valid_to",
] satisfies (keyof T.LicenceRow)[]);
const REVIEW_SETTING = keysOf([
  "position_id",
  "title",
  "area",
  "period_days",
  "starts_on",
  "current_period_end",
  "last_batch_end",
] satisfies (keyof T.ReviewSetting)[]);
const ERROR = keysOf(["detail"] satisfies (keyof T.ErrorBody)[]);

type Guard = { keys: string[]; list?: boolean; nested?: Record<string, string[]> };

// Contract name (or `prefix*`) → the keys its type requires.
const GUARDS: Record<string, Guard> = {
  "me_*": { keys: ME },
  "home_*": { keys: HOME },
  login_start: { keys: CHALLENGE },
  decision_code: { keys: CHALLENGE },
  login_verify: { keys: ["user_id", "role"] satisfies (keyof T.LoginVerified)[] },
  transactions_list: { keys: SUMMARY, list: true },
  transaction_created: { keys: DETAIL },
  "transaction_detail_*": {
    keys: DETAIL,
    nested: {
      transport: ["name", "id_number", "vehicle_number", "route"],
      "timeline[0]": [
        "step",
        "outcome",
        "at",
        "by",
        "reason",
        "comment",
        "held_by",
      ] satisfies (keyof T.TimelineEvent)[],
    },
  },
  "transaction_check_*": {
    keys: ["ok", "reasons", "approval_chain"] satisfies (keyof T.CheckResult)[],
  },
  buyer_lookup: { keys: ["holder_name"] satisfies (keyof T.BuyerFound)[] },
  licences_mine: {
    keys: [
      "licence_number",
      "holder_name",
      "scope",
      "scope_kind",
      "unit",
      "status",
      "valid_to",
      "trading_permitted",
      "may_buy",
      "may_sell",
      "max_stock_qty",
      "max_per_transaction_qty",
    ] satisfies (keyof T.LicenceCard)[],
    list: true,
  },
  stock_mine: {
    keys: ["substance_code", "substance", "quantity", "unit"] satisfies (keyof T.StockRow)[],
    list: true,
  },
  "reason_codes_*": {
    keys: ["code", "label", "requires_text"] satisfies (keyof T.ReasonCode)[],
    list: true,
  },
  catalogue_substances: {
    keys: ["code", "name", "substance_class", "unit"] satisfies (keyof T.Substance)[],
    list: true,
  },
  catalogue_classes: {
    keys: ["code", "name", "unit"] satisfies (keyof T.SubstanceClass)[],
    list: true,
  },
  catalogue_licence_types: {
    keys: ["code", "name", "description", "rules"] satisfies (keyof T.LicenceType)[],
    list: true,
    nested: {
      "rules[0]": [
        "scope",
        "scope_kind",
        "version",
        "may_buy",
        "max_stock_qty",
        "validity_months",
      ] satisfies (keyof T.LicenceTypeRule)[],
    },
  },
  catalogue_approval_thresholds: {
    keys: [
      "scope",
      "scope_kind",
      "superintendent_above_qty",
      "unit",
      "version",
    ] satisfies (keyof T.ApprovalThreshold)[],
    list: true,
  },
  alerts: {
    keys: ["unacknowledged", "alerts"] satisfies (keyof T.AlertList)[],
    nested: { "alerts[0]": ALERT },
  },
  alert_acknowledged: { keys: ALERT },
  oversight_batches: { keys: BATCH, list: true },
  oversight_batch_detail: {
    keys: [...BATCH, "items", "can_sign"] satisfies (keyof T.BatchDetail)[],
    nested: {
      "items[0]": [
        "reference",
        "seller_name",
        "buyer_name",
        "approved_by_position",
        "approved_by_superintendent",
        "flag",
      ] satisfies (keyof T.BatchItem)[],
    },
  },
  review_settings: { keys: REVIEW_SETTING, list: true },
  review_setting_saved: { keys: REVIEW_SETTING },
  rule_changes: { keys: RULE_CHANGE, list: true },
  "rule_change_*": { keys: RULE_CHANGE },
  licences_register: {
    keys: ["count", "page", "page_size", "results"] satisfies (keyof T.LicenceRegister)[],
    nested: { "results[0]": LICENCE_ROW },
  },
  licence_search: {
    keys: ["count", "page", "page_size", "results"] satisfies (keyof T.LicenceRegister)[],
    nested: { "results[0]": LICENCE_ROW },
  },
  licence_detail: {
    keys: [...LICENCE_ROW, "gstin", "periods", "permissions"] satisfies (keyof T.LicenceDetail)[],
    nested: {
      permissions: [
        "may_buy",
        "may_sell",
        "may_transport",
        "max_stock_qty",
        "max_per_transaction_qty",
        "unit",
        "trading_permitted",
        "valid_from",
        "valid_to",
      ] satisfies (keyof T.LicenceDetail["permissions"])[],
    },
  },
  demo_personas: {
    keys: ["key", "label", "description", "user_id", "password"] satisfies (keyof T.DemoPersona)[],
    list: true,
  },
  demo_inbox: {
    keys: [
      "display_name",
      "contact_last4",
      "code",
      "created_at",
    ] satisfies (keyof T.DemoInboxMessage)[],
    list: true,
  },
  error_400_field_errors: { keys: [] },
  "error_*": { keys: ERROR },
};

function guardFor(name: string): Guard | undefined {
  // An exact name wins over a prefix; a longer prefix wins over a shorter one.
  if (GUARDS[name]) return GUARDS[name];
  const prefixes = Object.keys(GUARDS)
    .filter((key) => key.endsWith("*") && name.startsWith(key.slice(0, -1)))
    .sort((a, b) => b.length - a.length);
  return prefixes[0] ? GUARDS[prefixes[0]] : undefined;
}

function at(value: unknown, path: string): unknown {
  const match = /^(\w+)(\[0\])?$/.exec(path);
  if (!match || !value || typeof value !== "object") return undefined;
  const child = (value as Record<string, unknown>)[match[1]!];
  return match[2] ? (child as unknown[])[0] : child;
}

function missing(value: unknown, keys: string[]): string[] {
  if (!value || typeof value !== "object") return ["(not an object)"];
  return keys.filter((key) => !(key in value));
}

const names = Object.keys(contracts).sort();

describe("API contracts match the hand-written types", () => {
  it("found the contract files", () => {
    expect(names.length).toBeGreaterThan(40);
  });

  it.each(names)("%s", (name) => {
    const guard = guardFor(name);
    expect(guard, `no type guard for contract "${name}"`).toBeDefined();
    const { keys, list, nested = {} } = guard!;
    const body = contracts[name];
    if (list) expect(Array.isArray(body) && body.length > 0, "a non-empty list").toBe(true);
    const sample = list ? (body as unknown[])[0] : body;
    expect(missing(sample, keys)).toEqual([]);
    for (const [path, required] of Object.entries(nested)) {
      expect(missing(at(sample, path), required), path).toEqual([]);
    }
  });

  it("a buyer over their stock limit may only reject, and the seller never sees the problem", () => {
    const buyer = contracts.transaction_detail_buyer_stock_limit as T.TransactionDetail;
    const seller = contracts.transaction_detail_seller as T.TransactionDetail;
    expect(buyer.allowed_outcomes).toEqual(["REJECT"]);
    expect(buyer.stock_limit_problem).toEqual(expect.any(String));
    expect(seller.stock_limit_problem).toBeNull();
  });

  it("field errors are lists of messages", () => {
    const body = contracts.error_400_field_errors as Record<string, unknown>;
    expect(Object.values(body).every(Array.isArray)).toBe(true);
  });
});
