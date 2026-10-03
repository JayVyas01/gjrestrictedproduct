# Code Map

**What this is:** the one place that says which code is responsible for what, which user roles it serves, and which tests prove it. Use it to review, debug or change the system.

**Keep it current:** every pull request that adds, removes or changes code or tests updates this file in the same pull request. A reviewer should reject a code PR that leaves this map stale.

**Last updated:** 2026-10-03, D2b Task 3: superintendent review periods and batch creation (286 tests).

---

## 1. User roles and where their rules live

| Role | What they can do today | Where it is enforced | Proving tests |
|---|---|---|---|
| **Licensee** (buyer and seller combined; what they may do comes from their licences) | Created only by licence-gated enrolment (a business with an active licence on record proves control with a code sent to the contact on file). Logs in with password and a one-time code. Sees only licences whose GSTIN matches their account (`licensee_gstin_index`, enforced by row-level security). Can view the permissions card of each of their own licences (`GET /api/licences/mine`). Sees own stock (`GET /api/stock/mine`). Sees transactions where their business is seller or buyer, matched by GSTIN. Sees their own view of each transaction (seller, buyer) with the other party's registered name only, never licence numbers or the buyer's free-text comment. May look up a buyer by GSTIN (sees only the registered name), start a transaction and cancel it while it waits for the buyer. As buyer, confirms or rejects (with a buyer reason) with a one-time code while the transaction waits for them. | `identity/roles.py` (`Role.LICENSEE`), `identity/login.py`, `identity/views.py`, `licensing/enrolment.py`, `licensing/views.py` (`MyLicencesView`); `stock/views.py` (`MyStockView`); `licensing/migrations/0002_rls_and_append_only.py` (licence read policy); `stock/migrations/0002_rls_and_append_only.py` (own-stock read policy); `transactions/service.py` (`find_buyer`, `start_transaction`, `cancel_transaction`, `decide`); `transactions/migrations/0002_rls_and_append_only.py` (party read policy) | `test_transaction_service.py`, `test_transaction_decisions.py`, `test_transaction_api.py`, `test_login_api.py`, `test_users.py::test_has_role`, `test_enrolment.py`, `test_licence_api.py`, `test_licensing.py::test_holder_sees_only_their_own_licences`, `test_stock.py::test_holder_sees_only_own_stock`, `test_stock.py::test_my_stock_api`, `test_transaction_rules.py::test_transaction_visibility` |
| **Authorised Personnel** | Log in. They hold positions (e.g. Area Officer for a taluka); authority is positional, so a transfer moves the position to the new person immediately. As the designated officer (the current holder of the seller area's Area Officer position) approves or rejects with a one-time code; on approval stock moves from seller to buyer. Reads transactions where they currently hold the designated or superintendent position (officer view includes comments and who held the officer position at each decision). The superintendent reads transactions whose stored superintendent position they currently hold (every transaction has one); reads the oversight batches of the district position they currently hold (flagging and sign-off arrive in D2b). Sees and acknowledges alerts addressed to the positions they currently hold (buyer rejections on their transactions); after a transfer the alerts follow the position. | `identity/roles.py` (`Role.PERSONNEL`); `positions/` (only Personnel can be assigned); `transactions/service.py` (`decision_role`, `decide`); `transactions/migrations/0002_rls_and_append_only.py` (position-holder read policy); `alerts/service.py` (`acknowledge`); `alerts/migrations/0002_rls_and_append_only.py` (position-holder read policy); `oversight/migrations/0002_rls_and_append_only.py` (batch read policy) | `test_oversight_batches.py::test_only_the_superintendent_and_authorities_see_batches`, `test_permissions.py`, `test_positions.py`, `test_transaction_decisions.py`, `test_transaction_api.py`, `test_transaction_rules.py::test_transaction_visibility`, `test_alerts.py` |
| **Licensing Authority** | Log in. Maintains the catalogue (substances, licence types, versioned rules; screens arrive in D3). Records licences issued by the existing process, records renewals, suspends or revokes (row-level security lets only this role and SYSTEM write licences). Sets superintendent review periods (15, 30 or 60 days) through `oversight.service.set_review_period`; the screen comes in D3. Does not read stock (DPDP data minimisation). | `identity/roles.py` (`Role.LICENSING_AUTHORITY`); `catalogue/`; `licensing/service.py`, `licensing/migrations/0002_rls_and_append_only.py`; `stock/migrations/0003_stock_readers_without_la.py` (no stock read) | `test_permissions.py`, `test_catalogue.py`, `test_licensing.py`, `test_stock.py::test_licensing_authority_cannot_read_stock` |
| **Software Owner** | Log in; read the whole audit log; read all licences with their periods and snapshots; read all stock; create or reset personnel accounts (the API comes in Phase 4); reads all transactions, all alerts and all oversight batches. | `identity/roles.py` (`AUDIT_READERS`, `PERSONNEL_PROVISIONERS`); `audit/migrations/0002_protect_and_rls.py` (read policy); `licensing/migrations/0002_rls_and_append_only.py` (licence read policy); `create_software_owner` command (first account only); `transactions/migrations/0002_rls_and_append_only.py` (authority read policy) | `test_audit.py::test_only_audit_readers_can_read_events`, `test_create_software_owner.py`, `test_transaction_rules.py::test_transaction_visibility`, `test_alerts.py::test_only_position_holders_and_authorities_see_alerts` |
| **Head Authority** | Log in; read the whole audit log (oversight); read all licences with their periods and snapshots; read all stock; create or reset personnel accounts (Phase 4); reads all transactions, all alerts and all oversight batches. | Same as Software Owner, plus `licensing/migrations/0002_rls_and_append_only.py`; `transactions/migrations/0002_rls_and_append_only.py` (authority read policy) | `test_audit.py::test_only_audit_readers_can_read_events`, `test_transaction_rules.py::test_transaction_visibility`, `test_alerts.py::test_only_position_holders_and_authorities_see_alerts` |
| **SYSTEM** (background jobs, never a person) | Read the audit log to verify the chain; read and record licences (enrolment matching, seeding); the only writer of stock balances and movements; the only writer of transactions, decisions, alerts, acknowledgements, oversight batches and batch items. | `core/db_context.py` (`SYSTEM_ROLE`, `acting_as_system`), `verify_audit_chain` command, `licensing/migrations/0002_rls_and_append_only.py`, `stock/migrations/0002_rls_and_append_only.py`; `transactions/migrations/0002_rls_and_append_only.py` (SYSTEM-only write policies) | `test_audit.py::test_verify_command_*`, `test_stock.py::test_only_system_can_write_stock`, `test_transaction_rules.py::test_only_system_writes_and_only_status_changes` |
| **Any logged-in user** (all roles) | Read the substance list (`GET /api/catalogue/substances`); list reason codes (`GET /api/reason-codes?kind=`) | `licensing/views.py` (`SubstanceListView`); `reasons/views.py` (`ReasonCodeListView`) | `test_licence_api.py::test_substance_list_for_logged_in_users`, `test_reasons.py::test_reason_code_api_lists_active_codes` |
| **Anonymous** (not logged in) | Only the health check, the CSRF cookie, the two login steps and the two enrolment steps (start, complete) | `settings.REST_FRAMEWORK` (deny by default), `AllowAny` on those views only; `licensing/views.py` | `test_login_api.py`, `test_enrolment.py`, `test_permissions.py::test_anonymous_is_refused`, `test_audit.py::test_anonymous_context_cannot_read_events` |

To restrict a new API endpoint to certain roles, use `permission_classes = [role_required(Role.X, ...)]` from `identity/permissions.py`.

---

## 2. Code responsibility map

Paths are relative to `backend/`.

### config: settings and startup

| File | Responsible for | Key names | Tests |
|---|---|---|---|
| `config/env.py` | Reading environment variables; stops at startup if a required one is missing | `required`, `optional`, `flag`, `listed`, `MissingSetting` | `test_env.py` |
| `config/settings.py` | All settings: database, security headers, sessions (15-minute idle timeout), rate limits (`login`, `otp`, `enrolment` 10/min, `lookup` 30/min, `NUM_PROXIES: 0`), encryption keys, OTP sender, exception handler | `REST_FRAMEWORK`, `CACHES`, `MIDDLEWARE` | Covered indirectly by all API tests; `check --deploy` in CI |
| `config/urls.py` | URL routing: `/api/health`, `/api/auth/*`, and the licensing routes under `/api/` (`enrolment/start`, `enrolment/complete`, `licences/mine`, `catalogue/substances`), the stock route, the transaction routes (`transactions`, `transactions/buyer-lookup`, `transactions/<ref>`, `.../decision-code`, `.../decide`, `.../cancel`), and the alert routes (`alerts`, `alerts/<id>/acknowledge`) | — | `test_health.py`, `test_login_api.py`, `test_enrolment.py`, `test_licence_api.py`, `test_stock.py::test_my_stock_api`, `test_transaction_api.py`, `test_alerts_api.py` |
| `.env.test` | Test-only settings (never real secrets) | — | — |

### core: shared building blocks

| File | Responsible for | Key names | Tests |
|---|---|---|---|
| `core/views.py` | Health check; also confirms the database is reachable | `health` | `test_health.py` |
| `core/crypto.py` | Encrypting sensitive fields; one-way lookup keys (blind indexes) for exact-match lookup only | `encrypt`, `decrypt`, `blind_index(context, value)`, `DecryptionError` | `test_crypto.py` |
| `core/db_context.py` | Telling Postgres who is acting, so row-level security can check it; the setting lasts only for the current transaction | `set_actor`, `current_actor`, `SYSTEM_ROLE`, `acting_as_system(job)` (brief SYSTEM block in its own savepoint: restores the previous actor on normal exit, and any error rolls back to the savepoint so the actor reverts too; writes inside are all-or-nothing; writes no audit event itself, so every caller audits its cross-owner action; outside a transaction it opens its own short one) | `test_db_context.py`, `test_licensing.py::test_acting_as_system_restores_previous_actor`, `test_licensing.py::test_acting_as_system_does_not_mask_database_errors`, `test_licensing.py::test_acting_as_system_restores_actor_after_caught_nested_error` |
| `core/middleware.py` | One database transaction per request, tagged with the user; a 5xx response rolls back | `DbContextMiddleware` | `test_db_context.py` |
| `core/exceptions.py` | A raised API error undoes the request's writes (**raise to roll back, return to commit**) | `rollback_on_exception` | `test_rollback_on_exception.py` |
| `core/migrations/0002_append_only_guard.py` | Shared trigger function `reject_append_only_change()`; append-only tables attach it (row trigger for update/delete, statement trigger for truncate); used by rule versions, licence validity periods and permission snapshots | `reject_append_only_change` | `test_catalogue.py::test_rule_versions_blocked_even_for_table_owner`, `test_licensing.py::test_periods_and_snapshots_blocked_even_for_table_owner` |
| `core/migrations/0001_app_role_privileges.py` | The app role `gj_app` gets data access only: no schema changes, no ownership | — | `test_db_privileges.py` |

### identity: accounts, roles, one-time codes, login

| File | Responsible for | Key names | Tests |
|---|---|---|---|
| `identity/roles.py` | The six fixed roles and role groups | `Role`, `AUDIT_READERS`, `PERSONNEL_PROVISIONERS` | `test_users.py`, `test_permissions.py`, `test_audit.py` |
| `identity/models.py` | User accounts (system-generated ID, `licensee_gstin_index` linking a licensee to their licences, Argon2 password, encrypted contact, lockout fields; at most one account per non-empty `licensee_gstin_index`) and one-time-code records (for a user or, before an account exists, a subject such as `"licence:<id>"`; at most one open code per user, or per subject, and purpose) | `User`, `UserManager.create_user`, `generate_user_id`, `OtpChallenge`, `OtpPurpose` (`LOGIN`, `ENROL`, `DECISION` for signing a transaction decision) | `test_users.py`, `test_otp.py`, `test_otp_subject.py` |
| `identity/migrations/0008_one_account_per_licensee_gstin.py` | Partial unique constraint: one account per non-empty licensee GSTIN | — | `test_enrolment.py::test_database_allows_one_account_per_gstin` |
| `identity/migrations/0007_user_licensee_gstin_index.py` | Adds the indexed `licensee_gstin_index` column | — | `test_licensing.py::test_holder_sees_only_their_own_licences` |
| `identity/migrations/0002_protect_users.py` | Accounts can't be deleted, only deactivated | — | `test_users.py::test_app_role_cannot_delete_users` |
| `identity/otp.py` | Issuing and checking 6-digit codes: stored as HMAC, 5-minute expiry, 5 attempts, single use, a new code cancels the old one, issuing locks the user row (subjects: a per-subject advisory lock); checking locks the user row first, then the challenge (same order as login, so no deadlock); also codes for subjects with no account yet (enrolment) | `issue`, `verify`, `issue_for_subject`, `verify_subject`, `OTP_TTL`, `OTP_MAX_ATTEMPTS` | `test_otp.py`, `test_otp_subject.py` |
| `identity/otp_delivery.py` | How codes are sent: console in development (refuses unless DEBUG), in-memory outbox in tests, real provider later | `get_sender`, `ConsoleOtpSender`, `OutboxOtpSender` | `test_otp.py` |
| `identity/login.py` | Login step 1: password check on every path (timing is the same whether or not the account exists), lockout after 5 wrong passwords or 5 code requests in 15 minutes, locking cancels open codes | `start_login`, `LOCKOUT_THRESHOLD`, `LOCKOUT_DURATION` | `test_login_api.py` |
| `identity/serializers.py` | Validating login input | `LoginSerializer`, `OtpVerifySerializer` | `test_login_api.py` |
| `identity/views.py`, `identity/urls.py` | Login API: csrf, login, login/verify, logout, me | `CsrfView`, `LoginStartView`, `LoginVerifyView`, `LogoutView`, `MeView` | `test_login_api.py` |
| `identity/permissions.py` | Restricting an endpoint to certain roles | `role_required` | `test_permissions.py` |
| `identity/management/commands/create_software_owner.py` | Creating the very first Software Owner (run once, interactive) | — | `test_create_software_owner.py` |

### catalogue: substances, licence types, versioned rules

| File | Responsible for | Key names | Tests |
|---|---|---|---|
| `catalogue/models.py` | What can be traded and what each licence type may do with it: substance classes, substances (each with a unit), licence types, rules (scoped to exactly one substance or one class) and rule versions (buy/sell/transport, stock and per-transaction limits, validity) | `Unit`, `SubstanceClass`, `Substance`, `LicenceType`, `LicenceTypeRule`, `LicenceTypeRuleVersion` | `test_catalogue.py` |
| `catalogue/service.py` | Finding the governing rule (substance rule beats class rule; none means not permitted), listing a licence type's substance-specific overrides within a class (latest versions), and adding a new rule version | `resolve_rule`, `substance_overrides`, `add_rule_version` | `test_catalogue.py` |
| `catalogue/migrations/0003_rule_version_trigger.py` | Rule versions also blocked by trigger for the table owner | — | `test_catalogue.py::test_rule_versions_blocked_even_for_table_owner` |
| `catalogue/migrations/0004_rule_validity_positive.py` | Validity must be above zero | — | `test_catalogue.py::test_validity_must_be_positive` |
| `catalogue/migrations/0002_append_only_versions.py` | Rule versions can't be updated or deleted by the app role: a change is a new version | — | `test_catalogue.py::test_rule_versions_cannot_be_edited` |

### positions: areas, positions, who holds them

| File | Responsible for | Key names | Tests |
|---|---|---|---|
| `positions/models.py` | The authority hierarchy: areas (taluka, district, state, each with a parent), exactly one approving position per area (its level is the area's level), and assignments saying who holds a position from when to when; the database allows only one active holder per position | `AreaLevel`, `Area`, `Position`, `PersonnelAssignment` | `test_positions.py` |
| `positions/service.py` | Finding the position that covers an area at a level (walking up parents; deterministic since one position per area), assigning or transferring a position (atomic, locks the position row first, ends the old holder, audited with `user_id` and `previous_user_id`), current holder and positions held | `covering_position`, `assign`, `current_holder`, `positions_held` | `test_positions.py` |
| `positions/migrations/0001_initial.py` | Creates the three tables and the one-active-holder constraint | — | `test_positions.py::test_database_allows_one_active_holder_per_position` |
| `positions/migrations/0002_one_position_per_area.py` | Drops `Position.level`; `Position.area` becomes one-to-one (one position per area) | — | `test_positions.py::test_one_position_per_area` |

### licensing: licence records, frozen permissions, trading_permitted

| File | Responsible for | Key names | Tests |
|---|---|---|---|
| `licensing/apps.py` | App registration | `LicensingConfig` | — |
| `licensing/migrations/0001_initial.py` | Creates the three licence tables and their constraints (exactly one scope, period ends after start) | — | `test_licensing.py` |
| `licensing/models.py` | Licences as issued by the existing process (number and GSTIN encrypted with blind indexes, holder, type, one substance or one class, area, status limited to the known values), append-only validity periods, and append-only permission snapshots taken in sets (a base row for the licence's scope plus, for a class licence, one override row per substance-specific rule in that class) | `LicenceStatus`, `Licence`, `LicenceValidityPeriod`, `LicencePermissionsSnapshot` | `test_licensing.py` |
| `licensing/service.py` | Recording a licence or renewal (atomic: licence, snapshot set, period and audit entry together or not at all; refused if no rule allows it), suspend/revoke (unknown statuses refused), current permissions from the newest snapshot set (a substance override wins over the base row), may-this-licence-trade-on-a-date, substance coverage, exact-match lookup by number | `record_licence`, `record_renewal`, `set_status`, `current_permissions`, `current_period`, `trading_permitted`, `covers`, `find_by_number`, `LicenceNotPermitted`, `InvalidLicenceData` | `test_licensing.py` |
| `licensing/migrations/0002_rls_and_append_only.py` | Row-level security (holder sees own by GSTIN; authority, Head, Software Owner, SYSTEM read all; only Licensing Authority and SYSTEM write); periods and snapshots append-only (REVOKE plus triggers) | — | `test_licensing.py` |
| `licensing/migrations/0003_status_only_updates.py` | The app role may update only `status` on a licence (no moving a licence to another holder) | — | `test_licensing.py::test_only_status_can_change_on_a_licence` |
| `licensing/migrations/0004_snapshot_substance.py` | Adds nullable `substance` to permission snapshots (NULL = base row, set = frozen substance override) | — | `test_licensing.py::test_class_licence_freezes_substance_override` |
| `licensing/migrations/0005_licence_status_valid.py` | Check constraint: status must be ACTIVE, SUSPENDED or REVOKED | — | `test_licensing.py::test_unknown_status_is_rejected` |
| `licensing/enrolment.py` | Licence-gated enrolment: match licence number + GSTIN + active + not yet enrolled, send the code to the contact ON FILE (the code is bound to that exact licence id, not just the GSTIN), audit after the send, then create the Licensee account with contact and `licensee_gstin_index` taken only from that same licence; every failure looks the same and is audited | `start_enrolment`, `complete_enrolment` | `test_enrolment.py` |
| `licensing/serializers.py` | Validates enrolment input (weak password rejected with 400 before the code is consumed); presents a licence as the permissions card dict (base permissions of the licence's own scope) | `EnrolmentStartSerializer`, `EnrolmentCompleteSerializer`, `licence_card` | `test_enrolment.py::test_weak_password_is_rejected_without_using_up_the_otp`, `test_licence_api.py::test_licensee_sees_own_licence_card` |
| `licensing/views.py` | Enrolment endpoints `POST /api/enrolment/start` and `/complete` (anonymous, CSRF-protected, throttled); `GET /api/licences/mine` (Licensee only, filtered by GSTIN and by row-level security); `GET /api/catalogue/substances` (any logged-in user) | `EnrolmentStartView`, `EnrolmentCompleteView`, `ENROLMENT_FAILED`, `MyLicencesView`, `SubstanceListView` | `test_enrolment.py`, `test_licence_api.py` |
| `licensing/urls.py` | Routes enrolment, my-licences and substance-list endpoints under `/api/` | `urlpatterns` | `test_enrolment.py` |
| `tests/conftest.py` fixtures | `make_licence(...)` records a licence as SYSTEM with sensible defaults (area Sanand; valid 2026-01-01 to 2047-12-31 so tests never expire before 2047); `make_licensee(licence)` creates a Licensee linked to the licence's GSTIN; `trade` sets up a seller, a buyer, the Sanand officer, the district superintendent and 400 L of seller whisky; `settle(qty, buyer=, officer=, reason_code=, comment=)` drives a transaction through the real services (`officer=None` stops at awaiting officer); `set_decided_on(tx, day)` moves a decision to noon local on that day; `review_setting` sets a 15-day period from 2026-06-01 for the district officer position; `DEMO_GSTIN` and `BUYER_GSTIN` use a non-existent state code | `make_licence`, `make_licensee`, `trade`, `settle`, `set_decided_on`, `DEMO_GSTIN`, `BUYER_GSTIN` | — |

### reasons: configurable reason codes

Reference data with no row-level security (ruling D-R12, same as the catalogue): everyone logged in may read it.

| File | Responsible for | Key names | Tests |
|---|---|---|---|
| `reasons/models.py` | Reason codes in a table so admins can add new ones without a code change; unique per kind; kind checked by the database | `ReasonKind`, `ReasonCode` | `test_reasons.py` |
| `reasons/service.py` | Listing active codes of a kind; validating a chosen code (must exist, be active, be of that kind; "OTHER" needs text) | `active_reasons`, `resolve_reason`, `InvalidReason` | `test_reasons.py` |
| `reasons/views.py`, `reasons/urls.py` | `GET /api/reason-codes?kind=` for dropdowns (any logged-in user; 400 for unknown kind) | `ReasonCodeListView` | `test_reasons.py::test_reason_code_api_*` |
| `reasons/migrations/0001_initial.py` | Creates the reason code table and its constraints | — | `test_reasons.py` |
| `reasons/migrations/0002_seed_defaults.py` | Seeds the default codes per kind, each with an "OTHER" that requires text | `DEFAULTS` | `test_reasons.py::test_defaults_*` |

### stock: balances and movements

Per business (GSTIN blind index) per substance. Only SYSTEM writes; holders read their own; Head Authority, Software Owner and SYSTEM read all.

| File | Responsible for | Key names | Tests |
|---|---|---|---|
| `stock/models.py` | Balance per business and substance (unique, never negative by database constraint); append-only movement history | `StockBalance`, `StockMovement`, `MovementReason` | `test_stock.py` |
| `stock/service.py` | Reading a balance; recording an opening balance once; moving stock between businesses in sorted lock order, refusing overdrafts and refusing to take the target above `max_target` (its licence's stock limit) | `balance_of`, `set_opening_balance`, `transfer`, `InsufficientStock`, `StockLimitExceeded` | `test_stock.py` |
| `stock/views.py`, `stock/urls.py` | `GET /api/stock/mine` (Licensee only) | `MyStockView` | `test_stock.py::test_my_stock_api` |
| `stock/migrations/0002_rls_and_append_only.py` | Row-level security (own-business read, SYSTEM-only write), balance updates limited to quantity and updated_at, movements append-only | — | `test_stock.py` |
| `stock/migrations/0003_stock_readers_without_la.py` | Recreates the stock read policies without the Licensing Authority: holders read their own business, Head Authority, Software Owner and SYSTEM read all (reversible) | — | `test_stock.py::test_licensing_authority_cannot_read_stock` |

### transactions: records, licence selection, checks, start, cancel, decisions and API

A seller-initiated sale of a substance to another business. Only SYSTEM writes (services check who may act first); parties, position holders and authorities read.

| File | Responsible for | Key names | Tests |
|---|---|---|---|
| `transactions/models.py` | The transaction (encrypted transporter details, designated and superintendent positions fixed at creation, status) and its append-only decisions | `Transaction`, `TransactionDecision`, `TransactionStatus`, `DecisionStep`, `DecisionOutcome`, `generate_reference` | `test_transaction_rules.py` |
| `transactions/selection.py` | Whether a licence is eligible (covers the substance, may trade on the day, permissions allow the action); choosing the licence a business uses: eligible, substance-specific licence preferred, then earliest | `licence_eligible`, `select_licence` | `test_transaction_rules.py` |
| `transactions/checks.py` | Plain-language problems: missing licence, per-transaction limits, seller stock, buyer stock limit | `fmt_qty`, `eligibility_problems`, `transaction_problems` | `test_transaction_rules.py` |
| `transactions/service.py` | The journey's first steps: buyer lookup by GSTIN (registered name only, audited by blind index), start (checks, licence selection, routing to the seller area's taluka and district positions, both required, encrypted transporter details), seller cancel while awaiting the buyer, one-time-code-signed buyer and officer decisions (`request_decision_code`, `decide`). Approval re-checks that both licences are still eligible today, the limits and stock, then moves stock re-checking the seller's stock and the buyer's cap under the balance locks; a refused approval rolls back and is audited (`transaction.approval_refused`). Reads run under the caller's own RLS. Writes run in `acting_as_system` after a plain-Python who-may-act check. A buyer rejection raises alerts (`alerts.service`) after the decision row and before the audit record. Lock order: user row, OTP challenge rows, transaction row, stock balance rows (sorted), alert inserts, audit last | `find_buyer`, `start_transaction`, `cancel_transaction`, `decision_role`, `request_decision_code`, `decide`, `load_visible`, `Transport`, `TransactionRefused`, `NotAllowed`, `NO_OFFICER`, `NO_SUPERINTENDENT` | `test_transaction_service.py`, `test_transaction_decisions.py` |
| `transactions/presenters.py` | What each viewer sees: summary and detail (transport, designated officer, status timeline, next action, `can_decide`). Party names read as SYSTEM, registered name only; buyer and officer comments and the officer position's holder (`held_by`) shown to authority viewers (officer, superintendent, head authority, software owner) only | `transaction_summary`, `transaction_detail` | `test_transaction_api.py` |
| `transactions/serializers.py` | Input validation with fix-it messages (GSTIN, quantity above 0, vehicle number format, six-digit code, outcome) | `BuyerLookupSerializer`, `NewTransactionSerializer`, `DecideSerializer` | `test_transaction_api.py::test_invalid_input_is_400` |
| `transactions/views.py`, `transactions/urls.py` | Thin HTTP layer: buyer lookup (Licensee only, `lookup` throttle), create and cancel (Licensee only), list (50 newest) and detail (any logged-in user; RLS scopes rows), decision code and decide (`otp` throttle). Refusals return 422 with reasons, wrong code 401, not allowed 403, unknown or invisible 404 | `BuyerLookupView`, `TransactionListView`, `TransactionDetailView`, `DecisionCodeView`, `DecideView`, `CancelView` | `test_transaction_api.py` |
| `transactions/migrations/0002_rls_and_append_only.py` | Row-level security (party, position-holder and authority read; SYSTEM-only write), only status and decided_at updatable, decisions append-only | — | `test_transaction_rules.py` |
| `transactions/migrations/0003_superintendent_required.py` | `superintendent_position` becomes required | — | `test_transaction_service.py::test_district_without_superintendent_is_refused` |
| `transactions/migrations/0004_indexes.py` | Indexes for the seller pattern count, buyer lookups and the superintendent's batch queries | — | `test_alerts.py::test_pattern_counts_recent_rejections` |

### alerts: buyer-rejection alerts for authorities

In-app alerts addressed to positions, not people: whoever currently holds the position sees and acknowledges them, including after a transfer. Only SYSTEM writes; position holders, Head Authority, Software Owner and SYSTEM read. Alerts and acknowledgements are append-only.

| File | Responsible for | Key names | Tests |
|---|---|---|---|
| `alerts/models.py` | An alert (kind, addressed position, transaction, reason, comment, pattern count) and its at-most-one acknowledgement | `AuthorityAlert`, `AlertAcknowledgement`, `AlertKind` | `test_alerts.py` |
| `alerts/service.py` | Raising alerts inside the decision's SYSTEM block (buyer rejection: one to the designated officer's position, one to the superintendent's, with the seller's 30-day buyer-rejection count); acknowledging (the user must currently hold the position; once only, including when two requests race and the unique constraint fires; audited as `alert.acknowledged`); ordinal and pattern wording | `raise_buyer_rejection_alerts`, `raise_flag_alert`, `acknowledge`, `NotAllowed`, `PATTERN_WINDOW`, `ordinal`, `pattern_text` | `test_alerts.py` |
| `alerts/presenters.py` | What an authority sees for an alert: kind, transaction reference, substance, quantity, registered party names (read as SYSTEM; never licence numbers, GSTINs or contacts), reason, comment, pattern wording (buyer rejections), acknowledgement details | `alert_view` | `test_alerts_api.py` |
| `alerts/views.py`, `alerts/urls.py` | Thin HTTP layer: list (any logged-in user; RLS scopes rows to held positions; unacknowledged first, then newest, at most 100) and acknowledge (note capped at 500 characters; not allowed returns 403) | `AlertListView`, `AcknowledgeView` | `test_alerts_api.py` |
| `alerts/migrations/0002_rls_and_append_only.py` | Row-level security (position-holder and authority read, SYSTEM-only write), append-only via REVOKE and triggers (reversible) | — | `test_alerts.py::test_only_position_holders_and_authorities_see_alerts`, `test_alerts.py::test_alerts_and_acknowledgements_are_append_only_even_for_owner` |

### oversight: superintendent review periods and batches

Each district superintendent position has a review period (15, 30 or 60 days). When a period has ended, SYSTEM creates a batch listing the approved transactions of that period. Batches and items are append-only; readable by the current holder of the position, Head Authority, Software Owner and SYSTEM. Flags and sign-offs arrive in Task 4.

| File | Responsibility | Key names | Tests |
|---|---|---|---|
| `oversight/models.py` | The review setting (one per district position), batches (one per position and period start) and batch items; `REVIEW_PERIODS`, `SIGN_OFF_DAYS` (30) and `due_on()` | `SuperintendentSetting`, `OversightBatch`, `BatchItem` | `test_oversight_batches.py` |
| `oversight/service.py` | Setting the review period (district positions only; lookups and write run as SYSTEM so the caller's RLS cannot hide batches; a change continues the day after the last batch, or keeps the existing start when no batch exists; an explicit start that would skip or overlap days is refused; audited as `oversight.review_period_set`) and idempotent batch creation for every completed period (audited as `oversight.batch_created`) | `set_review_period`, `create_due_batches`, `InvalidSetting` | `test_oversight_batches.py` |
| `oversight/management/commands/create_due_batches.py` | Daily job: `manage.py create_due_batches [--today YYYY-MM-DD]` runs `create_due_batches` as SYSTEM | `Command` | `test_oversight_batches.py::test_command_creates_due_batches` |
| `oversight/migrations/0002_rls_and_append_only.py` | Row-level security (position-holder and authority read, SYSTEM-only write), append-only via REVOKE and triggers (reversible); the setting has no RLS | — | `test_oversight_batches.py::test_only_the_superintendent_and_authorities_see_batches`, `test_batches_are_append_only_even_for_owner` |

### audit: tamper-evident audit log

| File | Responsible for | Key names | Tests |
|---|---|---|---|
| `audit/hashing.py` | Hash-chain maths: each entry's hash covers the previous one | `compute_hash`, `event_fields`, `GENESIS_HASH` | `test_audit_hashing.py` |
| `audit/models.py` | The audit entry table, plus a single row holding the latest hash | `AuditEvent`, `AuditChainHead` | `test_audit.py` |
| `audit/service.py` | Writing an entry. Rules: call it **last** in a request; payloads hold **IDs and lookup keys only, never personal data** | `record` | `test_audit.py` |
| `audit/verify.py` | Recomputing the chain and reporting the first broken entry | `verify_chain`, `ChainReport` | `test_audit.py` |
| `audit/migrations/0002_protect_and_rls.py` | Append-only (REVOKE plus a trigger), readable only by Software Owner, Head Authority and SYSTEM | — | `test_audit.py` |
| `audit/management/commands/verify_audit_chain.py` | Scheduled integrity check; exits with an error if the log was altered | — | `test_audit.py::test_verify_command_*` |

### Repository, CI and local setup

| File | Responsible for | Check name |
|---|---|---|
| `.github/workflows/ci.yml` | Lint, format, migrations check, tests, dependency vulnerability audit, production settings check | `backend` |
| `.github/workflows/branch-policy.yml` | Pull requests into `main` must come from `dev` | `source-branch` |
| `.github/workflows/codeql.yml` | Security scanning of Python and GitHub Actions | `analyze (python)`, `analyze (actions)` |
| `.github/dependabot.yml` | Weekly dependency and action updates | — |
| GitHub ruleset "Protect dev and main" | Pull request required, the checks above must pass, merge commits only, no force-push, deletion or bypass | — |
| `docker-compose.yml`, `docker/postgres-init.sh` | Local Postgres 16 with roles `gj_owner` (migrations and tests) and `gj_app` (the running app) | — |

---

## 3. Test catalogue: what each test proves

Run all: `cd backend && uv run --env-file .env.test pytest`. Run one: `... pytest tests/<file>.py::<test> -v`.

Shared fixtures (`make_user`, `make_licence`, `make_licensee`, `trade`, `org`, `catalogue`, `otp_outbox`, `audit_actions`, `settle`) live in `tests/conftest.py`; see its row in section 2.

### `test_env.py`: configuration loading
| Test | Proves |
|---|---|
| `test_required_returns_trimmed_value` | Values are read without surrounding spaces |
| `test_required_fails_fast_when_missing` / `_when_blank` | A missing or blank required setting stops startup |
| `test_optional_uses_default_when_unset` | Optional settings fall back to their default |
| `test_flag_parses_truthy_and_falsy`, `test_flag_default_when_unset` | On/off flags are read correctly |
| `test_listed_splits_and_trims` | Comma-separated lists are parsed |

### `test_health.py`: health check
| Test | Proves |
|---|---|
| `test_health_returns_ok` | `GET /api/health` → `{"status": "ok"}` |
| `test_health_rejects_post` | Only GET is allowed |
| `test_security_headers_present` | `X-Frame-Options: DENY` and `nosniff` are sent |

### `test_db_privileges.py`: least-privilege database role
| Test | Proves |
|---|---|
| `test_app_role_is_not_superuser_and_cannot_bypass_rls` | `gj_app` has no superuser and no row-level-security bypass |
| `test_app_role_owns_no_tables` | The app owns nothing, so it can't disable protections |
| `test_app_role_can_use_migrated_tables` | The app can read and write data |
| `test_tables_created_later_are_granted_to_app_role` | Future tables are accessible automatically |
| `test_app_role_cannot_create_tables` | The app can't change the schema |

### `test_crypto.py`: encryption and lookup keys
| Test | Proves |
|---|---|
| `test_encrypt_round_trip` | Decrypt returns the original value |
| `test_ciphertext_does_not_reveal_plaintext`, `test_encryption_is_randomised` | Stored values reveal nothing, and the same input encrypts differently each time |
| `test_decrypt_rejects_garbage`, `..._with_another_key` | Tampered data or a wrong key fails safely |
| `test_blind_index_is_deterministic_and_normalised` | Same value → same key, ignoring case and spaces |
| `test_blind_index_differs_between_values`, `_depends_on_secret_key`, `_differs_by_context` | Keys can't be guessed or linked across fields |
| `test_blind_index_rejects_empty_context` | Every lookup key must name its field |

### `test_users.py`: accounts and roles
| Test | Proves |
|---|---|
| `test_user_id_is_system_generated`, `test_user_ids_are_unique` | IDs look like `GJ` plus 10 unambiguous characters and are unique |
| `test_password_is_hashed_with_argon2` | Passwords are stored as Argon2 hashes |
| `test_contact_is_encrypted_at_rest` | The contact is encrypted in the database |
| `test_database_rejects_unknown_role` | The database only accepts the 6 roles |
| `test_has_role`, `test_inactive_user_has_no_role` | Role checks work, and deactivated users have no role |
| `test_app_role_cannot_delete_users` | Accounts can never be deleted |

### `test_db_context.py`: row-level-security context
| Test | Proves |
|---|---|
| `test_set_actor_is_visible_to_postgres` | Postgres sees the acting user and role |
| `test_set_actor_refuses_to_run_outside_a_transaction` | The actor can't be set where it would leak |
| `test_middleware_tags_request_with_authenticated_user` | Logged-in requests carry the user's identity |
| `test_middleware_sets_no_actor_for_anonymous_request`, `test_anonymous_request_after_authenticated_request_has_no_actor` | Anonymous requests never inherit a previous identity |
| `test_middleware_rolls_back_writes_on_server_error` | A 5xx undoes the request's writes |

### `test_rollback_on_exception.py`
| Test | Proves |
|---|---|
| `test_raised_exception_rolls_back_audit_write` | A raised 4xx error undoes the request's writes |

### `test_audit_hashing.py` and `test_audit.py`: audit log
| Test | Proves |
|---|---|
| `test_hash_is_64_hex_chars_and_deterministic`, `test_hash_ignores_payload_key_order`, `test_hash_changes_when_any_field_changes` | The hash is stable and sensitive to any change |
| `test_each_event_links_to_the_previous_one` | Entries form a chain |
| `test_verify_passes_on_untouched_chain` | A healthy log verifies |
| `test_record_rejects_nested_payload` | Only simple values can be stored, so hashes are reproducible |
| `test_app_role_cannot_update_events` / `_delete_events` | The app can't edit or delete entries |
| `test_trigger_blocks_changes_even_for_table_owner` | Even the database owner is blocked |
| `test_verify_detects_edited_event` / `_deleted_middle_event` / `_deleted_last_event` | Every kind of tampering is detected |
| `test_verify_accepts_events_appended_after_head_read` | No false alarm when entries are written during a check |
| `test_only_audit_readers_can_read_events` (every role) | Only Software Owner and Head Authority can read the log |
| `test_anonymous_context_cannot_read_events` | Anonymous requests see nothing |
| `test_verify_command_reports_ok` / `_fails_loudly_on_tampering` | The scheduled check reports correctly |

### `test_otp_subject.py`: one-time codes before an account exists
| Test | Proves |
|---|---|
| `test_subject_code_goes_to_the_given_contact` | The enrolment code is sent to the contact given, not to any stored user |
| `test_verify_subject_returns_subject_once` | A subject code works exactly once and returns the subject |
| `test_user_verify_rejects_subject_challenge` | An enrolment code cannot be used as a user login code |
| `test_subject_verify_rejects_user_challenge` | A user's login code cannot be used for enrolment |
| `test_new_subject_challenge_supersedes_old` | A new enrolment code cancels the previous one |
| `test_database_requires_exactly_one_of_user_or_subject` | The database refuses a code tied to both a user and a subject |
| `test_database_allows_one_open_challenge_per_subject_and_purpose` | The database refuses a second open code for the same subject and purpose |
| `test_issue_for_subject_rejects_empty_subject` | An enrolment code cannot be issued without a subject |

### `test_otp.py`: one-time codes
| Test | Proves |
|---|---|
| `test_issue_sends_six_digit_code_to_registered_contact` | Codes go only to the contact on file |
| `test_code_is_not_stored_in_plaintext` | Only an HMAC of the code is stored |
| `test_verify_locks_user_before_challenge` | Checking a code locks the user row before the challenge row, matching login's order (deadlock guard) |
| `test_correct_code_returns_user_once` | A code works exactly once |
| `test_wrong_code_is_rejected_and_counted`, `test_challenge_closes_after_max_attempts` | Wrong guesses count; after 5 the code is dead |
| `test_expired_code_is_rejected` | Codes expire after 5 minutes |
| `test_new_challenge_supersedes_the_old_one`, `test_database_allows_one_open_challenge_per_user_and_purpose` | Only one open code per user and purpose, even under concurrency |
| `test_inactive_user_cannot_complete_otp` | Deactivated users can't log in |
| `test_malformed_challenge_id_is_rejected` | Junk input fails safely |

### `test_login_api.py`: login API
| Test | Proves |
|---|---|
| `test_full_login_requires_password_and_otp` | The password alone doesn't log you in; password plus code does |
| `test_user_id_is_case_insensitive` | `gj…` and `GJ…` both work |
| `test_wrong_password_and_unknown_user_look_identical` | User IDs can't be discovered from responses |
| `test_locked_and_inactive_accounts_still_check_the_password` | …or from response timing |
| `test_wrong_otp_is_rejected` | A wrong code doesn't log in |
| `test_account_locks_after_repeated_failures` | 5 wrong passwords lock the account |
| `test_account_locks_after_too_many_code_requests` | 5 code requests in 15 minutes lock the account |
| `test_locking_cancels_outstanding_login_code` | A code sent before the lock stops working |
| `test_login_is_rate_limited`, `test_rate_limit_ignores_spoofed_forwarded_for` | 10 per minute per IP, and a faked IP header doesn't bypass it |
| `test_session_cookie_is_hardened` | Session cookie is HttpOnly, Secure and SameSite=Strict |
| `test_logout_ends_session` | Logout really logs out |
| `test_csrf_endpoint_sets_cookie`, `test_login_requires_csrf_token` | Anti-forgery (CSRF) protection is enforced on login |
| `test_login_events_are_audited` | Failures, successes and logouts are written to the audit log |
| `test_unknown_user_attempt_is_not_stored_in_plaintext` | Mistyped IDs or passwords never enter the audit log in plain text |

### `test_permissions.py`: role checks
| Test | Proves |
|---|---|
| `test_listed_role_is_allowed` | The permitted role gets in |
| `test_every_other_role_is_refused` (every role) | Every other role gets 403 |
| `test_anonymous_is_refused`, `test_deactivated_user_is_refused` | Not-logged-in and deactivated users get 403 |

### `test_create_software_owner.py`: first admin account
| Test | Proves |
|---|---|
| `test_creates_first_owner_and_audits_it` | Creates the owner and writes it to the audit log |
| `test_refuses_when_an_owner_already_exists` | It can only ever create the first owner |
| `test_rejects_weak_password`, `test_rejects_mismatched_passwords` | Password rules are enforced |

### `test_catalogue.py`: catalogue and rules
| Test | Proves |
|---|---|
| `test_class_rule_applies_to_every_substance_in_the_class` | A class-level rule covers every substance in that class |
| `test_substance_rule_overrides_class_rule` | A substance-specific rule beats the class rule, other substances keep the class rule |
| `test_no_rule_means_not_permitted` | A licence type with no rule gets no permission |
| `test_class_scope_resolves_class_rule` | Looking up by class alone finds the class rule |
| `test_latest_version_wins_and_versions_increment` | A change is a new version (1, 2, ...) and the latest is used |
| `test_rule_needs_exactly_one_scope` | The database rejects a rule with both or neither of substance and class |
| `test_rule_versions_cannot_be_edited` | The app role can't update rule versions |
| `test_limits_must_be_positive` | The database rejects zero or negative limits |
| `test_rule_versions_blocked_even_for_table_owner` | A trigger stops even the table owner editing a rule version |
| `test_validity_must_be_positive` | The database rejects zero validity months |

### `test_positions.py`: areas, positions, assignments
| Test | Proves |
|---|---|
| `test_covering_position_at_same_level` | A taluka resolves to its own taluka position |
| `test_covering_position_walks_up_the_hierarchy` | A taluka resolves to the district position above it |
| `test_covering_position_none_when_level_has_no_position` | No position at a level means none is returned |
| `test_assign_makes_user_the_holder` | Assigning makes the user holder, lists the position, writes an audit event |
| `test_transfer_moves_the_position_immediately` | A new assignment removes the old holder at once |
| `test_only_personnel_can_hold_positions` | Non-Personnel users can't be assigned |
| `test_vacant_position_has_no_holder` | An unassigned position has no holder |
| `test_database_allows_one_active_holder_per_position` | The database rejects two active holders |
| `test_one_position_per_area` | The database rejects a second position in the same area, so routing is deterministic |
| `test_transfer_audit_names_previous_holder` | The assignment audit event names the new holder and the one it replaced (empty when vacant) |

### `test_licensing.py`: licence records and trading_permitted
| Test | Proves |
|---|---|
| `test_recorded_licence_freezes_rule_permissions` | A new licence gets a snapshot of the rule's permissions |
| `test_rule_change_does_not_touch_existing_licence` | A later rule version does not change an existing licence |
| `test_renewal_takes_a_fresh_snapshot_of_the_latest_rule` | Renewal freezes the latest rule; both events are audited |
| `test_class_licence_freezes_substance_override` | A class licence freezes a stricter substance rule (Retail + Rum may not sell) while other substances and the base keep the class rule |
| `test_override_added_after_recording_does_not_apply_until_renewal` | A substance override created later only applies once a renewal takes a new snapshot set |
| `test_licence_type_without_rule_cannot_be_recorded` | No rule means the licence cannot be recorded |
| `test_refused_licence_leaves_no_partial_record` | A refused licence leaves no rows behind |
| `test_malformed_gstin_is_rejected` | GSTIN must be in the valid format |
| `test_period_must_end_after_it_starts` | A period cannot end before it starts |
| `test_identifiers_are_encrypted_at_rest` | Number and GSTIN are unreadable in the database |
| `test_find_by_number_is_exact_but_forgiving_about_case_and_spaces` | Lookup is exact; no partial search |
| `test_trading_permitted_follows_validity_period` | Trading is allowed only within a period (inclusive dates) |
| `test_gap_between_periods_is_not_permitted` | A gap between renewals is not covered |
| `test_suspended_or_revoked_licence_cannot_trade` | Suspended or revoked licences cannot trade |
| `test_unknown_status_is_rejected` | `set_status` refuses an unknown status, and so does the database |
| `test_covers_substance_directly_or_through_its_class` | A licence covers its substance or every substance in its class |
| `test_holder_sees_only_their_own_licences` | A licensee sees only licences with their GSTIN (and their periods) |
| `test_anonymous_context_sees_no_licences` | No actor, no licences |
| `test_licensing_authority_sees_all_licences` | The authority reads every licence |
| `test_non_holder_sees_no_snapshots` | A licensee sees no permission snapshots of another GSTIN's licence |
| `test_licensee_cannot_change_licence_status` | A licensee's status update touches no rows; the status stays unchanged |
| `test_head_authority_can_read_but_not_record_licences` | Head Authority reads licences but the database refuses its inserts |
| `test_licensee_cannot_record_a_licence` | A licensee cannot write licences (database refuses) |
| `test_validity_periods_cannot_be_edited` | The app role cannot update validity periods |
| `test_periods_and_snapshots_blocked_even_for_table_owner` | Triggers stop even the owner editing periods and snapshots |
| `test_acting_as_system_restores_previous_actor` | The SYSTEM block puts the caller's actor back |
| `test_only_status_can_change_on_a_licence` | Even the authority cannot rewrite other licence columns; status changes still work |
| `test_acting_as_system_restores_actor_after_caught_nested_error` | A caught error inside the SYSTEM block never leaves the caller running as SYSTEM |
| `test_acting_as_system_does_not_mask_database_errors` | A failing SQL statement inside the SYSTEM block surfaces its own error |

### `test_enrolment.py`: licence-gated enrolment

| Test | Proves |
|---|---|
| `test_enrolment_creates_a_licensee_linked_to_the_gstin` | Full flow makes a Licensee whose GSTIN link and contact come from the licence |
| `test_otp_always_goes_to_contact_on_file` | A contact supplied in the request is ignored |
| `test_wrong_gstin_and_unknown_licence_look_identical` | Same 401 body for both; no code sent (no enumeration) |
| `test_suspended_licence_cannot_enrol` | Only active licences can enrol |
| `test_gstin_already_enrolled_cannot_enrol_again` | One account per GSTIN |
| `test_weak_password_is_rejected_without_using_up_the_otp` | 400 on weak password, code still usable |
| `test_wrong_code_does_not_enrol` | Wrong code gives 401 and no account |
| `test_enrolment_is_rate_limited` | 11th start in a minute gets 429 |
| `test_enrolment_is_audited` | failed, otp_sent and completed events are recorded |
| `test_enrolment_uses_the_contact_of_the_licence_that_received_the_code` | With two licences on one GSTIN, the account gets the contact of the licence whose code was entered |
| `test_database_allows_one_account_per_gstin` | The database itself refuses a second account for the same GSTIN |

### `test_licence_api.py`: permissions card and substance list

| Test | Proves |
|---|---|
| `test_licensee_sees_own_licence_card` | A Licensee gets exactly their own licence's card (fields, quantities as strings, validity dates), not another GSTIN's |
| `test_only_licensees_have_my_licences` | Personnel, Licensing Authority and Head Authority get 403 |
| `test_my_licences_requires_login` | Anonymous gets 403 |
| `test_substance_list_for_logged_in_users` | Any logged-in user can read the substance list |

### `test_reasons.py`: reason codes

| Test | Proves |
|---|---|
| `test_defaults_are_seeded_for_every_kind` | Every kind has at least four active codes including OTHER |
| `test_buyer_defaults_match_the_spec` | The buyer rejection labels match the spec |
| `test_other_requires_text` | OTHER with blank text is refused; with text it is accepted |
| `test_unknown_or_inactive_code_is_rejected` | Unknown or deactivated codes are refused |
| `test_code_of_another_kind_is_rejected` | A code from a different kind is refused |
| `test_admin_can_add_a_new_reason_without_code_change` | A new row is usable immediately |
| `test_reason_code_api_lists_active_codes` | The API lists active codes for a kind; unknown kind gives 400 |
| `test_reason_code_api_requires_login` | Anonymous gets 403 |

### `test_stock.py`: stock balances and movements

| Test | Proves |
|---|---|
| `test_balance_is_zero_without_a_row` | No row means zero stock |
| `test_opening_balance_is_recorded_once_with_a_movement` | Opening balance writes a movement and an audit event; a second one is refused |
| `test_transfer_moves_stock_and_logs_both_sides` | A transfer debits the seller, credits the buyer and logs both movements |
| `test_transfer_refuses_more_than_the_seller_holds` | Overdraft is refused and nothing changes |
| `test_transfer_refuses_above_target_limit` | A transfer that would take the target above `max_target` raises `StockLimitExceeded` and nothing changes |
| `test_database_never_allows_negative_stock` | The database rejects a negative balance |
| `test_holder_sees_only_own_stock` | Row-level security shows a Licensee only their business |
| `test_licensing_authority_cannot_read_stock` | The Licensing Authority sees no balances or movements |
| `test_only_system_can_write_stock` | Non-SYSTEM roles cannot write balances |
| `test_movements_are_append_only_even_for_owner` | Movements cannot be updated, even by the schema owner |
| `test_my_stock_api` | `/api/stock/mine` returns the holder's balances |

### `test_transaction_rules.py`: transaction records, selection and checks

| Test | Proves |
|---|---|
| `test_fmt_qty_drops_trailing_zeros` | Quantities print without trailing zeros |
| `test_reference_format` | References start with TX and are 12 characters |
| `test_selects_licence_that_allows_the_action` | A licence permitting sell or buy is selected |
| `test_substance_scoped_licence_is_preferred` | A licence for the exact substance beats a class licence |
| `test_expired_or_suspended_licence_is_not_selected` | Expired or suspended licences are never selected |
| `test_substance_override_can_forbid_selling` | A substance rule can forbid selling while the class allows it |
| `test_eligibility_problems_are_plain` | Missing-licence messages are plain sentences |
| `test_per_transaction_limit_message` | Both parties' per-transaction limits are reported |
| `test_stock_and_buyer_capacity_messages` | Seller shortfall is reported |
| `test_buyer_stock_limit_message` | Buyer stock-limit breach is reported |
| `test_valid_transaction_has_no_problems` | A valid request gives no problems |
| `test_transaction_visibility` | Parties, position holders and authorities see a transaction; outsiders do not |
| `test_only_system_writes_and_only_status_changes` | Non-SYSTEM cannot update; only status and decided_at are updatable |
| `test_decisions_are_append_only_even_for_owner` | Decisions cannot be updated, even by the schema owner |

---

### `test_transaction_service.py`: start, look up and cancel

| Test | Proves |
|---|---|
| `test_find_buyer_returns_registered_name_only` | Lookup tolerates case and spaces, returns only the name, gives None for unknown or malformed GSTINs, and audits every lookup |
| `test_buyer_lookup_audit_holds_no_gstin` | The lookup audit payload never contains the GSTIN |
| `test_start_creates_transaction_routed_to_seller_area_officer` | A new transaction awaits the buyer, uses the seller area's taluka and district positions, the selected licences, and is audited |
| `test_transporter_identifiers_are_encrypted` | Transporter id and vehicle number are stored encrypted |
| `test_over_limit_is_refused_with_plain_reasons` | Over-limit quantity is refused with the plain reason and nothing is saved |
| `test_unknown_buyer_is_refused` | A buyer without a valid buying licence is refused in plain words |
| `test_cannot_sell_to_own_business` | Selling to your own GSTIN is refused |
| `test_area_without_officer_position_is_refused` | No taluka officer position for the seller's area is refused |
| `test_district_without_superintendent_is_refused` | No district superintendent position for the seller's area is refused |
| `test_seller_can_cancel_only_while_awaiting_buyer` | Seller cancels while awaiting buyer (audited); a second cancel is not allowed |
| `test_buyer_cannot_cancel` | Only the seller can cancel |

### `test_transaction_decisions.py`: signed decisions and stock transfer

| Test | Proves |
|---|---|
| `test_happy_path_moves_stock_on_approval` | Buyer confirm then officer approve moves stock, records both decisions, audits both |
| `test_decision_records_position_and_holder` | The officer decision stores the position, the holder and the code-verified time |
| `test_buyer_reject_needs_a_buyer_reason` | A buyer rejection needs a buyer-kind reason, checked before the code is used |
| `test_officer_reject_other_needs_text` | Officer "Other" needs text; a rejection moves no stock |
| `test_wrong_code_records_no_decision_but_counts_attempt` | A wrong code returns None, counts the attempt, records nothing |
| `test_only_the_right_party_can_decide_at_each_step` | Only the party whose turn it is can request a code |
| `test_buyer_cannot_approve_and_officer_cannot_confirm` | Outcomes are limited to the role's step |
| `test_transferred_officer_cannot_decide` | After a transfer only the new position holder can decide |
| `test_approval_rechecks_stock` | Approval re-runs the checks; a refusal rolls back, leaves the transaction waiting and is audited |
| `test_decision_code_is_bound_to_the_user` | Another user's valid code cannot be spent |
| `test_approval_refused_when_seller_suspended_after_confirm` | A seller licence suspended after the buyer confirms blocks approval; nothing moves |
| `test_approval_refused_when_buyer_licence_expired` | A buyer licence that expired before approval blocks it; nothing moves |
| `test_transfer_insufficient_under_lock_maps_to_refusal` | A stock shortfall found under the balance lock becomes a plain refusal; nothing moves |

### `test_alerts.py`: buyer-rejection alerts

| Test | Proves |
|---|---|
| `test_ordinal` | 1st, 2nd, 3rd, 4th, 11th to 13th, 21st, 22nd, 103rd |
| `test_pattern_text` | The pattern wording reads "3rd buyer rejection for this seller in the last 30 days" |
| `test_buyer_rejection_alerts_officer_and_superintendent` | A buyer rejection raises one alert for the designated officer's position and one for the superintendent's, with the reason and pattern count 1; the audit record is still last |
| `test_buyer_comment_is_kept_on_the_alert` | The buyer's comment is stored on the alert |
| `test_confirm_and_officer_reject_raise_no_alerts` | Buyer confirmation and officer rejection raise nothing |
| `test_pattern_counts_recent_rejections` | The third buyer rejection for a seller shows count 3 |
| `test_pattern_ignores_rejections_older_than_30_days` | A rejection decided 31 days ago is not counted |
| `test_only_position_holders_and_authorities_see_alerts` | The officer and superintendent see one alert each, Head Authority sees both; seller, buyer and unrelated personnel see none |
| `test_alert_follows_the_position_after_transfer` | After a transfer the old holder sees nothing and the new holder sees and acknowledges the alert (audited) |
| `test_acknowledge_rules` | Only the current holder of the addressed position can acknowledge; a second acknowledgement is refused |
| `test_alerts_and_acknowledgements_are_append_only_even_for_owner` | The schema owner cannot update alerts or acknowledgements |
| `test_duplicate_acknowledgement_race_is_reported_plainly` | When another request wins the race past the exists check, the unique constraint is reported as "already acknowledged" |

### `test_alerts_api.py`: alerts API

| Test | Proves |
|---|---|
| `test_officer_sees_alert_with_pattern` | The officer lists the alert with reason, pattern wording and registered names, and no licence numbers |
| `test_acknowledge_over_http` | Acknowledging with a note returns the updated alert and the unacknowledged count drops to 0 |
| `test_licensees_see_no_alerts` | A licensee gets an empty list |
| `test_cannot_acknowledge_someone_elses_alert` | The superintendent cannot acknowledge the officer's alert (403) |

### `test_oversight_batches.py`: review periods and batches

| Test | Proves |
|---|---|
| `test_review_period_must_be_15_30_or_60_days` | Any other period is refused |
| `test_review_period_only_for_district_positions` | A taluka position cannot have a review period |
| `test_batch_holds_approved_transactions_of_the_period` | Only approved transactions decided inside the period are listed; due date is 30 days after the period ends |
| `test_no_batch_for_the_period_still_running` | No batch until the period has fully ended |
| `test_batches_are_created_once_per_completed_period` | Back-to-back periods are created once each and a rerun creates none; each is audited |
| `test_changing_the_period_before_any_batch_keeps_the_start` | With no batch yet, a new length keeps the existing start date |
| `test_review_period_set_by_licensing_authority_sees_existing_batches` | A Licensing Authority caller still continues after the last batch (lookups run as SYSTEM) |
| `test_review_period_cannot_skip_days` | An explicit start that would leave days unreviewed or overlap a batch is refused |
| `test_empty_period_still_gets_a_batch` | A period with no approvals still gets an empty batch |
| `test_changing_the_period_continues_after_the_last_batch` | A new period length starts the day after the last batch ended |
| `test_only_the_superintendent_and_authorities_see_batches` | The superintendent and Head Authority see the batch; the officer and the seller see none |
| `test_batches_are_append_only_even_for_owner` | The schema owner cannot update a batch |
| `test_command_creates_due_batches` | The command reports the batches it created |

### `test_transaction_api.py`: transaction API

| Test | Proves |
|---|---|
| `test_full_journey_over_http` | Lookup, create, buyer confirm and officer approve over HTTP; the timeline and next action are right and stock moves |
| `test_refused_transaction_returns_reasons` | A refused start returns 422 with the plain-language reasons |
| `test_invalid_input_is_400` | Empty vehicle number, negative quantity and unknown substance return 400 |
| `test_unknown_buyer_lookup_is_404` | An unknown GSTIN returns 404 with the check-15-characters message |
| `test_wrong_code_is_401` | A wrong code returns 401 with the request-a-new-code message |
| `test_outsider_cannot_see_transaction` | An unrelated business gets 404 on detail and an empty list |
| `test_buyer_comment_is_hidden_from_seller` | The seller sees the reason label but not the buyer's comment; the officer sees it |
| `test_seller_sees_buyer_name_but_not_licence_number` | The seller sees the buyer's registered name; no licence number appears |
| `test_confirm_with_blank_reason_code_is_accepted` | A confirm that sends an empty reason code is accepted |
| `test_seller_can_cancel_and_buyer_cannot` | The seller cancels (200, CANCELLED); the buyer gets 403 |
| `test_non_licensee_cannot_start_or_look_up` | Personnel get 403 on create and buyer lookup |
| `test_decide_maps_errors` | A wrong-kind reason returns 400; an approval refused for stock returns 422 with the reason |
| `test_post_requires_csrf_token` | Creating a transaction without the CSRF header returns 403; with it, 201 |
| `test_timeline_shows_holder_to_authority_only` | The officer sees who held the position on the approval; the seller does not; `can_decide` is true only for the party whose turn it is |

---

## 4. Conventions every change must follow

| Rule | Why | Enforced by |
|---|---|---|
| Views **raise** to roll back and **return** to commit | No half-saved data | `core/exceptions.py`, `test_rollback_on_exception.py` |
| Call `audit.record()` as the **last** lock in a request | Avoids deadlocks on the audit chain lock | Docstring in `audit/service.py` (code review) |
| Audit payloads hold IDs, codes and lookup keys only, **never personal data** | The log is permanent; DPDP erasure must stay possible | Docstring and code review |
| `blind_index` always names its field (`"licence_number"`, `"gstin"`, …) | Values can't be linked across tables | `test_blind_index_rejects_empty_context` |
| Tests use `app_db` (runs as `gj_app`), never `transactional_db` | Tests see production privileges | `tests/conftest.py` docstring |
| Every new business table gets row-level-security policies in the migration that creates it | Database backstop for access rules | Code review |
| Every change goes feature branch → PR into `dev` → PR from `dev` into `main` | Test in dev before production | GitHub ruleset, `source-branch` check |
| Append-only tables REVOKE update/delete from `gj_app` and attach `reject_append_only_change()` triggers | Even the owner can't rewrite history | `core/migrations/0002_append_only_guard.py`, `test_catalogue.py` |
| One unit per substance class (quantities in a class share the class's unit); D2 stores the unit on each transaction | Quantities in a class can be added up safely | Seed data and code review |
| Catalogue tables are reference data with no row-level security, written only through Licensing Authority services (ruling D-R12) | Everyone may read the catalogue; writes go through `catalogue/service.py` | Code review |
| Reason codes are data. Add a row, never rename a code | Stored decisions keep pointing at the same meaning | Code review |
| D2a lock order: user row → OTP challenge rows → transaction row → stock balance rows (sorted by GSTIN index) → audit (`record()` last). Transaction writes happen only through services under SYSTEM. Alert inserts (`alerts.service`) go inside the decision's SYSTEM block, after the decision row and before `record()` | Prevents deadlocks; no path lets a user write a transaction directly | `transactions/migrations/0002_rls_and_append_only.py`, code review |
| Decisions verify the code BEFORE writing; a wrong code returns (commits the attempt); a refused approval raises (rolls back its writes) and is audited after the rollback | A failed guess is counted and a failed approval leaves no half-moved stock | `test_transaction_decisions.py` |
| Periods run back to back from `starts_on`; a batch is created only after its period ends; sign-off is due 30 days later | Predictable, idempotent oversight batches | `test_oversight_batches.py` |
| The review setting has no row-level security (configuration, ruling D-R6 style) | Written only through `set_review_period`, which audits every change | `oversight/service.py`, code review |
| **Update this file in the same PR** | Keeps the map trustworthy | Code review |

Open follow-ups from the reviews: [`superpowers/plans/2026-09-29-phase1-followups.md`](superpowers/plans/2026-09-29-phase1-followups.md).

