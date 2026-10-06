// Hand-written types for the JSON the backend returns. Each one is checked against the
// contracts captured from the real backend (src/test/contracts, see contracts.test.ts).
// Quantities are decimal strings ("150.000") and dates ISO strings, exactly as sent.

export type Role =
  "LICENSEE" | "PERSONNEL" | "LICENSING_AUTHORITY" | "HEAD_AUTHORITY" | "SOFTWARE_OWNER";

// Auth ------------------------------------------------------------------------------------------

export interface Challenge {
  challenge_id: string;
}

/** The role chosen at sign-in; officers sign in as AREA_OFFICER or SUPERINTENDENT. */
export type LoginRole =
  | "PARTY"
  | "LICENSING_AUTHORITY"
  | "AREA_OFFICER"
  | "SUPERINTENDENT"
  | "HEAD_AUTHORITY"
  | "SOFTWARE_OWNER";

export interface LoginVerified {
  user_id: string;
  role: Role;
  /** A password the system issued: every other API answers 403 until it is changed. */
  must_change_password: boolean;
}

export interface Position {
  id: number;
  title: string;
  level: "STATE" | "DISTRICT" | "TALUKA";
}

export interface Me {
  user_id: string;
  role: Role;
  display_name: string;
  positions: Position[];
  must_change_password: boolean;
}

// Home: each role gets a different subset of counts ----------------------------------------------

export interface HomeCounts {
  awaiting_your_decision?: number;
  sales_in_progress?: number;
  unacknowledged_alerts?: number;
  open_batches?: number;
  overdue_batches?: number;
  next_due?: string | null;
  your_open_rule_changes?: number;
  expiring_licences_30d?: number;
  districts_without_review_period?: number;
  rule_changes_submitted?: number;
  rule_changes_awaiting_you?: number;
  awaiting_superintendent?: number;
}

export interface Home {
  role: Role;
  counts: HomeCounts;
}

// Transactions ----------------------------------------------------------------------------------

export type TransactionStatus =
  | "AWAITING_BUYER"
  | "AWAITING_OFFICER"
  | "AWAITING_SUPERINTENDENT"
  | "APPROVED"
  | "REJECTED_BY_BUYER"
  | "REJECTED_BY_OFFICER"
  | "REJECTED_BY_SUPERINTENDENT"
  | "CANCELLED";
export type Outcome = "CONFIRM" | "APPROVE" | "RECOMMEND" | "REJECT";
export type ApprovalChain = "OFFICER" | "OFFICER_THEN_SUPERINTENDENT";
export type ViewerRole = "seller" | "buyer" | "officer" | "superintendent" | "authority";

export interface TransactionSummary {
  reference: string;
  status: TransactionStatus;
  status_label: string;
  substance: string;
  quantity: string;
  unit: string;
  seller_name: string;
  buyer_name: string;
  created_at: string;
  your_role: ViewerRole;
  approval_chain: ApprovalChain;
  approval_chain_label: string;
}

export interface TimelineEvent {
  step: "SELLER" | "BUYER" | "OFFICER" | "SUPERINTENDENT";
  outcome: "STARTED" | Outcome | "CANCEL";
  at: string;
  by: string;
  reason: string | null;
  comment: string | null;
  held_by: string | null;
}

export interface TransactionDetail extends TransactionSummary {
  transport: { name: string; id_number: string; vehicle_number: string; route: string };
  designated_officer: string;
  timeline: TimelineEvent[];
  next_action: string | null;
  can_decide: boolean;
  allowed_outcomes: Outcome[];
  /** The buyer's own stock-limit problem; only ever sent to the buyer. */
  stock_limit_problem: string | null;
}

export interface CheckResult {
  ok: boolean;
  reasons: string[];
  approval_chain: ApprovalChain | null;
}

export interface BuyerFound {
  holder_name: string;
}

// The licensee's own records --------------------------------------------------------------------

export type LicenceStatus = "ACTIVE" | "SUSPENDED" | "REVOKED";

export interface LicenceCard {
  licence_number: string;
  holder_name: string;
  licence_type: string;
  scope: string;
  /** Whether `scope` names a substance or a class. */
  scope_kind: ScopeKind;
  /** The substance's unit, or the class's shared unit (null only for a class with no substances). */
  unit: string | null;
  status: LicenceStatus;
  valid_from: string | null;
  valid_to: string | null;
  trading_permitted: boolean;
  may_buy: boolean;
  may_sell: boolean;
  may_transport: boolean;
  max_stock_qty: string;
  max_per_transaction_qty: string;
}

export interface StockRow {
  substance_code: string;
  substance: string;
  quantity: string;
  unit: string;
}

// Catalogue and reasons -------------------------------------------------------------------------

export type ReasonKind = "BUYER_REJECTION" | "OFFICER_REJECTION" | "SUPERINTENDENT_FLAG";

export interface ReasonCode {
  code: string;
  label: string;
  requires_text: boolean;
}

export interface Substance {
  code: string;
  name: string;
  substance_class: string;
  unit: string;
}

export interface SubstanceClass {
  code: string;
  name: string;
  unit: string | null;
}

export type ScopeKind = "class" | "substance";

export interface LicenceTypeRule {
  scope: string;
  scope_code: string;
  scope_kind: ScopeKind;
  unit: string | null;
  version: number;
  may_buy: boolean;
  may_sell: boolean;
  may_transport: boolean;
  max_stock_qty: string;
  max_per_transaction_qty: string;
  validity_months: number;
}

