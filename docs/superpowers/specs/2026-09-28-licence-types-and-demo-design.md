# Licence Types and the Demo Milestone — Design

**Status:** Revision 3, 2026-09-30. The authorities' demo review may change it.
**Extends:** [`highlevel_plan.md`](../../../highlevel_plan.md) · **Roadmap:** [`2026-09-26-roadmap.md`](../plans/2026-09-26-roadmap.md)

> **Revision 2 change:** the **licence application and renewal process is out of scope.** A
> stakeholder confirmed the authority already runs it outside this product. Licences reach the
> platform as records entered by the Licensing Authority. Removed with it: the Applicant role,
> the application workflow, requirement checklists, review modes, renewal grace periods and the
> document store. They can be re-added if the authority asks; the earlier design is in git history
> (commit `af25b64`).
>
> **Revision 3 change (2026-09-30):** the approval chain is replaced. **One designated officer**,
> the Area Officer position covering the seller's area, approves each transaction. A
> **superintendent** (district-level position) then reviews and **signs off periodic batches** of
> approved transactions every 15 days, 1 month or 2 months, and can flag individual transactions.
> The buyer is looked up by **GSTIN**, and the system picks the licences involved. Stock moves on
> approval. See section 5b.

## 1. Summary

1. **Licence types as a first-class, configurable catalogue.** A licence type has permissions
   (may buy, sell or transport, stock limits, per-transaction limits) that differ by substance and by
   substance class. Every transaction is checked against them.
2. **Licence records come from the existing process.** The Licensing Authority records the licence
   the authority issued, including its type, scope and validity. A renewal granted outside the
   platform is recorded as a new validity period.
3. **A Demo milestone:** a polished, production-quality slice of the **transaction approval
   journey** on synthetic data, to present to the authorities before the full build.

**Top-level product priorities** (in addition to security and compliance): the product must be
**very user friendly**, and the demo must be **strong and compelling**.

## 2. Decisions

| # | Decision | Choice |
|---|---|---|
| D1 | Licence application and renewal | **Out of scope.** The existing authority process handles them. |
| D2 | Licence types | Catalogue of licence types plus **licence type rules** per (type × substance or class). The specific substance overrides its class. Anything without a rule is not permitted. |
| D3 | Rule changes | Rules are **versioned**. Permissions are **frozen on the licence** when the licence is recorded, and again when a renewal is recorded. |
| D4 | Roles | `BUYER` and `SELLER` are replaced by **`LICENSEE`**; what a licensee may do comes from its licences. |
| D5 | How licences enter the platform | The Licensing Authority records them (manual entry now, bulk CSV in Phase 2). A renewal is a new validity-period entry. |
| D6 | Demo scope | The **transaction approval journey**. |
| D7 | Language | **English only for the demo**. All text goes through i18n files so Gujarati can be added without code changes. |
| D8 | Demo data | Licence types and permissions are **demo placeholders** that the admin will update later. |
| D9 | Buyer rejection | Rejecting needs an OTP and a reason, and is final (`REJECTED_BY_BUYER`). An **in-app alert** goes to the **designated officer and the superintendent** (Revision 3). |
| D10 | Approval | **One designated officer**: the Area Officer position covering the **seller's** area approves or rejects each transaction with an OTP and a reason code (mandatory on reject). |
| D11 | Oversight | A **superintendent** (district-level position covering all areas in its district) **signs off periodic batches** of approved transactions. The review period is set per superintendent by the Licensing Authority: 15 days, 1 month or 2 months. The superintendent can **flag** individual transactions with a reason code and comment, which alerts the approving officer. Nothing is reversed. |
| D12 | Buyer lookup | The seller enters the buyer's **GSTIN**, not a licence number (a business holds one licence per compound). The system chooses the buyer's and the seller's licences for the chosen substance. |
| D13 | Stock (demo) | A stock balance per licensee per substance. On approval the seller's balance goes down and the buyer's goes up, recorded in an append-only stock movement log. |
| D14 | Reason codes | One configurable table with three kinds (officer rejection, buyer rejection, superintendent flag), seeded with defaults; each kind includes "Other" with free text. Admin can add codes later. |

**Deferred:** Head Authority edit permissions (to be defined after the demo), the oversight
dashboard, on-screen admin configuration, CSV licence import, session listing and notifications.

## 3. Roles and access

