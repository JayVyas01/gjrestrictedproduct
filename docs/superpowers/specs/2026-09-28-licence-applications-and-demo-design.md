# Licence Types, Applications & Renewals, and the Demo Milestone — Design

**Status:** Approved in brainstorming on 2026-09-28. The authorities' demo review may change it.
**Extends:** [`highlevel_plan.md`](../../../highlevel_plan.md) · **Roadmap:** [`2026-09-26-roadmap.md`](../plans/2026-09-26-roadmap.md)

## 1. Summary

Four additions to the platform:

1. **Licence types as a first-class, configurable catalogue.** A licence type has permissions (may buy, sell or transport, stock limits, per-transaction limits) that differ by substance and by substance class.
2. **Licence applications.** Any business can apply for a licence of a given type for a specific substance or substance class, against a checklist of requirements published in advance. The application is verified in the applicant's area and approved and issued by the Licensing Authority.
3. **Licence renewal**, through the same workflow.
4. **A Demo milestone**: a polished, production-quality slice of the licence application and transaction approval journeys, running on synthetic data, to present to the authorities before the full build.

**Top-level product priorities** (in addition to security and compliance): the product must be **very user friendly**, and the demo must be **strong and compelling**.

## 2. Decisions

| # | Decision | Choice |
|---|---|---|
| D1 | How a business without a licence gets access | A limited **Applicant** account (GSTIN, business name, contact, confirmed by OTP to that contact). It can never trade. |
| D2 | Who reviews | Two fixed steps: a **verifier** (the area-level position for the premises), then the **Licensing Authority**, which approves and issues. |
| D3 | Requirements | A **configurable checklist** for each licence type rule. Item kinds: `DOCUMENT`, `NUMBER`, `TEXT`, `DATE`, `DECLARATION`. |
| D4 | Renewal | A renewal application with a **grace period set to 0 days for now**. The setting stays, pending legal confirmation. |
| D5 | Defects | **Approve**, **reject** (final) or **return for correction**. Resubmissions are limited (default 3). |
| D6 | Code structure | A new `applications` module that reuses shared building blocks and calls `licensing` to issue licences (approach A). |
| D7 | Licence types | Catalogue of licence types plus **licence type rules** per (type × substance or class). The specific substance overrides its class. Anything without a rule is not permitted. |
| D8 | Rule changes | Rules are **versioned**. Permissions are **frozen on the licence at issue and at renewal**. |
| D9 | Roles | `BUYER` and `SELLER` are replaced by **`LICENSEE`** (what they may do comes from their licences). **`APPLICANT`** is added. |
| D10 | Review mode | Set per rule: **`SEPARATE`** (default; verifier and approver must be different user IDs) or **`COMBINED`** (one Licensing Authority reviewer, one OTP, still two decision records). |
| D11 | Demo scope | **Licence application journey** plus **transaction approval journey**. |
| D12 | Language | **English only for the demo**. All text goes through i18n files so Gujarati can be added without code changes. |
| D13 | Demo data | Licence types, permissions and the storage provider are **demo placeholders** that the admin will update later. |

**Deferred:** Head Authority edit permissions (to be defined after the demo), the oversight dashboard, on-screen admin configuration, CSV licence import, session listing, and notifications (the demo shows status on screen instead).

## 3. Roles and access

| Role | Can see | Can do |
|---|---|---|
| **Applicant** (new) | Their own applications; published licence types and requirements | Register; draft, submit (signed with an OTP), correct and resubmit, withdraw |
| **Licensee** (replaces Buyer/Seller) | The above, plus their own licences with permissions; their own inventory and transactions | Renew; apply for other licence types or substances; buy and sell only as their licences allow |
| **Authorised Personnel** (as verifier) | Applications sent to a position they currently hold; transactions sent to their position | Check each requirement; forward, return or reject (signed with an OTP); decide on transactions |
| **Licensing Authority** | Applications at the issuing step; all licences; the catalogue | Maintain the catalogue and rules (new versions); approve and issue, return, or reject (signed with an OTP) |
| **Head Authority** | Everything, read-only (edit rights deferred) | Audit |
| **Software Owner** | Everything, plus system configuration | Provision personnel accounts |

**Applicant to licensee.** An approved application creates the licence record with the verified GSTIN and contact. The business then uses the existing **licence-gated enrolment** (licence number, GSTIN, OTP to the contact on file) to get a `LICENSEE` account. An Applicant account never gains trading rights.

**What reviewers' comments applicants see.** Applicants see outcomes and reason codes, never reviewers' internal comments.

## 4. Catalogue and licence types