export interface LicenceType {
  code: string;
  name: string;
  description: string;
  rules: LicenceTypeRule[];
}

export interface ApprovalThreshold {
  scope: string;
  scope_kind: ScopeKind;
  superintendent_above_qty: string;
  unit: string | null;
  version: number;
}

// Alerts ----------------------------------------------------------------------------------------

export interface Alert {
  id: number;
  kind: "BUYER_REJECTION" | "SUPERINTENDENT_FLAG";
  kind_label: string;
  created_at: string;
  transaction_reference: string;
  substance: string;
  quantity: string;
  unit: string;
  seller_name: string;
  buyer_name: string;
  reason: string;
  comment: string | null;
  pattern: string | null;
  /** The count behind `pattern` (buyer rejections only); 2 or more is a repeat. */
  pattern_count: number | null;
  acknowledged: boolean;
  acknowledged_by: string | null;
  acknowledged_at: string | null;
  note: string | null;
}

export interface AlertList {
  unacknowledged: number;
  alerts: Alert[];
}

// Superintendent batches and review periods ----------------------------------------------------

export type BatchStatus = "OPEN" | "OVERDUE" | "SIGNED";

export interface BatchSummary {
  id: number;
  position: string;
  period_start: string;
  period_end: string;
  due_on: string;
  status: BatchStatus;
  item_count: number;
  flag_count: number;
  signed_at: string | null;
  signed_by: string | null;
}

export interface BatchItem {
  reference: string;
  substance: string;
  quantity: string;
  unit: string;
  seller_name: string;
  buyer_name: string;
  approved_at: string;
  approved_by_position: string;
  approved_by_superintendent: boolean;
  flag: { reason: string; comment: string | null; flagged_at: string } | null;
}

export interface BatchDetail extends BatchSummary {
  items: BatchItem[];
  can_sign: boolean;
}

export interface ReviewSetting {
  position_id: number;
  title: string;
  area: string;
  period_days: number | null;
  starts_on: string | null;
  current_period_end: string | null;
  last_batch_end: string | null;
}

// Rule changes ----------------------------------------------------------------------------------

export type ProposalKind = "NEW_LICENCE_TYPE" | "RULE_VERSION" | "APPROVAL_THRESHOLD";
export type ProposalStatus = "SUBMITTED" | "APPROVED" | "REJECTED" | "WITHDRAWN";

/** The proposed values (their keys depend on the kind) with display names resolved. */
export type ProposalValues = Record<string, string | number | boolean | null>;

export interface RuleChange {
  id: number;
  kind: ProposalKind;
  kind_label: string;
  status: ProposalStatus;
  status_label: string;
  justification: string;
  drafted_at: string;
  drafted_by_role: string;
  /** Sent to Head Authority and Software Owner viewers only. */
  drafted_by?: string;
  proposed: ProposalValues;
  /** What the catalogue holds today for the same scope, while the proposal is open. */
  current: ProposalValues | null;
  decision: { outcome: ProposalStatus; decided_at: string | null; note: string | null } | null;
  can_withdraw: boolean;
  can_decide: boolean;
}

// The licence register --------------------------------------------------------------------------

export interface LicenceRow {
  id: number;
  licence_number: string;
  holder_name: string;
  licence_type: string;
  scope: string;
  area: string;
  status: LicenceStatus;
  valid_to: string | null;
}

export interface LicenceRegister {
  count: number;
  page: number;
  page_size: number;
  results: LicenceRow[];
}

export interface LicenceDetail extends LicenceRow {
  gstin: string;
  periods: { starts_on: string; ends_on: string }[];
  /** The permissions card's fields: allowances, limits and unit, and the current period. */
  permissions: Pick<
    LicenceCard,
    | "may_buy"
    | "may_sell"
    | "may_transport"
    | "max_stock_qty"
    | "max_per_transaction_qty"
    | "unit"
    | "trading_permitted"
    | "valid_from"
    | "valid_to"
  >;
}

// Error bodies ----------------------------------------------------------------------------------

/** A refusal: `detail` always, `reasons` on 422. A 400 may instead carry field errors. */
export interface ErrorBody {
  detail?: string;
  reasons?: string[];
  [field: string]: unknown;
}

// Demo mode only (D4): these endpoints answer 404 outside demo mode ----------------------------

/** A synthetic account the persona picker signs in as (the shared demo password included). */
export interface DemoPersona {
  key: string;
  label: string;
  description: string;
  role: LoginRole;
  /** A party's GSTIN or an official's email. */
  identifier: string;
  password: string;
}

/** A code the demo SMS inbox "sent": the recipient's name and the last 4 digits only. */
export interface DemoInboxMessage {
  display_name: string;
  contact_last4: string;
  code: string;
  created_at: string;
}

/** What party sign-up asks for (POST /api/demo/signup/start; the answer is a `Challenge`). */
export interface DemoSignupForm {
  gstin: string;
  /** Must match the phone on file of an ACTIVE licence for the GSTIN; the code goes there. */
  phone: string;
  email: string;
  business_name: string;
  address: string;
  password: string;
}

/** The account a completed sign-up created (not signed in yet). */
export interface DemoSignupCompleted {
  user_id: string;
}

/** A licensed business with no account yet, offered to testers for sign-up. */
export interface DemoSignupCandidate {
  gstin: string;
  business_name: string;
  phone_on_file: string;
}