| Role | Can see | Can do |
|---|---|---|
| **Licensee** (replaces Buyer/Seller) | Own profile, own licences with the permissions each grants, own stock, own transactions (as seller or buyer) | Sell, as the seller: look up a buyer by GSTIN and start a transaction. Buy, as the buyer: confirm or reject with an OTP. Only as their licences allow. |
| **Authorised Personnel — designated officer** (Area Officer position) | Transactions whose seller is in their area; alerts addressed to their position | Approve or reject, signed with an OTP, with a reason code (mandatory on reject); acknowledge alerts |
| **Authorised Personnel — superintendent** (district position) | Batches, transactions and alerts for every area in their district | Flag transactions in a batch (reason code + comment); sign off the batch with an OTP; acknowledge alerts |
| **Licensing Authority** | All licence records; the catalogue | Record licences and renewals (new validity periods); suspend or revoke; maintain licence types and rules (new versions); assign personnel to positions |
| **Head Authority** | Everything, read-only (edit rights deferred) | Audit |
| **Software Owner** | Everything, plus system configuration | Provision personnel accounts |

Enrolment is unchanged from `highlevel_plan.md`: licence number and GSTIN, then an OTP to the
contact on file, then an account with the `LICENSEE` role.

## 4. Catalogue and licence types

- `substance_class`, for example *Spirits*, and `substance`, for example *Whisky*, which belongs to one class.
- `licence_type`, for example Manufacturer, Wholesale, Retail, Transport or Permit holder.
- `licence_type_rule`: the scope is exactly one of a substance or a substance class. Each rule is
  stored as a series of **`licence_type_rule_version`** rows, and a version is never edited. Each
  version holds `may_buy`, `may_sell`, `may_transport`, `max_stock_qty`,
  `max_per_transaction_qty`, `unit` (for example L or kg) and `validity_months`.
- **Finding the rule** (`resolve_rule(licence_type, substance)`): a rule for the specific substance
  wins over a rule for its class. If there is no rule, the licence type is **not permitted** for
  that substance.

## 5. Licence records

- A **licence** records the holder's GSTIN, registered contact (encrypted), licence number (encrypted,
  with a blind index for exact lookup), `licence_type`, its scope (a substance or a class), area,
  and status (active, suspended or revoked).
- **`licence_validity_period`** rows are append-only. A renewal granted by the authority's existing
  process is recorded as a new period by the Licensing Authority. The spec doesn't require periods
  to be continuous, because renewal timing is decided outside the platform.
- **`licence_permissions_snapshot`** rows are append-only. Each is copied from the current rule
  version when the licence is recorded and when each renewal is recorded. Changing a rule never
  changes an existing licence's terms until its next recorded renewal.
- **`trading_permitted(licence, at) -> bool`** is the only function that decides whether a licence
  allows trading. It returns true when the licence is not suspended or revoked **and** a validity
  period covers `at`.
- **Transaction checks** (plain functions, each returning a plain-language reason when it fails):
  - The seller has a licence for which `trading_permitted` is true, which covers the substance and
    whose snapshot allows `may_sell`.
  - The buyer has a licence for which `trading_permitted` is true, which covers the substance and
    whose snapshot allows `may_buy`.
  - The quantity is no more than the smaller of the seller's and the buyer's
    `max_per_transaction_qty`.
  - The buyer's recorded stock plus the quantity is no more than the buyer's `max_stock_qty`.

## 5a. Buyer rejection alerts

- **Buyer rejects:** signed with an OTP. A reason is **mandatory**, chosen from a configurable
  list of buyer reason codes: "I did not place this order", "Quantity does not match", "Wrong
  substance", "Terms dispute", or "Other" with free text. The transaction becomes
  **`REJECTED_BY_BUYER`**, which is final.
- **Alert:** the system creates one append-only `authority_alert` row (kind `BUYER_REJECTION`) for
  each of the transaction's **designated officer position and superintendent position**, addressed
  to the **position**. Whoever currently holds the position sees it, including after a transfer.
- **Alert content:** the transaction, both parties' licence numbers, the buyer's reason code and
  comment, the status timeline, and a **pattern signal**: how many buyer rejections the seller has
  had in the last 30 days (for example "3rd buyer rejection for this seller in the last 30 days").
- **Acknowledging:** an append-only `alert_acknowledgement` row (position, the person who holds it,
  time, optional note). The alert shows as acknowledged for that position. Creating and
  acknowledging an alert each write an audit event.
- **Seller view:** the rejection and the reason code appear in the seller's timeline. **The buyer's
  free-text comment is visible only to the authority.**