- `substance_class`, for example *Spirits*, and `substance`, for example *Whisky*, which belongs to one class.
- `licence_type`, for example Manufacturer, Wholesale, Retail, Transport or Permit holder.
- `licence_type_rule`: the scope is exactly one of a substance or a substance class. Each rule is stored as a series of **`licence_type_rule_version`** rows, and a version is never edited. Each version holds:
  - `may_buy`, `may_sell`, `may_transport`
  - `max_stock_qty`, `max_per_transaction_qty`, `unit` (for example L or kg)
  - `validity_months`, `renewal_window_days` (default 60), `grace_days` (**0**)
  - `review_mode` (`SEPARATE` | `COMBINED`)
  - its requirement definitions
- **Finding the rule:** a rule for the specific substance wins over a rule for its class. If there is no rule, the licence type is **not available** for that substance.

**Licence changes (Phase 2 model):**
- A licence records the holder's GSTIN, its `licence_type`, its scope (a substance or a class), and its status (active, suspended or revoked).
- `licence_validity_period` rows are append-only.
- `licence_permissions_snapshot` is copied from the rule version at issue and at each renewal.
- **`trading_permitted(licence, at) -> bool`** is the only function that decides whether a licence allows trading. It returns true when the licence is not suspended or revoked, and either:
  - a validity period covers `at`, or
  - a renewal was submitted before expiry, is still pending, and `at < expiry + grace_days`.
- With `grace_days = 0`, the second case never applies.

## 5. Application data model

All tables are append-only unless noted.

- **`requirement_definition`** (belongs to a rule version): `code`, `label`, `help_text`, `example`, `kind`, `mandatory`, `unit`, `min`/`max` (for `NUMBER`), allowed file types (for `DOCUMENT`), `order`.
- **`licence_application`**:
  - public reference `APP-YYYY-NNNNNN`
  - `applicant`, `kind` (`NEW` | `RENEWAL`), `licence_type`, scope, `rule_version`
  - `renews_licence` (for renewals only)
  - `premises_area`, which decides the verifier
  - `status`, `resubmission_count`: the only fields that change, and every change writes an audit event
- **`application_revision`**: numbered 1, 2, 3 and so on. A draft can be edited; a submitted revision is frozen. It stores `verifier_position` (resolved at submission) and `submitted_at` with the OTP timestamp.
- **`requirement_answer`**: one per requirement per revision. It holds an encrypted value or a link to a `document`.
- **`document`**: owner, SHA-256 hash, content type, size, `scan_status` (`PENDING` | `CLEAN` | `INFECTED`), storage key, encrypted original filename.
- **`requirement_check`**: per answer, `MET` | `NOT_MET`, reason code, optional internal comment, reviewer.
- **`application_decision`**:
  - `step` (`VERIFICATION` | `ISSUANCE`), `outcome` (`FORWARD` | `APPROVE` | `RETURN` | `REJECT`)
  - user ID, position (if any), `otp_verified_at`
  - `reason_code`, required for `RETURN` and `REJECT`
  - comment

**Checks at submission:**
- every mandatory requirement is answered
- numbers are within `min`/`max` and use the right unit
- documents are `CLEAN` and of an allowed type
- every declaration is ticked
- no other open application exists for the same GSTIN, licence type and scope
- no active licence exists for that combination (the business must renew it instead)

Any failure is reported against the specific requirement, in plain language.

**Renewals** are pre-filled from the licence's last approved revision. Each answer must be confirmed or replaced. A `DATE` requirement that has expired, such as a NOC expiry date, must be replaced.

## 6. Workflow

```
DRAFT ──submit──▶ IN_VERIFICATION ──forward──▶ WITH_AUTHORITY ──approve──▶ APPROVED (licence issued)
                    │    ▲                       │
                    │    └──────resubmit─────┐   │
                    ├──return──▶ RETURNED ◀──┴───┤ return
                    └──reject──▶ REJECTED ◀──────┘ reject
Any state except APPROVED / REJECTED ──withdraw──▶ WITHDRAWN
RETURNED left untouched for 30 days (setting) ──▶ LAPSED
```

**Who can do what:**
- The applicant signs **submit** with an OTP.
- In `SEPARATE` mode:
  - The **verifier** must record a check against every requirement before forwarding. `RETURN` needs at least one `NOT_MET` with a reason; `REJECT` needs a reason code.
  - The **Licensing Authority** sees the verifier's checks and may add its own. It can `APPROVE`, `RETURN` or `REJECT`.
  - The verifier's and approver's user IDs must differ. This is enforced in the app and by a database constraint.
