# Gujarat Restricted-Items Transaction Authorisation Platform: Design Plan

## Context
Gujarat restricts certain items (liquor and prohibited substances first). Buyers and sellers are licensed, and every sale is **seller-initiated** and must be authorised by the correct government position with a tamper-evident record. This is a control/authorisation system for government oversight, not a marketplace. The repo (`/Users/jayvyas/gjrestrictedproduct`) is empty apart from README and .gitignore, so this is a greenfield build.

Decisions made so far:
- Items: liquor / prohibited substances (item model designed so more categories can be added later).
- Scope v1: authorisation + audit record only. No payments, no goods movement/e-pass beyond the record itself.
- Identity: licence-gated self-enrolment, not open self-signup. The Licensing Authority pre-issues and holds licence records (each with a linked GSTIN and a contact phone/email for that GSTIN). A user enrols by entering their licence number + GSTIN; the system validates this pair against the Licensing Authority's records, then sends an OTP to the phone/email already on file for that GSTIN (never to an address the user types in) to prove control of it. Only after OTP verification is an account created, with a system-generated user ID and a password the user sets. Forgot-password uses the same OTP-to-registered-contact flow. No one can create an account for a licence number/GSTIN pair that isn't already on record, and no one can redirect OTP delivery to a different contact.
- Platform: responsive web app, hosted in an India cloud region (data residency).
- Architecture: modular monolith on Postgres (row-level security, hash-chained append-only audit log).
- **No open catalogue/browsing.** A licensed user (seller) can only view and manage their own items/inventory — never another seller's. There is no buyer-facing marketplace. A seller initiates a sale by looking up a specific buyer's licence (exact ID/number lookup, not a browsable list) and submitting a transaction against them.
- **Transporter details are mandatory** on every seller-initiated transaction: transporter identity, licence/registration, vehicle details, and route/area.
- **Authority is positional, not personal.** Approval chains are resolved from (area/jurisdiction of the transaction) x (item severity/complexity) to a chain of **positions** — e.g. Area Officer -> District Officer -> State Officer — not to named individuals. Whoever currently holds a position acts for it. A personnel transfer reassigns the position-holder; it does not change the chain itself, and historical approvals stay attributed to "position, held by [X] at the time."
- **Security and legal compliance are top-level, non-negotiable requirements**, not hardening done later: strict least-privilege access, DPDP Act 2023 (consent/purpose limitation, data minimisation, breach notification, data-principal rights, data-localisation), and the Gujarat Prohibition Act plus other applicable prohibition/licensing acts drive retention, disclosure and access-logging rules baked into the design from the start.

## Roles and data access
| Role | Can see | Can do |
|---|---|---|
| Buyer (licensed) | Own profile, own licence, own incoming/past transactions | OTP-authorise (accept/reject with comment) a transaction a seller initiated against them |
| Seller (licensed) | Own profile, own item inventory only, own initiated transactions | Look up a specific buyer by licence ID, initiate a sale with item + transporter details |
| Authorised Personnel (position-holder) | Only transactions routed to their position, plus the parties' licence status needed for that decision | OTP-authorise (accept/reject with comment) at their step in the chain |
| Licensing Authority | All licence records and accounts it issued | Onboard licensees (licence/GSTIN/contact records), suspend/revoke; assign/transfer personnel to positions |
| Software Owner / Head Authority (admin rights) | Everything, incl. system configuration | The only roles that can create or reset an Authorised Personnel account (id + initial password); assign personnel to positions |
| Head Authority (oversight rights) | Everything, read-only, including the full audit trail | Audit and export; no writes to transactions/licences |

Note: "Software Owner" and "Head Authority" are the only roles with account-provisioning rights over Authorised Personnel; Head Authority additionally has the read-only oversight access described below. Buyers, sellers and Authorised Personnel never provision their own or each other's accounts.

Rules:
1. Buyer and seller do not see each other's personal details until a transaction is approved, and then only the minimum needed (never full profiles).
2. Records are never edited or deleted. Corrections are new entries, chained to the original.
3. A seller can never see another seller's inventory or transactions; a buyer can never see another buyer's.
4. All access to another party's sensitive data (licence number, ID, address) is itself logged, including by officials.
5. An Authorised Personnel account can only be created or have its password reset by Software Owner or Head Authority — never by self-enrolment.

## Architecture
Single backend service with modules: `identity`, `licensing`, `positions` (org/authority hierarchy), `inventory` (per-seller items + severity), `transactions`, `approvals`, `transport`, `audit`, `compliance`. One Postgres database. Access is enforced twice: application-layer role checks, and Postgres row-level security as a backstop (every table scoped by owning user/position, verified independently of app logic).

