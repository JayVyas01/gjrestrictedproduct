# Licence Types and the Demo Milestone — Design

**Status:** Revision 2, 2026-09-28. The authorities' demo review may change it.
**Extends:** [`highlevel_plan.md`](../../../highlevel_plan.md) · **Roadmap:** [`2026-09-26-roadmap.md`](../plans/2026-09-26-roadmap.md)

> **Revision 2 change:** the **licence application and renewal process is out of scope.** A
> stakeholder confirmed the authority already runs it outside this product. Licences reach the
> platform as records entered by the Licensing Authority. Removed with it: the Applicant role,
> the application workflow, requirement checklists, review modes, renewal grace periods and the
> document store. They can be re-added if the authority asks; the earlier design is in git history
> (commit `af25b64`).

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

**Deferred:** Head Authority edit permissions (to be defined after the demo), the oversight
dashboard, on-screen admin configuration, CSV licence import, session listing and notifications.

## 3. Roles and access

| Role | Can see | Can do |
|---|---|---|
| **Licensee** (replaces Buyer/Seller) | Own profile, own licences with the permissions each grants, own stock, own transactions | Sell, as the seller: look up a buyer by exact licence number and start a transaction. Buy, as the buyer: confirm or reject with an OTP. Only as their licences allow. |
| **Authorised Personnel** | Transactions sent to a position they currently hold, plus the parties' licence status needed to decide | Accept or reject at their step, signed with an OTP, with a reason code (mandatory on reject) |
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

## 6. The Demo milestone

**Scope.** Everything here is production quality: tested and secure, not throwaway.

**Transaction journey:**
1. The seller signs in and sees their licences, each with a **permissions card** (what it allows,
   stock limit, per-transaction limit and validity), and their stock.
2. The seller looks up the buyer by **exact licence number**. There is no browsing and no partial
   match.
3. The seller enters the substance and quantity and the mandatory **transporter details**
   (identity, licence or registration, vehicle, route).
4. The system checks the licence permissions and **blocks anything not allowed, with a plain
   explanation**, for example "Quantity 600 L exceeds this licence's per-transaction limit of
   500 L".
5. The buyer confirms with an OTP.
6. The **Area Officer**, then the **District Officer** accept or reject with an OTP and reason
   codes. The approval chain is resolved from the area and the substance severity.
7. The **status timeline** updates at each step. The approved record shows each position and who
   held it at the time.

**What the journey needs underneath:** areas, positions and assignments; licence records with
type, scope and frozen permissions; licence-gated enrolment; the demo catalogue and rules; a
seeded read-only stock list per licensee; a demo approval policy matrix; configurable reason codes.

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
  - several dozen transactions in mixed states
- **Persona picker** (demo mode only) on the login screen: one click fills in the credentials for
  Seller, Buyer, Area Officer, District Officer or Licensing Authority. The **real password and
  OTP login still runs**.
- **Demo SMS inbox:** a drawer showing OTPs sent to synthetic contacts. It exists only in demo mode
  and is backed by a `DemoInboxOtpSender`, which refuses to run outside demo mode.
- **`docs/demo/script.md`:** a 10–12 minute storyline covering the order of personas, clicks and
  talking points, including a blocked over-limit attempt and a rejection with a reason, plus a
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