- In `COMBINED` mode:
  - The application goes straight to the Licensing Authority queue. One reviewer checks all the requirements and decides, signed with **one OTP**.
  - Two decision rows are written (`VERIFICATION` and `ISSUANCE`) with the same user ID and OTP timestamp. The state skips `WITH_AUTHORITY`.

**Rules that apply in both modes:**
- **`APPROVE` issues the licence in the same database transaction.** Neither can exist without the other.
- **A resubmission always goes back to verification.**
- **Return limit:** once `resubmission_count` reaches the limit (default 3), `RETURN` is no longer offered.
- **Routing:** the verifier is the area-level position covering `premises_area`. It is resolved at submission and stored on the revision, so a personnel transfer doesn't move the application. A vacant position leaves the application queued. The Licensing Authority step is a shared queue for the role.

**Renewal:**
- The window opens `renewal_window_days` before expiry and closes at expiry. After expiry, a `NEW` application is needed.
- On approval, a new validity period starts the day after the old one ends, and the permissions are frozen again from the current rule version.

**Changing the review mode** is only possible through a new rule version created by the Licensing Authority, and it writes an audit event.

## 7. Documents and security

**Document store**
- **Interface:** `DocumentStore` with `put`, `get` and `lock`. Dev, test and demo use a local-disk implementation. Production uses private S3-compatible storage in an **India region**; the provider is a demo placeholder until it's chosen.
- **Encryption:** the application encrypts every file with `DOCUMENT_ENCRYPTION_KEY` before storing it; production also uses the bucket's own encryption.
- **Uploads** go only through the API. The API:
  - enforces a 10 MB limit (setting)
  - accepts PDF, PNG and JPEG only, **detected from the file's contents**
  - rejects PDFs containing JavaScript or embedded files
  - scans every file with **self-hosted ClamAV**
  - stores files under a random key, keeping the original filename cleaned and encrypted
- **Downloads** go through the API after an access check. They are served with `Content-Disposition: attachment`, `nosniff` and a sandbox CSP, and **every download writes an audit event** (reader, document, application, reason).
- **Locking:** documents of a submitted revision are locked. Uploads never attached to a submission are deleted after 7 days, because they were never an official record.

**Access** (checked in the app and backed by row-level security):
- The applicant sees only their own applications.
- A verifier sees only applications sent to a position they currently hold, and loses access after a transfer.
- The Licensing Authority sees applications at the issuing step, or all applications in `COMBINED` mode.
- The Head Authority has read-only access.
- The catalogue is readable by everyone logged in; only the Licensing Authority can create new versions.

**Abuse controls:**
- Registration is rate-limited.
- GSTIN format and checksum are validated.
- Each GSTIN can have only one active Applicant account.
- There are quotas on open drafts and on upload volume.
- Submitting and every decision require a fresh OTP.

**DPDP:**
- At registration the applicant accepts a consent notice limited to one purpose (licence processing), stored as a consent record.
- Only the listed requirements are collected.
- Retention periods are set by the compliance module in the Oversight phase.

## 8. The Demo milestone

**Scope.** Everything here is production quality: tested and secure, not throwaway.
- **Licence application journey:**
  1. The applicant registers and chooses a licence type and substance.
  2. A guided checklist wizard with sample PDFs.
  3. The applicant submits with an OTP.
  4. The verifier returns it for a missing fire NOC.
  5. The applicant corrects and resubmits.
  6. The verifier forwards it.
  7. The Licensing Authority approves.
  8. The licence is issued with a **permissions card** (what it allows, the stock limit, the per-transaction limit and validity).
- **Transaction journey:**
  1. The seller looks up the buyer by exact licence number and enters the item, quantity and mandatory transporter details.
  2. The system **checks licence permissions and blocks a quantity above the per-transaction or stock limit, with a plain explanation**.
  3. The buyer confirms with an OTP.
  4. The Area Officer approves, then the District Officer approves with reason codes.
  5. The status timeline updates at each step.
- **Review mode in the demo:** all demo rules use `SEPARATE`. `COMBINED` is built in Phase 3.
- **What they need underneath:** areas, positions and assignments; licence records and licence-gated enrolment; a small per-seller stock list seeded read-only; a demo approval policy matrix; configurable reason codes.

**Demo tooling**
- **`make demo`:** starts Postgres, the backend, the web app and ClamAV with Docker Compose on a laptop, **fully offline**.
- **`DEMO_MODE=1`** switches on the demo features. The app **refuses to start** if `DEMO_MODE` is combined with production settings (DEBUG off plus a production host list).
- **`seed_demo` and `reset_demo`** build and rebuild the synthetic data:
  - fictional businesses in real Gujarat district names
  - GSTINs with state code **99** (it doesn't exist, so it can't match a real business)
  - phone numbers in a reserved dummy range
  - sample PDFs watermarked **"SYNTHETIC — DEMO"**
  - demo licence types, rules and permissions
  - several dozen applications and transactions in mixed states