Key components:
- **Auth (licensees):** Licensing Authority pre-loads licence + GSTIN + registered contact records; user self-enrols with licence number + GSTIN, verified by OTP to the pre-registered phone/email; system-generated user ID, user-chosen password; forgot-password re-runs the same OTP verification; ongoing sign-in uses password + OTP as a second factor; short-lived sessions, device/session listing, lockout and rate limiting on both enrolment and login attempts (to stop licence/GSTIN enumeration).
- **Auth (Authorised Personnel):** no self-enrolment. Only Software Owner or Head Authority can create an Authorised Personnel account (assigned id + initial password, forced change on first login) or reset one. Sign-in uses password + OTP like other roles.
- **Positions & jurisdiction:** a hierarchy table (`position`: level [area/district/state], jurisdiction/area code, parent position) separate from `personnel_assignment` (who currently holds a position, with start/end dates). Approval routing always resolves to a `position_id`; the active assignment resolves that to a person at decision time.
- **Approval policy engine:** table `approval_policy(item_severity_class, area_level, quantity_band) -> ordered list of required position levels`. A transaction resolves the transaction's area + the item's severity/complexity + quantity to a concrete ordered chain of `position_id`s at request time, and that resolved chain is stored immutably with the transaction (so a later re-org or personnel transfer never changes an in-flight or historical chain's meaning).
- **Transaction authorisation step:** both the buyer's confirmation and each Authorised Personnel's decision are OTP-gated (password login is not sufficient by itself to accept/reject — a fresh OTP is required at the moment of decision, binding the decision to the person). Each decision is accept or reject. A comment is optional on accept, but **mandatory on reject**: a dropdown of common structured reasons (e.g. "material weight mismatch", "quantity mismatch: expected X kg, found Y kg", "transporter details invalid", "licence expired") with a free-text option when nothing in the dropdown fits. The dropdown's option list is a configurable reference table, not hardcoded, so new reasons can be added without a code change.
- **Transport record:** mandatory sub-record on every transaction: transporter identity, licence/registration number, vehicle details, route/area. Validated (format/licence checks) before the transaction can be submitted for approval.
- **Audit log:** append-only table, each row includes the hash of the previous row (hash chain), periodic anchoring of the latest hash to a separate store, and a verification job. Every read of sensitive data is logged (subject, reader, reason, timestamp).
- **Compliance module:** consent/purpose records for DPDP, configurable retention periods per data category, data-principal request handling (access/correction/erasure within legal limits — erasure never applies to the audit trail itself, only to no-longer-needed personal data per policy), and mapping of which fields are restricted under Gujarat Prohibition Act / other applicable acts.
- **Data protection:** encryption in transit and at rest, field-level encryption for identifiers (licence numbers, ID), secrets in a managed vault, backups encrypted and within India, regular access reviews.

## Core data model (sketch)
`users`, `roles`, `licences` (type, number, validity, status, area, gstin, registered_contact), `item_categories` (severity_class), `inventory_items` (owned by seller), `positions`, `personnel_assignments`, `transactions` (state machine: initiated, buyer_confirmed, in_approval, approved, rejected, cancelled), `transport_details`, `approval_policy`, `approval_steps` (resolved position chain + decisions, each decision: actor, OTP-verified timestamp, accept/reject, reason_code [required on reject, optional on accept], free_text_comment), `decision_reason_codes` (configurable dropdown values), `audit_log`, `consent_records`, `data_retention_policy`.

## Phases
1. **Foundation:** repo scaffold, CI, Postgres schema, identity + MFA, role model, audit log with hash chain, RLS baseline.
2. **Licensing & positions:** Licensing Authority pre-loads licence/GSTIN/contact records and manages suspend/revoke; licence-gated self-enrolment flow (licence + GSTIN + OTP) and forgot-password flow; position hierarchy + personnel assignment/transfer.
3. **Inventory:** per-seller item inventory with severity/complexity classification, strictly scoped visibility.
4. **Transactions, transport & approvals:** seller-initiates-by-lookup flow, mandatory transporter details, policy engine resolving area+severity+quantity to a position chain, OTP-gated accept/reject decisions with structured+free-text comments; Software Owner/Head Authority admin flow for creating and resetting Authorised Personnel accounts.
5. **Oversight & compliance:** Head Authority read-only dashboards, audit verification/export, DPDP consent & retention tooling, data-principal request handling.
6. **Hardening:** threat model review, penetration test, load test, backup/restore drill, deployment to India region, legal sign-off on compliance mapping.

## Open items to confirm before implementation
- Tech stack: **Django (Python) backend + React frontend, Postgres database.**
- Licence/GSTIN/contact records enter the system via **both** manual entry (Licensing Authority admin UI) and bulk CSV upload, from day one.
- Whether OTP goes to phone, email, or user's choice of either at enrolment/reset time; and the OTP/SMS provider to use (must keep data in India).
- Exact severity/complexity classes for liquor/prohibited items, and the area levels (taluka/area, district, state) mapped to Gujarat's actual administrative and police/excise structure.
- Whether a buyer must pre-exist in the system (licensed) before a seller can look them up (assumed yes — no lookup of unlicensed parties).
- Named legal reviewer/counsel to validate the DPDP and Gujarat Prohibition Act compliance mapping before go-live.

## Verification (once built)
- Unit tests for the policy engine across severity x area x quantity combinations, including a position-transfer scenario mid-chain.
- Row-level-security tests proving each role cannot read other roles'/sellers'/buyers' data, including direct SQL as a role's DB user.
- Audit chain test: tamper with a row, confirm the verifier flags it.
- End-to-end flow test: onboard users, seller looks up buyer, initiates transaction with transporter details, OTP-gated buyer confirmation, OTP-gated multi-position approval with dropdown+free-text comments, Head Authority audit view.
- Admin-provisioning test: confirm only Software Owner/Head Authority can create or reset an Authorised Personnel account, and every other role is refused.
- Security testing: auth abuse, IDOR checks (especially inventory/transaction scoping), MFA bypass attempts, dependency scan.
- Enrolment abuse tests: licence/GSTIN enumeration attempts, OTP redirection/interception attempts, rate limiting on enrolment and forgot-password.
- Compliance test: verify consent/retention rules and that a data-principal erasure request cannot remove audit-trail integrity.