- **Visibility (RLS):** people currently holding a recipient position, and the Head Authority
  (read-only).
- **Delivery:** in-app (bell with a count, and a "What's next" card). SMS and email come later with
  Phase 2 notifications.

## 5b. Transactions, approval and periodic oversight (Revision 3)

**Starting a transaction (seller)**
- Enter the buyer's **GSTIN** (exact match via blind index; only the buyer's registered name is
  shown), then the substance, quantity and mandatory **transporter details** (identity, licence or
  registration number, vehicle, route).
- The system **selects the licences**: for each party, the licence that covers the substance, is
  `trading_permitted` today and allows the needed action (seller `may_sell`, buyer `may_buy`).
  Preference: a licence scoped to that substance over one scoped to its class; ties go to the
  earliest recorded. No eligible licence → a plain reason (for example "This buyer has no licence
  that allows buying Whisky").
- Every GSTIN lookup is audited (by blind index, never the GSTIN) and rate limited.

**Checks** (plain functions, each with a plain-language reason; they run at creation and again at
approval): both licences eligible as above; quantity within both licences' per-transaction limits
(using `current_permissions(licence, substance)`); seller's stock covers the quantity; buyer's stock
plus quantity stays within the buyer licence's `max_stock_qty`.

**States:** `AWAITING_BUYER` → `REJECTED_BY_BUYER` (final) or `AWAITING_OFFICER` → `APPROVED` or
`REJECTED_BY_OFFICER` (final). The seller may cancel while `AWAITING_BUYER` (`CANCELLED`, final).

**Decisions:** the buyer's confirm/reject and the officer's approve/reject are each signed with a
fresh OTP (purpose `DECISION`). Reject needs a reason code; "Other" needs free text. Each decision is
an append-only row recording the position, the person holding it at that moment, the OTP time and
the reason.

**Designated officer:** the Area Officer position covering the seller licence's area, resolved and
stored on the transaction when it is created (a later transfer does not move it; whoever holds the
position acts).

**Approval effects:** in one all-or-nothing step, re-run the checks, write the decision, move stock
(seller −q, buyer +q, recorded in `stock_movement`), write audit events.

**Periodic oversight:**
- `SuperintendentSetting` per district position: review period of 15, 30 or 60 days.
- `create_due_batches` (command; scheduled later) creates a batch per superintendent for each
  completed period, listing every transaction approved in the district in that period.
- The superintendent opens a batch, may **flag** any transaction in it (reason code + comment →
  alert to the approving officer's position), then **signs off** the batch with an OTP. A batch
  unsigned after its period ends is shown as **overdue**. Batches, items, flags and sign-offs are
  append-only.

**Visibility (RLS):** seller and buyer see their own transactions (the buyer sees the seller's
registered name and the transporter details, not the seller's contact); the designated officer's
position sees transactions routed to it; the superintendent's position sees its district;
Head Authority reads all. Free-text comments by the buyer are visible to authorities only.

## 6. The Demo milestone

**Scope.** Everything here is production quality: tested and secure, not throwaway.

**Transaction journey:**
1. The seller signs in and sees their licences, each with a **permissions card** (what it allows,
   stock limit, per-transaction limit and validity), and their stock.
2. The seller looks up the buyer by **GSTIN**. There is no browsing and no partial match; the
   system picks both parties' licences for the chosen substance.
3. The seller enters the substance and quantity and the mandatory **transporter details**
   (identity, licence or registration, vehicle, route).
4. The system checks the licence permissions and **blocks anything not allowed, with a plain
   explanation**, for example "Quantity 600 L exceeds this licence's per-transaction limit of
   500 L".
5. The buyer confirms with an OTP.
6. The **designated officer** (Area Officer for the seller's area) approves or rejects with an
   OTP and a reason code. On approval, stock moves from seller to buyer.
6a. **Oversight scene:** the **Superintendent** opens the period's batch, flags one transaction
   ("quantity unusually high"), and signs off the batch with an OTP.
7. The **status timeline** updates at each step. The approved record shows each position and who
   held it at the time.

**Buyer-rejection scene:** the seller starts a second sale, and the buyer rejects it with "I did
not place this order". The Area Officer's and Superintendent's bells light up, and the alert shows the reason and the
pattern signal. The officer acknowledges it.

**What the journey needs underneath:** areas, positions and assignments; licence records with
type, scope and frozen permissions; licence-gated enrolment; the demo catalogue and rules; a
seeded stock balances that move on approval; superintendent review periods; configurable reason codes.

**Demo tooling**
- **`make demo`:** starts Postgres, the backend and the web app with Docker Compose on a laptop,
  **fully offline**.
- **`DEMO_MODE=1`** switches on the demo features. The app **refuses to start** if `DEMO_MODE` is
  combined with production settings (DEBUG off plus a production host list).
- **`seed_demo` and `reset_demo`** build and rebuild the synthetic data:
  - fictional businesses in real Gujarat district names
  - GSTINs with state code **99** (it doesn't exist, so it can't match a real business)
  - phone numbers in a reserved dummy range
  - demo licence types, rules and permissions
  - licences, including one close to its limits and one suspended, so the checks can be shown
  - several dozen transactions in mixed states, including two earlier buyer rejections for the demo seller so the pattern signal appears
- **Persona picker** (demo mode only) on the login screen: one click fills in the credentials for
  Seller, Buyer, Area Officer, Superintendent or Licensing Authority. The **real password and
  OTP login still runs**.
- **Demo SMS inbox:** a drawer showing OTPs sent to synthetic contacts. It exists only in demo mode
  and is backed by a `DemoInboxOtpSender`, which refuses to run outside demo mode.
- **`docs/demo/script.md`:** a 10–12 minute storyline covering the order of personas, clicks and
  talking points, including a blocked over-limit attempt, a buyer rejection alert and an officer rejection with a reason, plus a
  rehearsal and reset checklist.

## 7. User experience principles (every screen)

- **A "What's next" card** on every role's home screen stating the next action, for example
  "2 transactions waiting for your approval".
- **Step-by-step wizards** with a progress bar and automatic draft saving. Every field has a
  plain-language explanation.
- **A status timeline** on every transaction, like a parcel tracker, including rejection reasons.
- **Error messages that say how to fix the problem.** Never raw codes.
- **WCAG 2.1 AA**, responsive down to phone width, and a calm, official visual style.
- **Frontend:** React, TypeScript and Vite with an accessible component library. All text goes
  through i18n files (English now, Gujarati later). The visual direction is settled in the Demo
  milestone plan.

## 8. Roadmap impact

**Order:** Phase 1, then the Demo milestone, then the authorities' review, then Phases 2–6.

| # | Phase | Change |
|---|---|---|
| 1 | Foundation | `Role`: replace `BUYER`/`SELLER` with `LICENSEE` |
| D | **Demo milestone (new)** | Section 6 |
| 2 | Licensing & positions | Licence types catalogue and rule versions, licence records with type, scope, permissions snapshot and validity periods, `trading_permitted()`, and recording renewals |
| 3 | Inventory | Stock capped by the licence's `max_stock_qty` |
| 4 | Transactions & approvals | Uses `trading_permitted` and the permission and limit checks; transporters need a Transport licence |
| 5 | Oversight & compliance | Head Authority edit rights (to be defined) |
| 6 | Hardening | Unchanged |

## 9. Testing

- **Rules:** a specific substance overrides its class; anything without a rule is not permitted; a
  new rule version doesn't change existing licences; permissions are frozen when a licence and its
  renewals are recorded.
- **`trading_permitted`:** before, at and after the validity period; gaps between periods;
  suspended or revoked licences.
- **Transaction checks:** every rule in section 5, each with its exact plain-language message.
- **Buyer rejection:** refused without a reason or an OTP; `REJECTED_BY_BUYER` is final; one alert
  per chain position; the alert moves to the new holder after a transfer; only recipient positions
  and the Head Authority can see it (RLS and IDOR); the seller never sees the buyer's comment; the
  pattern count covers exactly the last 30 days.
- **Access:** RLS and IDOR tests. A licensee sees only their own licences, stock and transactions.
  Personnel see only transactions for positions they currently hold, and lose access after a
  transfer. The Head Authority is read-only.
- **Demo:** `seed_demo` then `reset_demo` gives the same state every time; demo features and the app
  itself refuse to start without `DEMO_MODE` or when combined with production settings; the
  synthetic GSTINs all use state code 99.
- **End to end** (browser, Playwright): the transaction journey following the demo script,
  finishing with `verify_audit_chain` passing.

## 10. Open items

- The real licence types, permissions and stock limits (demo placeholders until then; the admin
  will update them).
- Head Authority edit permissions (deferred).
- Whether the platform should later link to the authority's existing licence system (import or
  sync) instead of manual and CSV entry.
- Authorities' demo feedback, which may change any part of this design.