- **Persona picker** (demo mode only) on the login screen: one click fills in the credentials for Applicant, Verifier (Area Officer), District Officer, Licensing Authority, Seller or Buyer. The **real password and OTP login still runs**.
- **Demo SMS inbox:** a drawer showing OTPs sent to synthetic contacts. It exists only in demo mode and is backed by a `DemoInboxOtpSender`, which refuses to run outside demo mode.
- **`docs/demo/script.md`:** a 12–15 minute storyline covering the order of personas, clicks and talking points, plus a rehearsal and reset checklist.

## 9. User experience principles (every screen)

- **A "What's next" card** on every role's home screen stating the next action, for example "2 applications waiting for your verification".
- **Step-by-step wizards** with a progress bar and automatic draft saving. Every requirement has a plain-language explanation and an example.
- **A status timeline** on every application and transaction, like a parcel tracker, including return and reject reasons.
- **Error messages that say how to fix the problem**, for example "Quantity 600 L exceeds this licence's per-transaction limit of 500 L". Never raw codes.
- **WCAG 2.1 AA**, responsive down to phone width, and a calm, official visual style.
- **Frontend:** React, TypeScript and Vite with an accessible component library. All text goes through i18n files (English now, Gujarati later). The visual direction is settled in the Demo milestone plan.

## 10. Roadmap impact

**Order:** Phase 1, then the Demo milestone, then the authorities' review, then Phases 2–7 (adjusted by the feedback, and absorbing whatever the demo already built).

| # | Phase | Change |
|---|---|---|
| 1 | Foundation | `Role`: replace `BUYER`/`SELLER` with `LICENSEE`; add `APPLICANT` |
| D | **Demo milestone (new)** | Section 8 |
| 2 | Licensing & positions | Licence type, scope, permissions snapshot, validity periods, `trading_permitted()` |
| 3 | **Applications & renewals (new)** | Catalogue, versioned rules and requirements, document store, workflow, review modes, renewals |
| 4 | Inventory | Stock capped by the licence's `max_stock_qty` |
| 5 | Transactions & approvals | Needs `trading_permitted`, a licence covering the substance with the right permission, and per-transaction limits; transporters need a Transport licence |
| 6 | Oversight & compliance | Application and document retention; list of `COMBINED` rules; vacancy list; Head Authority edit rights (to be defined) |
| 7 | Hardening | ClamAV in production, bucket object lock, document restore drill |

## 11. Testing

- **Rules:** a specific substance overrides its class; anything without a rule is not permitted; a new version doesn't affect existing applications or licences; permissions are frozen at issue and at renewal.
- **State machine:** a table-driven test over state × action × role, allowing only the permitted transitions. Also: submission checks for each requirement kind, the return limit, lapsing, and withdrawal.
- **Review modes:** in `SEPARATE`, one user ID can't do both steps (tested in the app and against the database constraint); in `COMBINED`, one OTP writes two decisions; changing the mode affects only new applications.
- **Issuing:** approval and licence creation are atomic (a failure injected mid-way leaves neither); a renewal's validity period starts the day after the old one ends.
- **`trading_permitted`:** before, at and after expiry; pending renewal with `grace_days` 0 and above 0; suspended or revoked licences.
- **Access:** RLS and IDOR tests for applicants, verifiers (including after a transfer), the Licensing Authority and the Head Authority (read-only); the applicant never sees internal comments.
- **Documents:** wrong type, too large, disguised extension, PDF with JavaScript, and EICAR are all rejected; files are stored encrypted; downloads are audited; documents of a submitted revision can't be changed.
- **Demo:** `seed_demo` then `reset_demo` gives the same state every time; demo features and the app itself refuse to start without `DEMO_MODE` or when combined with production settings; the synthetic GSTINs all use state code 99.
- **End to end** (browser, Playwright): both demo journeys, following the demo script, finishing with `verify_audit_chain` passing.

## 12. Open items

- The legal position on grace periods under the Gujarat Prohibition Act (currently 0).
- The real licence types, permissions, stock limits and requirement lists (demo placeholders until then; the admin will update them).
- Object-storage provider and India region (demo placeholder).
- Head Authority edit permissions (deferred).
- Whether a Licensing Authority user could also act as an area verifier (currently prevented in `SEPARATE` mode by the user-ID check).
- Authorities' demo feedback, which may change any part of this design.
