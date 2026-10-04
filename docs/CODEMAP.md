# Code Map

**What this is:** the one place that says which code is responsible for what, which user roles it serves, and which tests prove it. Use it to review, debug or change the system.

**Keep it current:** every pull request that adds, removes or changes code or tests updates this file in the same pull request. A reviewer should reject a code PR that leaves this map stale.

**Last updated:** 2026-10-04, D3 Task 6 (backend 529 tests, frontend 224 tests): the new-sale wizard at `/licensee/sale/new` (`features/sale/`): buyer lookup by GSTIN in a POST body with "Is this the right business?", substances limited to what the seller's licences let them sell, a live check (ok, the two-step notice, or the reasons) that must pass for the current buyer, substance and quantity before Next, transport details with help text, review and send (201 opens the new transaction with "Sent to the buyer for confirmation."; 422 shows the reasons and a way back to the goods). Drafts live only in `sessionStorage["gj.draft.sale"]` (debounced 300 ms, restored with Start over / Discard draft, cleared on send and sign-out). Also: `renderApp` keeps a test's own `server.use(...)` handlers ahead of its contract handlers. Before that, D3 Task 5: the licensee's home (`features/licensee/LicenseeHomePage`), transactions list with All / Sales / Purchases / Waiting for you tabs (`?side=`, `?awaiting=me`; stacked cards under 768 px) and the reusable transaction detail (`features/transactions/`): summary, transport, officer, approval chain, timeline, next action, decisions driven only by `allowed_outcomes` with the code dialog, the buyer's stock-limit state (Reject only, STOCK_LIMIT preset, no Confirm button), seller cancel with confirmation; the seller never sees buyer stock text. Also: the sign-in code's error is linked to the digits, 4xx queries are not retried, modal and drawer headers are no longer extra banner landmarks, loaders are `role="status"`, and a `buyer-stock` mock persona. Before that, D3 Task 4: shared components in `frontend/src/components/` (`StatusTimeline`, `CodeDialog`, `ReasonPicker`, `PermissionCard`, `StatusBadge`, `WhatsNextCard`, `ErrorNotice`, `Qty`, `DateText`, `EmptyState`), each with state tests and an axe check; AA-safe status colours in `theme.ts`. Before that, D3 Task 3: sign-in with a one-time code (`auth/SignInPage`), `SessionProvider` (sign-out and session expiry clear the query cache and `gj.draft.*` drafts), `RequireRole` guards and role landing routes, and the app shell (navy header, role navigation with a burger under 768 px, bell and alerts drawer stub, skip link), with placeholder pages for the screens later tasks build. Before that, D3 Task 2: API contracts captured from the real backend (`tests/test_api_contracts.py` → `frontend/src/test/contracts/`), the typed API client (CSRF, error mapping, session expiry), endpoint modules and TanStack Query hooks, contract-backed MSW handlers and mock mode. Before that, D3 Task 1: web app scaffold in `frontend/` (Vite, React 18, Mantine 7, i18n, Vitest with MSW and axe), `frontend` CI job, CodeQL for JavaScript/TypeScript, Dependabot for npm. Before that, D2d: maker-checker rule changes (`governance` app), catalogue reads for drafting forms, licence register and review-settings APIs.

---

## 1. User roles and where their rules live

| Role | What they can do today | Where it is enforced | Proving tests |
|---|---|---|---|
| **Licensee** (buyer and seller combined; what they may do comes from their licences) | Created only by licence-gated enrolment (a business with an active licence on record proves control with a code sent to the contact on file). Logs in with password and a one-time code. Sees only licences whose GSTIN matches their account (`licensee_gstin_index`, enforced by row-level security). Can view the permissions card of each of their own licences (`GET /api/licences/mine`). Sees own stock (`GET /api/stock/mine`). Sees transactions where their business is seller or buyer, matched by GSTIN. Sees their own view of each transaction (seller, buyer) with the other party's registered name only, never licence numbers or the buyer's free-text comment. May look up a buyer by GSTIN (sees only the registered name), dry-run a sale first (`POST /api/transactions/check`: reasons and approval chain, never the buyer's stock), start a transaction and cancel it while it waits for the buyer. As buyer, confirms or rejects (with a buyer reason) with a one-time code while the transaction waits for them. The seller is never refused because of the buyer's stock limit and never sees the buyer's stock numbers (not at start, not in the detail, not on the timeline). When the sale would take the buyer over their licence's stock limit, the buyer sees `stock_limit_problem` (their own numbers) and may only reject: a CONFIRM is refused (422, audited `transaction.confirm_refused`); a REJECT with no reason defaults to `STOCK_LIMIT`, which raises no alert and is not counted in the seller's rejection pattern. `STOCK_LIMIT` is refused when no such problem exists (refused under the lock: audited `transaction.reject_refused`). Home screen counts: transactions awaiting their decision (including ones over their stock limit) and their sales in progress. | `identity/roles.py` (`Role.LICENSEE`), `identity/login.py`, `identity/views.py`, `licensing/enrolment.py`, `licensing/views.py` (`MyLicencesView`); `stock/views.py` (`MyStockView`); `licensing/migrations/0002_rls_and_append_only.py` (licence read policy); `stock/migrations/0002_rls_and_append_only.py` (own-stock read policy); `transactions/service.py` (`find_buyer`, `check_transaction`, `start_transaction`, `cancel_transaction`, `decide`, `stock_limit_problem`); `transactions/checks.py` (`buyer_stock_problem`); `transactions/presenters.py` (`stock_limit_problem`, buyer only); `transactions/migrations/0002_rls_and_append_only.py` (party read policy); `core/home.py` (`_licensee`) | `test_transaction_service.py`, `test_transaction_decisions.py`, `test_transaction_api.py`, `test_buyer_stock_limit.py`, `test_login_api.py`, `test_users.py::test_has_role`, `test_enrolment.py`, `test_licence_api.py`, `test_licensing.py::test_holder_sees_only_their_own_licences`, `test_stock.py::test_holder_sees_only_own_stock`, `test_stock.py::test_my_stock_api`, `test_transaction_rules.py::test_transaction_visibility`, `test_d3_apis.py::test_check_endpoint_hides_buyer_stock`, `test_home_api.py::test_licensee_counts` |
| **Authorised Personnel** | Log in. They hold positions (e.g. Area Officer for a taluka); authority is positional, so a transfer moves the position to the new person immediately. As the designated officer (the current holder of the seller area's Area Officer position) approves or rejects with a one-time code; on approval stock moves from seller to buyer. Above the approval threshold (the two-step chain) the officer instead recommends or rejects; a recommendation re-runs every check but moves no stock, and the current holder of the transaction's superintendent position then gives the final approval (stock moves) or rejects with an officer-kind reason. A superintendent's approval is enough: an officer who also holds the transaction's superintendent position is offered APPROVE or REJECT at the officer step, and their APPROVE signs both levels with one code (an OFFICER RECOMMEND and a SUPERINTENDENT APPROVE decision, stock moves, `transaction.approved` with `{"both_levels": true}`); their REJECT is an ordinary officer rejection. An officer who recommended and is then given the district position gives the final approval themselves. Reads transactions where they currently hold the designated or superintendent position (officer view includes comments and who held the officer and superintendent positions at each decision). The superintendent reads transactions whose stored superintendent position they currently hold (every transaction has one); reads the oversight batches of the district position they currently hold and reviews them: flags a transaction in their batch (the flag alerts the approving officer's position) and signs off the batch with a one-time code. Items the superintendent gave final approval to (two-step chain, including a dual holder's one-step approval) are marked `approved_by_superintendent` and cannot be flagged ("You approved this transaction; the Head Authority reviews it.", 403 over HTTP); no flag or alert is created. Sees and acknowledges alerts addressed to the positions they currently hold (buyer rejections on their transactions, and superintendent-flag alerts on transactions they approved); after a transfer the alerts follow the position. Home screen counts: awaiting their decision, unacknowledged alerts of held positions, open and overdue batches and the next due date. A district superintendent (holding any DISTRICT-level position) may draft rule-change proposals (justification of 10 to 1000 characters) and withdraw their own while submitted; they see only their own proposals. Taluka-only officers can neither draft nor see proposals. A district superintendent's home screen also counts `your_open_rule_changes` (their own SUBMITTED proposals). | `identity/roles.py` (`Role.PERSONNEL`); `governance/service.py` (`may_draft`, `draft`, `withdraw`); `governance/migrations/0002_rls_and_guards.py` (drafter read policy); `positions/` (only Personnel can be assigned); `transactions/service.py` (`decision_role`, `allowed_outcomes`, `decide`, `final_approval`); `transactions/migrations/0002_rls_and_append_only.py` (position-holder read policy); `alerts/service.py` (`acknowledge`); `alerts/migrations/0002_rls_and_append_only.py` (position-holder read policy); `oversight/service.py` (`flag_item`, `sign_off`); `oversight/migrations/0002_rls_and_append_only.py` (batch read policy); `oversight/migrations/0003_flags_and_sign_offs.py` (flag and sign-off read policy); `core/home.py` (`_personnel`) | `test_oversight_batches.py::test_only_the_superintendent_and_authorities_see_batches`, `test_oversight_review.py`, `test_home_api.py::test_personnel_awaiting_includes_promoted_recommender`, `test_home_api.py::test_personnel_alerts_and_batches`, `test_permissions.py`, `test_positions.py`, `test_transaction_decisions.py`, `test_two_step_approval.py`, `test_transaction_api.py`, `test_transaction_rules.py::test_transaction_visibility`, `test_alerts.py`, `test_governance.py`, `test_governance_api.py` |
| **Licensing Authority** | Log in. Proposes catalogue changes (new licence types, rule versions, approval thresholds that decide when the superintendent gives final approval) through rule-change proposals; from D2d no role changes the catalogue directly, only an approved proposal reaches it (ruling D-R12; screens arrive in D3). Records licences issued by the existing process, records renewals, suspends or revokes (row-level security lets only this role and SYSTEM write licences). Sets superintendent review periods (15, 30 or 60 days); it is the only role that may change them (`PUT /api/oversight/review-settings/<position_id>` with `{period_days, starts_on?}`: 404 for an unknown position, 422 `{"detail": "This review period can't be saved.", "reasons": [..]}`, 200 with the position's overview row); reads every district position's period, start, current period end and last batch end (`GET /api/oversight/review-settings`); the screen comes in D3. Reads the latest approval thresholds (`GET /api/catalogue/approval-thresholds`). Home screen counts: active licences expiring within 30 days and district positions without a review period. Does not read stock (DPDP data minimisation). Drafts rule-change proposals (new licence type, rule version, approval threshold; a Head Authority officer decides them, and only an approved change reaches the catalogue), withdraws their own while submitted, and reads all proposals (`/api/rule-changes`; sees the drafter's role, not their user id). Home screen also counts `your_open_rule_changes` (own SUBMITTED) and `rule_changes_submitted` (all SUBMITTED). Uses the licence register (`GET /api/licences`, exact `?number=`/`?gstin=` search, `?status=`, `?area=`, `?page=`; `GET /api/licences/<id>` with GSTIN, periods and permissions, never contact or stock); searches and detail views are audited as `licence.register_search` (blind index and result count) and `licence.viewed`. | `identity/roles.py` (`Role.LICENSING_AUTHORITY`); `catalogue/`; `governance/service.py` (`may_draft`, `draft`, `withdraw`); `governance/migrations/0002_rls_and_guards.py` (authority read policy); `core/home.py` (`_licensing_authority`); `licensing/register.py`, `licensing/views.py` (`LicenceRegisterView`, `LicenceDetailView`); `oversight/views.py` (`ReviewSettingsView`, `ReviewSettingChangeView`), `oversight/service.py` (`set_review_period`, `review_settings_overview`); `licensing/service.py`, `licensing/migrations/0002_rls_and_append_only.py`; `stock/migrations/0003_stock_readers_without_la.py` (no stock read) | `test_permissions.py`, `test_review_settings_api.py`, `test_catalogue.py`, `test_thresholds.py`, `test_licensing.py`, `test_stock.py::test_licensing_authority_cannot_read_stock`, `test_home_api.py::test_licensing_authority_counts`, `test_home_api.py::test_rule_change_counts`, `test_governance.py`, `test_governance_api.py`, `test_licence_register.py` |
| **Software Owner** | Log in; read the whole audit log; read all licences with their periods and snapshots; read all stock; create or reset personnel accounts (the API comes in Phase 4); reads all transactions, all alerts and all oversight batches; reads the approval thresholds; reads all rule-change proposals (cannot draft them), with the drafter's user id (ruling D-R2); home screen counts: all unacknowledged alerts and all transactions awaiting a superintendent. Uses the licence register (`GET /api/licences`, exact `?number=`/`?gstin=` search, `?status=`, `?area=`, `?page=`; `GET /api/licences/<id>` with GSTIN, periods and permissions, never contact or stock); searches and detail views are audited as `licence.register_search` (blind index and result count) and `licence.viewed`. Reads the review settings (`GET /api/oversight/review-settings`) but cannot change them (403). | `identity/roles.py` (`AUDIT_READERS`, `PERSONNEL_PROVISIONERS`); `oversight/views.py` (`ReviewSettingsView`); `licensing/register.py`, `licensing/views.py` (`LicenceRegisterView`, `LicenceDetailView`); `governance/migrations/0002_rls_and_guards.py` (authority read policy); `governance/presenters.py` (`proposal_view`: `drafted_by`); `core/home.py` (`_oversight`); `audit/migrations/0002_protect_and_rls.py` (read policy); `licensing/migrations/0002_rls_and_append_only.py` (licence read policy); `create_software_owner` command (first account only); `transactions/migrations/0002_rls_and_append_only.py` (authority read policy); `alerts/migrations/0002_rls_and_append_only.py` (authority read policy); `oversight/migrations/0002_rls_and_append_only.py` (authority read policy) | `test_audit.py::test_only_audit_readers_can_read_events`, `test_create_software_owner.py`, `test_transaction_rules.py::test_transaction_visibility`, `test_alerts.py::test_only_position_holders_and_authorities_see_alerts`, `test_oversight_batches.py::test_only_the_superintendent_and_authorities_see_batches`, `test_home_api.py::test_head_authority_and_owner_counts`, `test_governance.py::test_visibility`, `test_licence_register.py`, `test_review_settings_api.py::test_only_licensing_authority_can_change` |
| **Head Authority** | Log in; read the whole audit log (oversight); read all licences with their periods and snapshots; read all stock; create or reset personnel accounts (Phase 4); reads all transactions, all alerts and all oversight batches, including the items a superintendent gave final approval to (the superintendent cannot flag those; the Head Authority reviews them); reads the approval thresholds; drafts rule-change proposals and withdraws their own while submitted, and reads all proposals; approves or rejects a proposal they did not draft with a one-time code (`request_decision_code`, `decide`; a rejection needs a note of 10 to 500 characters; an approval applies the change to the catalogue in the same SYSTEM block, all or nothing; their own proposal is refused with "You drafted this change, so another Head Authority officer must decide it." at the code request and again when deciding, before and under the lock); over HTTP `/api/rule-changes/<id>/decision-code` and `/decide`, and sees the drafter's user id (ruling D-R2); home screen counts: all unacknowledged alerts, all transactions awaiting a superintendent, `rule_changes_awaiting_you` (SUBMITTED, not drafted by them) and `your_open_rule_changes` (own SUBMITTED). Uses the licence register (`GET /api/licences`, exact `?number=`/`?gstin=` search, `?status=`, `?area=`, `?page=`; `GET /api/licences/<id>` with GSTIN, periods and permissions, never contact or stock); searches and detail views are audited as `licence.register_search` (blind index and result count) and `licence.viewed`. Reads the review settings (`GET /api/oversight/review-settings`) but cannot change them (403). | Same as Software Owner, plus `governance/service.py` (`may_draft`, `draft`, `withdraw`, `request_decision_code`, `decide`, `apply_change`); `governance/views.py`; `core/home.py` (`_head_rule_changes`); `licensing/migrations/0002_rls_and_append_only.py`; `transactions/migrations/0002_rls_and_append_only.py` (authority read policy); `alerts/migrations/0002_rls_and_append_only.py` (authority read policy); `oversight/migrations/0002_rls_and_append_only.py` (authority read policy) | `test_audit.py::test_only_audit_readers_can_read_events`, `test_transaction_rules.py::test_transaction_visibility`, `test_alerts.py::test_only_position_holders_and_authorities_see_alerts`, `test_oversight_batches.py::test_only_the_superintendent_and_authorities_see_batches`, `test_home_api.py::test_head_authority_and_owner_counts`, `test_home_api.py::test_rule_change_counts`, `test_governance.py`, `test_governance_decisions.py`, `test_governance_api.py`, `test_licence_register.py`, `test_review_settings_api.py::test_only_licensing_authority_can_change` |
| **SYSTEM** (background jobs, never a person) | Read the audit log to verify the chain; read and record licences (enrolment matching, seeding); the only writer of stock balances and movements; the only writer of transactions, decisions, alerts, acknowledgements, oversight batches, batch items, flags and sign-offs, and rule-change proposals. | `core/db_context.py` (`SYSTEM_ROLE`, `acting_as_system`), `verify_audit_chain` command, `licensing/migrations/0002_rls_and_append_only.py`, `stock/migrations/0002_rls_and_append_only.py`; `transactions/migrations/0002_rls_and_append_only.py` (SYSTEM-only write policies), `alerts/migrations/0002_rls_and_append_only.py` (SYSTEM-only write, append-only alerts and acknowledgements), `oversight/migrations/0002_rls_and_append_only.py` (SYSTEM-only write, append-only batches and items), `oversight/migrations/0003_flags_and_sign_offs.py` (SYSTEM-only write, append-only flags and sign-offs), `governance/migrations/0002_rls_and_guards.py` (SYSTEM-only write, decision columns only, decided rows final) | `test_audit.py::test_verify_command_*`, `test_stock.py::test_only_system_can_write_stock`, `test_transaction_rules.py::test_only_system_writes_and_only_status_changes`, `test_alerts.py::test_only_position_holders_and_authorities_see_alerts`, `test_alerts.py::test_alerts_and_acknowledgements_are_append_only_even_for_owner`, `test_oversight_batches.py::test_only_the_superintendent_and_authorities_see_batches`, `test_oversight_batches.py::test_batches_are_append_only_even_for_owner`, `test_governance.py::test_only_system_writes_proposals` |
| **Any logged-in user** (all roles) | Read the substance list (`GET /api/catalogue/substances`); list reason codes (`GET /api/reason-codes?kind=`); read the latest approval thresholds (`GET /api/catalogue/approval-thresholds`); read licence types with the latest version of each rule (`GET /api/catalogue/licence-types`) and substance classes (`GET /api/catalogue/classes`); list and open the rule-change proposals row-level security lets them see (`GET /api/rule-changes?status=`, `GET /api/rule-changes/<id>`, 404 when not visible; drafting, withdrawing and deciding stay limited as above); read who they are (`GET /api/auth/me`: role, display name, held positions); read their home-screen counts (`GET /api/home`, per role, under their own RLS); list transactions filtered by `awaiting=me`, `side=sales\|purchases` and `approved_by=superintendent` (AND; any other value 400) | `licensing/views.py` (`SubstanceListView`); `reasons/views.py` (`ReasonCodeListView`); `catalogue/views.py` (`ApprovalThresholdListView`, `LicenceTypeListView`, `SubstanceClassListView`); `governance/views.py` (`ProposalListView`, `ProposalDetailView`); `identity/views.py` (`MeView`); `core/home.py` (`home_counts`), `core/views.py` (`HomeView`); `transactions/service.py` (`awaiting_decision_for`, `filter_transactions`) | `test_licence_api.py::test_substance_list_for_logged_in_users`, `test_reasons.py::test_reason_code_api_lists_active_codes`, `test_d3_apis.py`, `test_home_api.py`, `test_catalogue_api.py`, `test_governance_api.py` |
| **Anonymous** (not logged in) | Only the health check, the CSRF cookie, the two login steps and the two enrolment steps (start, complete) | `settings.REST_FRAMEWORK` (deny by default), `AllowAny` on those views only; `licensing/views.py` | `test_login_api.py`, `test_enrolment.py`, `test_permissions.py::test_anonymous_is_refused`, `test_audit.py::test_anonymous_context_cannot_read_events` |

To restrict a new API endpoint to certain roles, use `permission_classes = [role_required(Role.X, ...)]` from `identity/permissions.py`.

Every app's `apps.py` only registers the app (its `AppConfig`), so section 2 does not list them.

---

## 2. Code responsibility map

Paths are relative to `backend/`, except in the **frontend** section (relative to `frontend/`).

### config: settings and startup

| File | Responsible for | Key names | Tests |
|---|---|---|---|
| `config/env.py` | Reading environment variables; stops at startup if a required one is missing | `required`, `optional`, `flag`, `listed`, `MissingSetting` | `test_env.py` |
| `config/settings.py` | All settings: database, security headers, sessions (15-minute idle timeout), rate limits (`login`, `otp`, `enrolment` 10/min, `lookup` 30/min, `NUM_PROXIES: 0`), encryption keys, OTP sender, exception handler | `REST_FRAMEWORK`, `CACHES`, `MIDDLEWARE` | Covered indirectly by all API tests; `check --deploy` in CI |
| `config/urls.py` | URL routing: `/api/health`, `/api/auth/*`, and the licensing routes under `/api/` (`enrolment/start`, `enrolment/complete`, `licences` (register), `licences/mine`, `licences/<int:id>` (register detail; `mine` is matched first), `catalogue/substances`), the stock route, the transaction routes (`transactions`, `transactions/buyer-lookup`, `transactions/<ref>`, `.../decision-code`, `.../decide`, `.../cancel`), and the alert routes (`alerts`, `alerts/<id>/acknowledge`), and the oversight routes (`oversight/batches`, `oversight/batches/<id>`, `.../flag`, `.../sign-off-code`, `.../sign-off`, `oversight/review-settings`, `oversight/review-settings/<position_id>`); `/api/home`; the catalogue read routes (`catalogue/approval-thresholds`, `catalogue/licence-types`, `catalogue/classes`); `transactions/check`; the rule-change routes (`rule-changes`, `rule-changes/<id>`, `.../withdraw`, `.../decision-code`, `.../decide`) | — | `test_health.py`, `test_login_api.py`, `test_enrolment.py`, `test_licence_api.py`, `test_stock.py::test_my_stock_api`, `test_transaction_api.py`, `test_alerts_api.py`, `test_home_api.py`, `test_d3_apis.py`, `test_catalogue_api.py`, `test_governance_api.py`, `test_licence_register.py`, `test_review_settings_api.py` |
| `config/wsgi.py` | The WSGI entry point the production server loads (`config.settings`) | `application` | `check --deploy` in CI |
| `.env.test` | Test-only settings (never real secrets) | — | — |

### core: shared building blocks

| File | Responsible for | Key names | Tests |
|---|---|---|---|
| `core/views.py` | Health check (also confirms the database is reachable); `GET /api/home` for any logged-in user: `{"role", "counts"}` from `home_counts` with today's local date | `health`, `HomeView` | `test_health.py`, `test_home_api.py` |
| `core/home.py` | The counts each role's home screen shows, all read under the caller's own RLS (no SYSTEM). Licensee: `awaiting_your_decision` (`awaiting_decision_for`), `sales_in_progress` (they sell, any AWAITING_* status). Personnel: `awaiting_your_decision` (same queryset as `?awaiting=me`, including transactions they recommended and now hold the superintendent position for), `unacknowledged_alerts`, `open_batches`, `overdue_batches` (`batch_status` over batches of held positions) and `next_due` (earliest due date of an OPEN batch, ISO, or null). Licensing Authority: `expiring_licences_30d` (ACTIVE licences whose latest validity period ends between today and today + 30), `districts_without_review_period` (DISTRICT positions with no `SuperintendentSetting`), `your_open_rule_changes` (own SUBMITTED proposals) and `rule_changes_submitted` (all SUBMITTED). Head Authority and Software Owner: `unacknowledged_alerts` (all) and `awaiting_superintendent` (all); the Head Authority also gets `rule_changes_awaiting_you` (SUBMITTED, not drafted by them) and `your_open_rule_changes`. Personnel get `your_open_rule_changes` only when they may draft (`may_draft`: a district position) | `home_counts`, `IN_PROGRESS`, `EXPIRY_WINDOW` | `test_home_api.py` |
| `core/crypto.py` | Encrypting sensitive fields; one-way lookup keys (blind indexes) for exact-match lookup only | `encrypt`, `decrypt`, `blind_index(context, value)`, `DecryptionError` | `test_crypto.py` |
| `core/db_context.py` | Telling Postgres who is acting, so row-level security can check it; the setting lasts only for the current transaction | `set_actor`, `current_actor`, `SYSTEM_ROLE`, `acting_as_system(job)` (brief SYSTEM block in its own savepoint: restores the previous actor on normal exit, and any error rolls back to the savepoint so the actor reverts too; writes inside are all-or-nothing; writes no audit event itself, so every caller audits its cross-owner action; outside a transaction it opens its own short one) | `test_db_context.py`, `test_licensing.py::test_acting_as_system_restores_previous_actor`, `test_licensing.py::test_acting_as_system_does_not_mask_database_errors`, `test_licensing.py::test_acting_as_system_restores_actor_after_caught_nested_error` |
| `core/middleware.py` | One database transaction per request, tagged with the user; a 5xx response rolls back | `DbContextMiddleware` | `test_db_context.py` |
| `core/exceptions.py` | A raised API error undoes the request's writes (**raise to roll back, return to commit**) | `rollback_on_exception` | `test_rollback_on_exception.py` |
| `core/migrations/0002_append_only_guard.py` | Shared trigger function `reject_append_only_change()`; append-only tables attach it (row trigger for update/delete, statement trigger for truncate); used by rule versions, approval threshold versions, licence validity periods and permission snapshots | `reject_append_only_change` | `test_catalogue.py::test_rule_versions_blocked_even_for_table_owner`, `test_thresholds.py::test_threshold_versions_are_append_only_even_for_owner`, `test_licensing.py::test_periods_and_snapshots_blocked_even_for_table_owner` |
| `core/migrations/0001_app_role_privileges.py` | The app role `gj_app` gets data access only: no schema changes, no ownership | — | `test_db_privileges.py` |

### identity: accounts, roles, one-time codes, login

| File | Responsible for | Key names | Tests |
|---|---|---|---|
| `identity/roles.py` | The six fixed roles and role groups | `Role`, `AUDIT_READERS`, `PERSONNEL_PROVISIONERS` | `test_users.py`, `test_permissions.py`, `test_audit.py` |
| `identity/models.py` | User accounts (system-generated ID, `licensee_gstin_index` linking a licensee to their licences, Argon2 password, encrypted contact, lockout fields; at most one account per non-empty `licensee_gstin_index`) and one-time-code records (for a user or, before an account exists, a subject such as `"licence:<id>"`; at most one open code per user, or per subject, and purpose) | `User`, `UserManager.create_user`, `generate_user_id`, `OtpChallenge`, `OtpPurpose` (`LOGIN`, `ENROL`, `DECISION` for signing a transaction decision) | `test_users.py`, `test_otp.py`, `test_otp_subject.py` |
| `identity/migrations/0001_initial.py` | Creates the user table; the database accepts only the six roles (`user_role_valid`) | — | `test_users.py::test_database_rejects_unknown_role` |
| `identity/migrations/0003_otpchallenge.py` | Creates the one-time-code table | — | `test_otp.py` |
| `identity/migrations/0004_otp_one_open_per_user.py` | Partial unique constraint: one open code per user and purpose | — | `test_otp.py::test_database_allows_one_open_challenge_per_user_and_purpose` |
| `identity/migrations/0005_otp_subject.py` | Adds `subject` (codes before an account exists, e.g. enrolment); a code belongs to exactly one of a user or a subject (`otp_user_xor_subject`) | — | `test_otp_subject.py::test_database_requires_exactly_one_of_user_or_subject` |
| `identity/migrations/0006_otp_one_open_per_subject.py` | Partial unique constraint: one open code per subject and purpose | — | `test_otp_subject.py::test_database_allows_one_open_challenge_per_subject_and_purpose` |
| `identity/migrations/0009_otp_purpose_decision.py` | Adds the `DECISION` purpose (signing a transaction decision or a batch sign-off) | — | `test_transaction_decisions.py::test_decision_code_is_bound_to_the_user`, `test_oversight_review.py::test_sign_off_with_code` |
| `identity/migrations/0008_one_account_per_licensee_gstin.py` | Partial unique constraint: one account per non-empty licensee GSTIN | — | `test_enrolment.py::test_database_allows_one_account_per_gstin` |
| `identity/migrations/0007_user_licensee_gstin_index.py` | Adds the indexed `licensee_gstin_index` column | — | `test_licensing.py::test_holder_sees_only_their_own_licences` |
| `identity/migrations/0002_protect_users.py` | Accounts can't be deleted, only deactivated | — | `test_users.py::test_app_role_cannot_delete_users` |
| `identity/otp.py` | Issuing and checking 6-digit codes: stored as HMAC, 5-minute expiry, 5 attempts, single use, a new code cancels the old one, issuing locks the user row (subjects: a per-subject advisory lock); checking locks the user row first, then the challenge (same order as login, so no deadlock); also codes for subjects with no account yet (enrolment) | `issue`, `verify`, `issue_for_subject`, `verify_subject`, `OTP_TTL`, `OTP_MAX_ATTEMPTS` | `test_otp.py`, `test_otp_subject.py` |
| `identity/otp_delivery.py` | How codes are sent: console in development (refuses unless DEBUG), in-memory outbox in tests, real provider later | `get_sender`, `ConsoleOtpSender`, `OutboxOtpSender` | `test_otp.py` |
| `identity/login.py` | Login step 1: password check on every path (timing is the same whether or not the account exists), lockout after 5 wrong passwords or 5 code requests in 15 minutes, locking cancels open codes | `start_login`, `LOCKOUT_THRESHOLD`, `LOCKOUT_DURATION` | `test_login_api.py` |
| `identity/serializers.py` | Validating login input | `LoginSerializer`, `OtpVerifySerializer` | `test_login_api.py` |
| `identity/views.py`, `identity/urls.py` | Login API: csrf, login, login/verify, logout, me. `me` adds `display_name` (Licensee: holder name of their first licence by id, read under their own RLS; Personnel: held position titles joined with ", ", or "Unassigned officer"; other roles: the role's label) and `positions` (`id`, `title`, `level`, ordered by id) | `CsrfView`, `LoginStartView`, `LoginVerifyView`, `LogoutView`, `MeView` | `test_login_api.py`, `test_d3_apis.py::test_me_has_display_name_and_positions` |
| `identity/permissions.py` | Restricting an endpoint to certain roles | `role_required` | `test_permissions.py` |
| `identity/management/commands/create_software_owner.py` | Creating the very first Software Owner (run once, interactive) | — | `test_create_software_owner.py` |

### catalogue: substances, licence types, versioned rules

| File | Responsible for | Key names | Tests |
|---|---|---|---|
| `catalogue/models.py` | What can be traded and what each licence type may do with it: substance classes, substances (each with a unit), licence types, rules (scoped to exactly one substance or one class) and rule versions (buy/sell/transport, stock and per-transaction limits, validity); approval thresholds (scoped to exactly one substance or one class, at most one per scope) and their versions (the quantity above which the superintendent gives final approval) | `Unit`, `SubstanceClass`, `Substance`, `LicenceType`, `LicenceTypeRule`, `LicenceTypeRuleVersion`, `ApprovalThreshold`, `ApprovalThresholdVersion` | `test_catalogue.py`, `test_thresholds.py` |
| `catalogue/service.py` | Finding the governing rule (substance rule beats class rule; none means not permitted), listing a licence type's substance-specific overrides within a class (latest versions), adding a new licence type (`add_licence_type`: refuses a taken code with `LicenceTypeExists`, "A licence type with code {code} already exists.", also when a concurrent insert wins the unique constraint; the exception carries `.code`; no `created_by` argument, the decision records who applied it; called only from the governance apply path, which builds the `ProposalInvalid` reason from `.code`, never from exception text) and adding a new rule version; finding the governing approval threshold (substance beats class; none means officer alone), adding a threshold version (locks the threshold row), the latest version of a threshold and of a rule (`latest_rule_version`), a class's unit (`class_unit`: from any of its substances, None while it has none), and the approval chain for a substance and quantity (two-step only above the threshold) | `resolve_rule`, `latest_rule_version`, `class_unit`, `substance_overrides`, `add_licence_type`, `LicenceTypeExists`, `add_rule_version`, `resolve_threshold`, `latest_threshold`, `add_threshold_version`, `approval_chain_for` | `test_catalogue.py`, `test_thresholds.py`, `test_governance_decisions.py` |
| `catalogue/views.py`, `catalogue/urls.py` | `GET /api/catalogue/approval-thresholds` (any logged-in user): each threshold's latest version as `scope`, `scope_kind` (substance or class), `superintendent_above_qty` (string), `unit` (a class takes it from any of its substances, since a class shares one unit) and `version`, ordered by id. `GET /api/catalogue/licence-types` (any logged-in user): every licence type by code with `code`, `name`, `description` and `rules` (latest version of each rule that has one: `scope`, `scope_code`, `scope_kind`, `unit`, `version`, may buy/sell/transport, limits as strings, `validity_months`). `GET /api/catalogue/classes`: `[{code, name, unit}]` by code. `scope_of` gives a rule's or threshold's scope fields | `ApprovalThresholdListView`, `LicenceTypeListView`, `SubstanceClassListView`, `scope_of` | `test_d3_apis.py::test_thresholds_api`, `test_catalogue_api.py` |
| `catalogue/migrations/0001_initial.py` | Creates substance classes, substances, licence types, rules and rule versions; a rule has exactly one scope and is unique per type and scope; limits must be positive | — | `test_catalogue.py::test_rule_needs_exactly_one_scope`, `test_catalogue.py::test_limits_must_be_positive` |
| `catalogue/migrations/0003_rule_version_trigger.py` | Rule versions also blocked by trigger for the table owner | — | `test_catalogue.py::test_rule_versions_blocked_even_for_table_owner` |
| `catalogue/migrations/0004_rule_validity_positive.py` | Validity must be above zero | — | `test_catalogue.py::test_validity_must_be_positive` |
| `catalogue/migrations/0002_append_only_versions.py` | Rule versions can't be updated or deleted by the app role: a change is a new version | — | `test_catalogue.py::test_rule_versions_cannot_be_edited` |
| `catalogue/migrations/0005_approval_thresholds.py` | Creates approval thresholds and their versions (no row-level security, ruling D-R12); versions are append-only (REVOKE from the app role plus `reject_append_only_change()` triggers) | — | `test_thresholds.py` |

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
| `licensing/migrations/0001_initial.py` | Creates the three licence tables and their constraints (exactly one scope, period ends after start) | — | `test_licensing.py` |
| `licensing/models.py` | Licences as issued by the existing process (number and GSTIN encrypted with blind indexes, holder, type, one substance or one class, area, status limited to the known values), append-only validity periods, and append-only permission snapshots taken in sets (a base row for the licence's scope plus, for a class licence, one override row per substance-specific rule in that class) | `LicenceStatus`, `Licence`, `LicenceValidityPeriod`, `LicencePermissionsSnapshot` | `test_licensing.py` |
| `licensing/service.py` | Recording a licence or renewal (atomic: licence, snapshot set, period and audit entry together or not at all; refused if no rule allows it), suspend/revoke (unknown statuses refused), current permissions from the newest snapshot set (a substance override wins over the base row), may-this-licence-trade-on-a-date, substance coverage, exact-match lookup by number | `record_licence`, `record_renewal`, `set_status`, `current_permissions`, `current_period`, `trading_permitted`, `covers`, `find_by_number`, `LicenceNotPermitted`, `InvalidLicenceData` | `test_licensing.py` |
| `licensing/migrations/0002_rls_and_append_only.py` | Row-level security (holder sees own by GSTIN; authority, Head, Software Owner, SYSTEM read all; only Licensing Authority and SYSTEM write); periods and snapshots append-only (REVOKE plus triggers) | — | `test_licensing.py` |
| `licensing/migrations/0003_status_only_updates.py` | The app role may update only `status` on a licence (no moving a licence to another holder) | — | `test_licensing.py::test_only_status_can_change_on_a_licence` |
| `licensing/migrations/0004_snapshot_substance.py` | Adds nullable `substance` to permission snapshots (NULL = base row, set = frozen substance override) | — | `test_licensing.py::test_class_licence_freezes_substance_override` |
| `licensing/migrations/0005_licence_status_valid.py` | Check constraint: status must be ACTIVE, SUSPENDED or REVOKED | — | `test_licensing.py::test_unknown_status_is_rejected` |
| `licensing/enrolment.py` | Licence-gated enrolment: match licence number + GSTIN + active + not yet enrolled, send the code to the contact ON FILE (the code is bound to that exact licence id, not just the GSTIN), audit after the send, then create the Licensee account with contact and `licensee_gstin_index` taken only from that same licence; every failure looks the same and is audited | `start_enrolment`, `complete_enrolment` | `test_enrolment.py` |
| `licensing/serializers.py` | Validates enrolment input (weak password rejected with 400 before the code is consumed); presents a licence as the permissions card dict (base permissions of the licence's own scope; the register reuses its permission fields) | `EnrolmentStartSerializer`, `EnrolmentCompleteSerializer`, `licence_card` | `test_enrolment.py::test_weak_password_is_rejected_without_using_up_the_otp`, `test_licence_api.py::test_licensee_sees_own_licence_card` |
| `licensing/views.py` | Enrolment endpoints `POST /api/enrolment/start` and `/complete` (anonymous, CSRF-protected, throttled); `GET /api/licences/mine` (Licensee only, filtered by GSTIN and by row-level security); `GET /api/catalogue/substances` (any logged-in user); the licence register `GET /api/licences` and `GET /api/licences/<id>` (`role_required(LICENSING_AUTHORITY, HEAD_AUTHORITY, SOFTWARE_OWNER)`; `?page=` below 1, above `MAX_REGISTER_PAGE` (10**6, so a huge page cannot overflow the SQL OFFSET) or not a number, an unknown `?status=`, or an `?area=` that is not an existing area id gives 400 "Unknown filter value."; response `{count, page, page_size: 25, results}`, a page beyond the end is empty with the count; unknown id 404 "Licence not found.") | `EnrolmentStartView`, `EnrolmentCompleteView`, `ENROLMENT_FAILED`, `MyLicencesView`, `SubstanceListView`, `LicenceRegisterView`, `LicenceDetailView`, `UNKNOWN_FILTER`, `MAX_REGISTER_PAGE` | `test_enrolment.py`, `test_licence_api.py`, `test_licence_register.py` |
| `licensing/register.py` | The licence register for authorities (B7), under the caller's own row-level security (no SYSTEM). `search`: exact match on number and/or GSTIN through the blind index (case and surrounding spaces ignored, no partial match), optional status and exact area filters, 25 per page, oldest first; a search with a number or GSTIN is audited as `licence.register_search` with `number_index`/`gstin_index` and `results` (total matches), an unfiltered listing is not audited. Row: `id`, `licence_number`, `holder_name`, `licence_type`, `scope`, `area` (name), `status`, `valid_to` (latest period's end). `detail`: the row plus `gstin`, sorted `periods` and `permissions` (the `licence_card` permission fields), audited as `licence.viewed` (subject licence id). Never the contact or any stock figure; `record()` last | `search`, `detail`, `PAGE_SIZE` | `test_licence_register.py` |
| `licensing/urls.py` | Routes enrolment, my-licences, licence-register (`licences`, `licences/<int:licence_id>`; the int converter keeps `licences/mine` on its own view) and substance-list endpoints under `/api/` | `urlpatterns` | `test_enrolment.py`, `test_licence_register.py` |
| `tests/conftest.py` fixtures | `make_licence(...)` records a licence as SYSTEM with sensible defaults (area Sanand; valid 2026-01-01 to 2047-12-31 so tests never expire before 2047); `make_licensee(licence)` creates a Licensee linked to the licence's GSTIN; `trade` sets up a seller, a buyer, the Sanand officer, the district superintendent and 400 L of seller whisky; `settle(qty, buyer=, officer=, reason_code=, comment=)` drives a transaction through the real services (`officer=None` stops at awaiting officer); `set_decided_on(tx, day)` moves a decision to noon local on that day; `review_setting` sets a 15-day period from 2026-06-01 for the district officer position; `DEMO_GSTIN` and `BUYER_GSTIN` use a non-existent state code | `make_licence`, `make_licensee`, `trade`, `settle`, `set_decided_on`, `DEMO_GSTIN`, `BUYER_GSTIN` | — |
| `tests/test_api_contracts.py` | The API contracts the web app is built on (D3 Task 2). One case per contract drives a real endpoint as the right role with the synthetic fixtures; with `UPDATE_CONTRACTS=1` it writes the JSON (sorted keys, 2-space indent, trailing newline) to `frontend/src/test/contracts/<name>.json`, otherwise it compares the response's shape with the committed file (same keys; string, number, boolean, null, list by its first element, object; an empty list matches any list). Fixtures make every list non-empty and set nullable fields where they can (a flagged batch item, an OPEN batch dated from today so `next_due` is set) | `CASES`, `contract`, `shape`, `differences`, `open_batch` | itself; `frontend/src/api/contracts.test.ts` |

### reasons: configurable reason codes

Reference data with no row-level security (ruling D-R12, same as the catalogue): everyone logged in may read it.

| File | Responsible for | Key names | Tests |
|---|---|---|---|
| `reasons/models.py` | Reason codes in a table so admins can add new ones without a code change; unique per kind; kind checked by the database | `ReasonKind`, `ReasonCode` | `test_reasons.py` |
| `reasons/service.py` | Listing active codes of a kind; validating a chosen code (must exist, be active, be of that kind; "OTHER" needs text) | `active_reasons`, `resolve_reason`, `InvalidReason` | `test_reasons.py` |
| `reasons/views.py`, `reasons/urls.py` | `GET /api/reason-codes?kind=` for dropdowns (any logged-in user; 400 for unknown kind) | `ReasonCodeListView` | `test_reasons.py::test_reason_code_api_*` |
| `reasons/migrations/0001_initial.py` | Creates the reason code table and its constraints | — | `test_reasons.py` |
| `reasons/migrations/0002_seed_defaults.py` | Seeds the default codes per kind, each with an "OTHER" that requires text | `DEFAULTS` | `test_reasons.py::test_defaults_*` |
| `reasons/migrations/0003_stock_limit_reason.py` | Seeds the buyer reason `STOCK_LIMIT` ("This would take me over my licence's stock limit", sort order 50); reversing deletes only that row | — | `test_buyer_stock_limit.py::test_stock_limit_reason_is_seeded` |

### stock: balances and movements

Per business (GSTIN blind index) per substance. Only SYSTEM writes; holders read their own; Head Authority, Software Owner and SYSTEM read all.

| File | Responsible for | Key names | Tests |
|---|---|---|---|
| `stock/models.py` | Balance per business and substance (unique, never negative by database constraint); append-only movement history | `StockBalance`, `StockMovement`, `MovementReason` | `test_stock.py` |
| `stock/service.py` | Reading a balance; recording an opening balance once; moving stock between businesses in sorted lock order, refusing overdrafts and refusing to take the target above `max_target` (its licence's stock limit) | `balance_of`, `set_opening_balance`, `transfer`, `InsufficientStock`, `StockLimitExceeded` | `test_stock.py` |
| `stock/views.py`, `stock/urls.py` | `GET /api/stock/mine` (Licensee only) | `MyStockView` | `test_stock.py::test_my_stock_api` |
| `stock/migrations/0001_initial.py` | Creates balances (one per business and substance, never negative) and movements | — | `test_stock.py::test_database_never_allows_negative_stock` |
| `stock/migrations/0002_rls_and_append_only.py` | Row-level security (own-business read, SYSTEM-only write), balance updates limited to quantity and updated_at, movements append-only | — | `test_stock.py` |
| `stock/migrations/0003_stock_readers_without_la.py` | Recreates the stock read policies without the Licensing Authority: holders read their own business, Head Authority, Software Owner and SYSTEM read all (reversible) | — | `test_stock.py::test_licensing_authority_cannot_read_stock` |

### transactions: records, licence selection, checks, start, cancel, decisions and API

A seller-initiated sale of a substance to another business. Only SYSTEM writes (services check who may act first); parties, position holders and authorities read.

| File | Responsible for | Key names | Tests |
|---|---|---|---|
| `transactions/models.py` | The transaction (encrypted transporter details, designated and superintendent positions and the approval chain fixed at creation, status including waiting for and rejected by the superintendent) and its append-only decisions (steps include the superintendent; outcomes include recommend) | `Transaction`, `TransactionDecision`, `TransactionStatus`, `DecisionStep`, `DecisionOutcome`, `ApprovalChain`, `generate_reference` | `test_transaction_rules.py`, `test_thresholds.py::test_approval_chain_cannot_be_updated_by_app_role` |
| `transactions/selection.py` | Whether a licence is eligible (covers the substance, may trade on the day, permissions allow the action); choosing the licence a business uses: eligible, substance-specific licence preferred, then earliest | `licence_eligible`, `select_licence` | `test_transaction_rules.py` |
| `transactions/checks.py` | Plain-language problems: missing licence, per-transaction limits, seller stock; the buyer's stock cap (with the buyer's numbers, for authorities) only with `include_buyer_stock=True`. `buyer_stock_problem(tx)` is the buyer's own sentence when confirming would take them over their limit (callers run it as SYSTEM) | `fmt_qty`, `eligibility_problems`, `transaction_problems`, `buyer_stock_problem` | `test_transaction_rules.py`, `test_buyer_stock_limit.py` |
| `transactions/service.py` | The journey's first steps: buyer lookup by GSTIN (registered name only, audited by blind index), start (checks without the buyer's stock cap, licence selection, routing to the seller area's taluka and district positions, both required, encrypted transporter details), seller cancel while awaiting the buyer, one-time-code-signed buyer, officer and superintendent decisions (`request_decision_code`, `decide`). Start records the approval chain (`catalogue.service.approval_chain_for`). `allowed_outcomes` says what each role may decide: on the two-step chain the officer recommends (`_recheck` only, no stock moves, status `AWAITING_SUPERINTENDENT`, audited `transaction.recommended`) and the superintendent approves or rejects (`transaction.superintendent_rejected`). A superintendent's approval is enough: an officer who also holds the superintendent position (`_holds_both`) gets APPROVE/REJECT at the officer step (`_step_outcomes`), and `_apply` turns their APPROVE into both levels in one SYSTEM block (`both_levels`: `_approve` and stock move, status APPROVED, an OFFICER RECOMMEND row and a SUPERINTENDENT APPROVE row signed by the same code, one audit `transaction.approved` with payload `{"both_levels": true}`); a recommender later given the district position is offered the superintendent step like anyone holding it. `_apply` re-checks `decision_role` and `_step_outcomes` under the transaction lock (`NOT_AVAILABLE` if a position changed hands). The `_NEXT`, `_AUDIT` and `_STEP` tables map each (role, outcome) to its status, audit action and step; `decided_at` is set for every status outside `_WAITING`. Approval re-checks that both licences are still eligible today, the limits and stock, then moves stock re-checking the seller's stock and the buyer's cap under the balance locks; a refused approval rolls back and is audited (`transaction.approval_refused`). Officer recommend and every final approval check the buyer's cap (`include_buyer_stock=True`). Buyer stock limit: `allowed_outcomes` gives the buyer only REJECT while `stock_limit_problem` (SYSTEM read, `buyer_stock_check`) is set, but `decide` gates on `_step_outcomes` so a CONFIRM reaches `_apply`, is refused under the transaction lock (`TransactionRefused`, 422), rolls back and is audited `transaction.confirm_refused`. `_buyer_reason_code` (before the code is spent) defaults a blank buyer reason to `STOCK_LIMIT` while the problem exists and refuses `STOCK_LIMIT` (`NO_STOCK_PROBLEM`) otherwise; `_check_buyer_stock` repeats both under the lock; a `STOCK_LIMIT` refused there (`InvalidReason`, the buyer's stock changed after the code was requested) rolls back and is audited `transaction.reject_refused`. A `STOCK_LIMIT` rejection raises no alerts (payload `{"alerts_raised": 0}`). Reads run under the caller's own RLS. Writes run in `acting_as_system` after a plain-Python who-may-act check. A buyer rejection raises alerts (`alerts.service`) after the decision row and before the audit record, whose payload is `{"alerts_raised": n}`. `check_transaction` (B4) is a dry run of start: the same self-sale check, licence selection and `_refusals` (without the buyer's stock cap) plus `_route` (its refusals included); it returns the reasons and, when there are none, the approval chain, and writes nothing but the audit record `transaction.checked` (payload `gstin_index` and `ok`, never the GSTIN), all inside one SYSTEM block (`check_transaction` job). `awaiting_decision_for(user)` is the queryset of transactions where `decision_role` is not None (buyer AWAITING_BUYER, including one over their stock limit; AWAITING_OFFICER for a held designated position; AWAITING_SUPERINTENDENT for a held superintendent position), read under the caller's RLS; it backs both `?awaiting=me` and the home count. `filter_transactions` applies the list filters with AND (`approved_by=superintendent` means a SUPERINTENDENT APPROVE decision). `final_approval` returns the APPROVE decision (officer's on the OFFICER chain, superintendent's on the two-step chain), read as SYSTEM (`final_approval` job) so the caller's RLS cannot hide it. Lock order: user row, OTP challenge rows, transaction row, stock balance rows (sorted), alert inserts, audit last | `find_buyer`, `check_transaction`, `awaiting_decision_for`, `filter_transactions`, `SELF_SALE`, `final_approval`, `start_transaction`, `cancel_transaction`, `decision_role`, `allowed_outcomes`, `stock_limit_problem`, `request_decision_code`, `decide`, `NOT_AVAILABLE`, `STOCK_LIMIT`, `NO_STOCK_PROBLEM`, `load_visible`, `Transport`, `TransactionRefused`, `NotAllowed`, `NO_OFFICER`, `NO_SUPERINTENDENT` | `test_transaction_service.py`, `test_transaction_decisions.py`, `test_two_step_approval.py`, `test_buyer_stock_limit.py`, `test_alerts.py::test_buyer_rejection_audit_counts_alerts_raised`, `test_d3_apis.py`, `test_home_api.py` |
| `transactions/presenters.py` | What each viewer sees: summary and detail (transport, designated officer, approval chain and its label, status timeline, next action ("Your decision is needed." exactly when `decision_role` is not None, so a holder who made the officer decision is told to wait like anyone else; otherwise the status's waiting message), `can_decide`, `allowed_outcomes` sorted and empty unless it is the viewer's turn, `stock_limit_problem` set only for the buyer while the sale waits for them, read as SYSTEM, otherwise None). Party names read as SYSTEM, registered name only; buyer and officer comments and the holder of the officer and superintendent positions at each decision (`held_by`) shown to authority viewers (officer, superintendent, head authority, software owner) only | `transaction_summary`, `transaction_detail` | `test_transaction_api.py`, `test_two_step_approval.py`, `test_buyer_stock_limit.py` |
| `transactions/serializers.py` | Input validation with fix-it messages (GSTIN, quantity above 0, vehicle number format, six-digit code, outcome including RECOMMEND); the pre-check input (the start input without the transport fields, which the start serializer extends); the list filters (`allow_blank`: blank means no filter, from a query string or plain data) | `BuyerLookupSerializer`, `CheckTransactionSerializer`, `NewTransactionSerializer`, `DecideSerializer`, `TransactionFilterSerializer` | `test_transaction_api.py::test_invalid_input_is_400`, `test_d3_apis.py::test_unknown_filter_is_400`, `test_d3_apis.py::test_filter_serializer_accepts_blanks_from_any_source` |
| `transactions/views.py`, `transactions/urls.py` | Thin HTTP layer: buyer lookup and pre-check `POST /api/transactions/check` (Licensee only, CSRF, `lookup` throttle; the check returns 200 `{"ok", "reasons", "approval_chain"}`, chain null when not ok), create and cancel (Licensee only), list (50 newest, with `awaiting`, `side` and `approved_by` filters; an unknown value is 400 "Unknown filter value.") and detail (any logged-in user; RLS scopes rows), decision code and decide (`otp` throttle). Refusals return 422 with reasons, wrong code 401, not allowed 403, unknown or invisible 404 | `BuyerLookupView`, `CheckView`, `TransactionListView`, `TransactionDetailView`, `DecisionCodeView`, `DecideView`, `CancelView` | `test_transaction_api.py`, `test_d3_apis.py` |
| `transactions/migrations/0001_initial.py` | Creates transactions and decisions; quantity must be positive, status must be known, seller and buyer must differ | — | `test_transaction_rules.py`, `test_transaction_service.py::test_cannot_sell_to_own_business` |
| `transactions/migrations/0002_rls_and_append_only.py` | Row-level security (party, position-holder and authority read; SYSTEM-only write), only status and decided_at updatable, decisions append-only | — | `test_transaction_rules.py` |
| `transactions/migrations/0003_superintendent_required.py` | `superintendent_position` becomes required | — | `test_transaction_service.py::test_district_without_superintendent_is_refused` |
| `transactions/migrations/0004_indexes.py` | Indexes for the seller pattern count, buyer lookups and the superintendent's batch queries | — | `test_alerts.py::test_pattern_counts_recent_rejections` |
| `transactions/migrations/0005_approval_chain.py` | Adds `approval_chain` (existing rows get OFFICER; check `transaction_chain_valid`), the new statuses (regenerated `transaction_status_valid`), and widens status, step and outcome; the app role's column grant stays `UPDATE (status, decided_at)`, so the chain can't be changed | — | `test_thresholds.py::test_approval_chain_cannot_be_updated_by_app_role` |

### alerts: buyer-rejection alerts for authorities

In-app alerts addressed to positions, not people: whoever currently holds the position sees and acknowledges them, including after a transfer. Only SYSTEM writes; position holders, Head Authority, Software Owner and SYSTEM read. Alerts and acknowledgements are append-only.

| File | Responsible for | Key names | Tests |
|---|---|---|---|
| `alerts/models.py` | An alert (kind, addressed position, transaction, reason, comment, pattern count) and its at-most-one acknowledgement | `AuthorityAlert`, `AlertAcknowledgement`, `AlertKind` | `test_alerts.py` |
| `alerts/service.py` | Raising alerts inside the decision's SYSTEM block (buyer rejection: one to the designated officer's position, one to the superintendent's, with the seller's 30-day buyer-rejection count, which excludes transactions with a BUYER `STOCK_LIMIT` decision via `~Exists`); acknowledging (the user must currently hold the position; once only, including when two requests race and the unique constraint fires; audited as `alert.acknowledged`); ordinal and pattern wording. A second acknowledgement raises `AlreadyAcknowledged` (a `NotAllowed`) in both places | `raise_buyer_rejection_alerts`, `raise_flag_alert`, `acknowledge`, `NotAllowed`, `AlreadyAcknowledged`, `PATTERN_WINDOW`, `ordinal`, `pattern_text` | `test_alerts.py`, `test_d3_apis.py::test_acknowledge_twice_is_409_with_message` |
| `alerts/presenters.py` | What an authority sees for an alert: kind, transaction reference, substance, quantity, registered party names (read as SYSTEM; never licence numbers, GSTINs or contacts), reason, comment, pattern wording (buyer rejections), acknowledgement details | `alert_view` | `test_alerts_api.py` |
| `alerts/serializers.py` | Input validation for acknowledge (optional note up to 500 characters; null or a non-object body is 400) | `AcknowledgeSerializer` | `test_alerts_api.py::test_acknowledge_rejects_bad_input`, `test_alerts_api.py::test_acknowledge_without_body_works` |
| `alerts/views.py`, `alerts/urls.py` | Thin HTTP layer: list (any logged-in user; RLS scopes rows to held positions; unacknowledged first, then newest, at most 100; the unacknowledged count is a true count, not capped) and acknowledge (validated by `AcknowledgeSerializer`, bad input 400; already acknowledged 409 "This alert is already acknowledged."; not the holder 403 "Only the officer holding this position can acknowledge this alert."; fixed messages, never `str(exc)`) | `AlertListView`, `AcknowledgeView`, `ALREADY_ACKNOWLEDGED`, `NOT_HOLDER` | `test_alerts_api.py`, `test_d3_apis.py` |
| `alerts/migrations/0001_initial.py` | Creates alerts and their at-most-one acknowledgement; the kind must be known (`alert_kind_valid`) | — | `test_alerts.py` |
| `alerts/migrations/0002_rls_and_append_only.py` | Row-level security (position-holder and authority read, SYSTEM-only write), append-only via REVOKE and triggers (reversible) | — | `test_alerts.py::test_only_position_holders_and_authorities_see_alerts`, `test_alerts.py::test_alerts_and_acknowledgements_are_append_only_even_for_owner` |

### oversight: superintendent review periods and batches

Each district superintendent position has a review period (15, 30 or 60 days). When a period has ended, SYSTEM creates a batch listing the approved transactions of that period. Batches and items are append-only; readable by the current holder of the position, Head Authority, Software Owner and SYSTEM. The superintendent flags transactions (one per transaction, alerting the approving officer) and signs the whole batch off with a one-time code; flags and sign-offs are append-only and written by SYSTEM only.

| File | Responsibility | Key names | Tests |
|---|---|---|---|
| `oversight/models.py` | The review setting (one per district position), batches (one per position and period start), batch items, flags and sign-offs; `REVIEW_PERIODS`, `SIGN_OFF_DAYS` (30) and `due_on()` | `SuperintendentSetting`, `OversightBatch`, `BatchItem`, `BatchFlag`, `BatchSignOff` | `test_oversight_batches.py`, `test_oversight_review.py` |
| `oversight/service.py` | Setting the review period (district positions only; lookups and write run as SYSTEM so the caller's RLS cannot hide batches; a change continues the day after the last batch, or keeps the existing start when no batch exists; a new setting starts no later than the earliest approval for the position (today if none); an explicit start that would skip or overlap days is refused; refusals raise `InvalidSetting` with a `reasons` list; audited as `oversight.review_period_set`). `review_settings_overview(today)`: every district position (by id) with its period, start, the end of the period containing today (null before the start or without a setting) and the last batch end; runs as SYSTEM because the Licensing Authority cannot read batches under RLS, and returns only dates (no audit event, since it is a read). `create_due_batches`: idempotent batch creation for every completed period (all batches and items first, then one `oversight.batch_created` audit each). Both take a job-level advisory lock (`_lock_batch_job`) so concurrent runs and period changes wait for each other. Review: only the position's current holder may flag or sign off (checked under the caller's RLS); a transaction the superintendent gave final approval to cannot be flagged (`OWN_APPROVAL`, refused before any write: no flag, alert or audit); a flag needs a superintendent-flag reason, is allowed once per transaction, raises an alert for the position of the final approval (`transactions.service.final_approval`) and is audited (`oversight.transaction_flagged`); sign-off uses a decision-purpose one-time code, a wrong code only counts the attempt and returns `None`, and a signed batch accepts no more flags or sign-offs (`oversight.batch_signed`); `batch_status` is SIGNED, OVERDUE (past the 30-day deadline) or OPEN. Writes run in `acting_as_system` under a per-batch advisory lock | `set_review_period`, `review_settings_overview`, `create_due_batches`, `InvalidSetting`, `flag_item`, `OWN_APPROVAL`, `request_sign_off_code`, `sign_off`, `batch_status`, `NotAllowed` | `test_oversight_batches.py`, `test_oversight_review.py`, `test_review_settings_api.py` |
| `oversight/management/commands/create_due_batches.py` | Daily job: `manage.py create_due_batches [--today YYYY-MM-DD]` runs `create_due_batches` as SYSTEM; a future `--today` is refused | `Command` | `test_oversight_batches.py::test_command_creates_due_batches`, `test_oversight_batches.py::test_command_refuses_a_future_today` |
| `oversight/migrations/0001_initial.py` | Creates review settings (period must be 15, 30 or 60), batches (one per position and period start, period ordered) and batch items (one per transaction in a batch) | — | `test_oversight_batches.py` |
| `oversight/migrations/0002_rls_and_append_only.py` | Row-level security (position-holder and authority read, SYSTEM-only write), append-only via REVOKE and triggers (reversible); the setting has no RLS | — | `test_oversight_batches.py::test_only_the_superintendent_and_authorities_see_batches`, `test_batches_are_append_only_even_for_owner` |
| `oversight/migrations/0003_flags_and_sign_offs.py` | Row-level security (position-holder and authority read, SYSTEM-only write) and append-only via REVOKE and triggers for batch flags and sign-offs (reversible) | — | `test_oversight_review.py::test_flags_and_sign_offs_are_append_only_even_for_owner` |
| `oversight/presenters.py` | Batch summary and detail for a superintendent or authority: period, due date, status, counts, items with substance, quantity, party names (read as SYSTEM; no licence numbers, GSTINs or contacts), approval time and approving position (from `final_approval`, read as SYSTEM), `approved_by_superintendent` (the final approval was the superintendent step), flag; `can_sign` | `batch_summary`, `batch_detail` | `test_oversight_api.py`, `test_oversight_review.py::test_superintendent_approved_items_are_marked` |
| `oversight/serializers.py` | Input validation for flag (reference, reason code, comment up to 500), sign-off (challenge id, six-digit code) and review period (integer `period_days`, optional date `starts_on`) | `FlagSerializer`, `SignOffSerializer`, `ReviewPeriodSerializer` | `test_oversight_api.py`, `test_review_settings_api.py::test_bad_types_are_400` |
| `oversight/views.py`, `oversight/urls.py` | Thin HTTP layer: list and detail (RLS scopes batches; 404 when not visible), flag (403 not allowed, including the superintendent's own approval, 400 bad reason), sign-off code and sign-off (OTP-throttled; a wrong code is returned as 401 so the attempt commits); review settings: GET for Licensing Authority, Head Authority and Software Owner, PUT for the Licensing Authority only (CSRF enforced; 400 bad types, 404 unknown position, 422 `InvalidSetting` with `exc.reasons`, 200 with the overview row) | `BatchListView`, `BatchDetailView`, `FlagView`, `SignOffCodeView`, `SignOffView`, `ReviewSettingsView`, `ReviewSettingChangeView` | `test_oversight_api.py`, `test_review_settings_api.py` |

### governance: maker-checker rule changes

An authority drafts a change to the catalogue (a new licence type, a rule version or an approval threshold) with a justification; a different Head Authority officer decides it with a one-time code, and only an approved change reaches the catalogue (applied in the decision's SYSTEM block, all or nothing). Proposals are written by SYSTEM through the service; readable by the drafter (own proposals), Head Authority, Software Owner, Licensing Authority and SYSTEM. A decided proposal (APPROVED, REJECTED or WITHDRAWN, all final) cannot change, even for the table owner, and no proposal can be deleted.

| File | Responsibility | Key names | Tests |
|---|---|---|---|
| `governance/models.py` | A proposal: kind, JSON payload, justification, drafter (user id and role), status (SUBMITTED, APPROVED, REJECTED, WITHDRAWN) and decision columns (`decided_by`, `decided_at`, `decision_note`, `applied_ref`); kind and status must be known (`proposal_kind_valid`, `proposal_status_valid`) | `RuleChangeProposal`, `ProposalKind`, `ProposalStatus` | `test_governance.py` |
| `governance/payloads.py` | One serializer per kind, used at draft and again at apply: NEW_LICENCE_TYPE (code `^[A-Z][A-Z0-9_]{1,31}$` not yet used, name up to 100, optional description up to 500), RULE_VERSION (existing licence type, exactly one existing substance or class, may buy/sell/transport, stock and per-transaction limits above 0 with per-transaction not above stock, validity 1 to 120 months), APPROVAL_THRESHOLD (exactly one existing substance or class, quantity above 0). Returns the cleaned payload with quantities as strings; otherwise raises `ProposalInvalid(reasons)` (whole-payload reasons as plain messages, field errors prefixed with the field's plain label from `FIELD_LABELS`, e.g. "Validity (months): ...") | `validate_payload`, `ProposalInvalid`, `PAYLOADS`, `FIELD_LABELS`, `ONE_SCOPE`, `PER_TRANSACTION_ABOVE_STOCK` | `test_governance.py::test_payload_validation_messages`, `test_payload_field_rules`, `test_payload_is_cleaned` |
| `governance/service.py` | Who may draft (`may_draft`: Licensing Authority, Head Authority, or personnel currently holding a DISTRICT-level position); drafting (drafter check, payload validation, justification of 10 to 1000 characters, insert as SYSTEM, `rule_change.drafted`); withdrawal (loaded under the caller's RLS, so an invisible proposal is `ProposalNotFound`; only the drafter; locked as SYSTEM and refused once decided; `rule_change.withdrawn`). Deciding (maker-checker): `request_decision_code` checks Head Authority (`NOT_HEAD`), not the drafter (`OWN_CHANGE`) and SUBMITTED (`ALREADY_DECIDED`) on the proposal read under the caller's RLS, then issues a DECISION code bound to the user. `decide` checks, before the code is spent, the outcome (APPROVE or REJECT), the note (`_clean_note`: REJECT needs 10 to 500 characters, `NOTE_REQUIRED`; any note at most 500) and the same decider rule, so a drafter holding a valid code from another proposal is refused and the code stays usable; a wrong code returns None (the attempt counts); a code signed by someone else is refused. Then one SYSTEM block (`_decide_locked`) locks the proposal, re-checks the decider rule, and on APPROVE calls `apply_change`, which re-validates the payload and applies it through `catalogue.service` (`add_licence_type`, a rule created if missing then `add_rule_version`, `add_threshold_version`), writes the catalogue audit (`catalogue.licence_type_added`, `catalogue.rule_version_added`, `catalogue.threshold_version_added`, payload `{"proposal_id", "<row>_id"}`) and returns `applied_ref` (`licence_type:<id>`, `rule_version:<id>`, `threshold_version:<id>`); the decision columns are set and `rule_change.approved` (`{"proposal_id", "kind", "applied_ref"}`) or `rule_change.rejected` is recorded last. A `ProposalInvalid` during apply (including `LicenceTypeExists` from a concurrent insert) rolls the block back, so the proposal stays SUBMITTED and no catalogue rows remain, then `rule_change.apply_failed` is recorded and the exception re-raised. Audit payloads never hold payload values, the justification or the note (ruling D-R3); `record()` is last. Each refusal is its own `NotAllowed` subclass with a fixed class `message` (`ProposalNotFound`, `NotADrafter`, `AlreadyDecided`, `NotTheDrafter`, `NotHead`, `OwnChange`, `UnknownOutcome`, `SomeoneElsesCode`), so the API maps them to statuses without echoing exception text. Lock order: user row → OTP challenge → proposal row → catalogue row (rule or threshold) → audit | `may_draft`, `draft`, `withdraw`, `request_decision_code`, `decide`, `apply_change`, `APPROVE`, `REJECT`, `NotAllowed` and its subclasses, `NOT_A_DRAFTER`, `NOT_THE_DRAFTER`, `ALREADY_DECIDED`, `NOT_HEAD`, `OWN_CHANGE`, `NOTE_REQUIRED` | `test_governance.py`, `test_governance_decisions.py` |
| `governance/presenters.py` | What a viewer sees of a proposal: `id`, `kind`, `kind_label`, `status`, `status_label`, `justification`, `drafted_at`, `drafted_by_role` (role label); `drafted_by` (user id) only for Head Authority and Software Owner viewers (ruling D-R2); `proposed` (cleaned payload plus resolved `licence_type_name`, `scope`, `scope_kind`, `unit`); `current` (the catalogue's latest rule version for the same type and scope, or latest threshold for the scope, or null; always null for a new licence type; read live, so it is null once the proposal is no longer SUBMITTED, since a decided proposal's live values would mislead); `decision` (`{outcome, decided_at, note}` once not SUBMITTED, including WITHDRAWN) or null; `can_withdraw` (drafter, SUBMITTED) and `can_decide` (Head Authority, not the drafter, SUBMITTED) | `proposal_view` | `test_governance_api.py` |
| `governance/serializers.py` | Draft input (`kind` one of the three kinds, else 400; `payload` any JSON; `justification`, checked by the service); decide input (`challenge_id`, six-digit `code`, `outcome` APPROVE or REJECT, `note` up to 500; a REJECT whose note is under 10 characters is a 400 field error on `note`, "Say why you are rejecting this change.", before the code is spent); the list's `status` filter (blank means none, unknown 400) | `DraftSerializer`, `DecideSerializer`, `ProposalFilterSerializer` | `test_governance_api.py` |
| `governance/views.py`, `governance/urls.py` | `GET /api/rule-changes` (any logged-in user, under their RLS, `?status=`, newest first, at most 100); `POST /api/rule-changes` (`role_required(LICENSING_AUTHORITY, HEAD_AUTHORITY, PERSONNEL)` plus the service's `may_draft`; 201 with the proposal); `GET /api/rule-changes/<id>` (404 "Rule change not found." when not visible); `POST .../withdraw`; `POST .../decision-code` and `POST .../decide` (`otp` throttle). Refusals map by class to fixed bodies (`_REFUSALS`): not found 404, already decided 409, the rest 403 with their message; `ProposalInvalid` 422 `{"detail": "This rule change can't be saved.", "reasons"}`; wrong code 401. Failures are returned, not raised, so a wrong code's attempt and an `apply_failed` audit are kept. POSTs need the CSRF token | `ProposalListView`, `ProposalDetailView`, `WithdrawView`, `DecisionCodeView`, `DecideView`, `_REFUSALS` | `test_governance_api.py` |
| `governance/migrations/0001_initial.py` | Creates the proposal table with its kind and status checks | — | `test_governance.py` |
| `governance/migrations/0002_rls_and_guards.py` | Row-level security (drafter and authority read, SYSTEM-only insert and update); `gj_app` may update only the decision columns (column grants) and cannot delete or truncate; `reject_decided_proposal_change()` trigger refuses any update of a row no longer SUBMITTED; shared no-delete and no-truncate triggers (reversible) | — | `test_governance.py::test_visibility`, `test_only_system_writes_proposals`, `test_decided_proposal_cannot_change_even_for_owner`, `test_app_role_can_update_only_decision_columns`, `test_proposals_cannot_be_deleted`, `test_proposals_cannot_be_deleted_even_for_owner` |

### audit: tamper-evident audit log

| File | Responsible for | Key names | Tests |
|---|---|---|---|
| `audit/hashing.py` | Hash-chain maths: each entry's hash covers the previous one | `compute_hash`, `event_fields`, `GENESIS_HASH` | `test_audit_hashing.py` |
| `audit/models.py` | The audit entry table, plus a single row holding the latest hash | `AuditEvent`, `AuditChainHead` | `test_audit.py` |
| `audit/service.py` | Writing an entry. Rules: call it **last** in a request; payloads hold **IDs and lookup keys only, never personal data** | `record` | `test_audit.py` |
| `audit/verify.py` | Recomputing the chain and reporting the first broken entry | `verify_chain`, `ChainReport` | `test_audit.py` |
| `audit/migrations/0001_initial.py` | Creates the audit entry table and the single-row chain head (`audit_head_single_row`) | — | `test_audit.py` |
| `audit/migrations/0002_protect_and_rls.py` | Append-only (REVOKE plus a trigger), readable only by Software Owner, Head Authority and SYSTEM | — | `test_audit.py` |
| `audit/management/commands/verify_audit_chain.py` | Scheduled integrity check; exits with an error if the log was altered | — | `test_audit.py::test_verify_command_*` |

### frontend: the web app (D3)

Paths are relative to `frontend/`. Stack: React 18, TypeScript (strict), Vite 6, Mantine 7, React Router 6, TanStack Query 5, react-i18next. Tests: Vitest, Testing Library, MSW 2, `vitest-axe`.

| File | Responsible for | Key names | Tests |
|---|---|---|---|
| `package.json`, `package-lock.json` | Exact-pinned dependencies; scripts `dev` (5173), `dev:mock` (5174, `--mode mock`), `build` (`tsc -b && vite build`), `test` (`vitest run`), `test:watch`, `lint`, `typecheck` | — | CI `frontend` job |
| `vite.config.ts` | Dev server on 5173 (strict port) forwarding `/api` to `http://127.0.0.1:8000` (one origin for the session cookie and CSRF); `@/` alias to `src/`; no source maps in the build; `dropMockWorker` removes `mockServiceWorker.js` (copied from `public/`) from the build output; Vitest settings (jsdom, `src/test/setup.ts`) | — | `npm run build`, every test |
| `tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json` | Strict TypeScript (`noUncheckedIndexedAccess` too) for `src/` and for the config files; `@/*` path | — | `npm run typecheck` |
| `eslint.config.js` | Flat config: typescript-eslint (type-checked), react-hooks, jsx-a11y; `no-restricted-syntax` bans `dangerouslySetInnerHTML` and `localStorage` | — | `npm run lint` |
| `postcss.config.js` | Mantine's PostCSS preset and breakpoint variables for CSS modules | — | `npm run build` |
| `.env.mock` | `VITE_MOCK_API=1`, read only in `--mode mock` (not a secret) | — | — |
| `index.html`, `src/main.tsx` | Page shell (`lang="en"`) and mounting `<App />` in `StrictMode`; in mock mode only (`import.meta.env.DEV` and `VITE_MOCK_API === "1"`) it first starts the MSW worker through a dynamic import, so MSW never reaches `vite build` | — | `npm run build` (no `msw` in `dist/`) |
| `src/App.tsx` | All providers: `MantineProvider` (theme and page background), `Notifications`, `QueryClientProvider` (a failed query is retried once, except a 4xx `ApiError`, which is never retried; no refetch on window focus) and the browser router | `App`, `AppProviders`, `createQueryClient` | `App.test.tsx` |
| `src/routes.tsx` | The route table: everything inside `SessionProvider`; `/sign-in`; `/` is the shell behind `RequireRole` (any signed-in user) with `/` redirecting to the role's home and each screen behind `RequireRole roles=[...]` (`/licensee/*` licensee, `/personnel/*` personnel, `/authority/*` Licensing Authority, `/head` Head Authority, `/overview` Software Owner, `/rule-changes/*` Licensing Authority, personnel and Head); unknown paths go to `/`. The licensee's home, transactions list and transaction detail are built (Task 5), and the new-sale wizard (Task 6); screens later tasks build are `PlaceholderPage`s for now | `routes` | `RequireRole.test.tsx`, `App.test.tsx` |
| `src/auth/session.ts` | The fixed role → landing table (never a path from input or the server: no `?next=`), the expiry path `/sign-in?expired=1`, `clearDrafts()` (removes every `gj.draft.*` key from `sessionStorage`, other keys stay), `holdsDistrictPosition` | `LANDING`, `landingFor`, `EXPIRED_PATH`, `clearDrafts`, `holdsDistrictPosition` | `SessionProvider.test.tsx`, `RequireRole.test.tsx` |
| `src/auth/SessionProvider.tsx` | Who is signed in (`useMe`; in mock mode the persona's `me_*` contract), `loading` until `me` answers, `signOut()` (`POST /api/auth/logout`, then ends the session even if that failed) and the client's expiry handler; ending a session clears the query cache and drafts and navigates to `/sign-in` (or `/sign-in?expired=1` on expiry) | `SessionProvider`, `useSession`, `Session` | `SessionProvider.test.tsx` |
| `src/auth/RequireRole.tsx` | Route guard: a loader while `me` is loading, signed-out visitors to `/sign-in`, the wrong role to its own home; `LandingRedirect` for `/` | `RequireRole`, `LandingRedirect` | `RequireRole.test.tsx` |
| `src/auth/SignInPage.tsx`, `PasswordStep.tsx`, `CodeStep.tsx`, `signInError.ts` | Sign-in in two steps; the challenge ID stays in component state (never the URL). Step 1: user ID and password (`POST /api/auth/login`), required-field errors linked to the fields. Step 2: the six-digit code in a `PinInput` (paste works; focus moves to the first digit; a fixed `id` keeps the inputs from being re-created; `withAria: false` so the error stays linked to each digit by `aria-describedby`, with `aria-invalid`), `POST /api/auth/login/verify`, then the landing route for the returned role after `me` is refetched; "Send a new code" goes back to step 1 keeping the user ID. Errors: 401 on the code step "That code didn't match…", 429 "Too many tries…", 5xx "Something went wrong…", otherwise the server's `detail` (e.g. "Invalid credentials"). `?expired=1` shows the expiry notice as `role="status"` | `SignInPage`, `PasswordStep`, `CodeStep`, `signInError` | `SignInPage.test.tsx` |
| `src/layout/AppShell.tsx` | Mantine `AppShell`: navy header (app name, `display_name` and role label, the bell for PERSONNEL and HEAD_AUTHORITY only, Sign out), the role's navigation (burger under 768 px, closes on navigating), the skip link and the page in `<main id="main">` | `AppShell` | `AppShell.test.tsx` |
| `src/layout/navigation.ts`, `NavLinks.tsx`, `NavLinks.module.css` | Each role's links (fixed paths; batches and rule changes only for personnel holding a district or state position); React Router marks the current link `aria-current="page"` | `navItems`, `NavItem`, `NavLinks` | `AppShell.test.tsx` |
| `src/layout/Bell.tsx`, `AlertsDrawer.tsx` | The bell: `home.counts.unacknowledged_alerts` (polled with home) in a saffron indicator, labelled "Alerts, N unacknowledged"; opens `AlertsDrawer`, a stub Task 7 fills | `Bell`, `AlertsDrawer` | `AppShell.test.tsx` |
| `src/layout/SkipLink.tsx`, `SkipLink.module.css` | "Skip to main content" link to `#main`, off screen until focused | `SkipLink` | `AppShell.test.tsx` |
| `src/layout/PlaceholderPage.tsx` | A titled "being built" page for routes later tasks fill, so they exist and are guarded now | `PlaceholderPage`, `PageKey` | `RequireRole.test.tsx` |
| `src/components/StatusTimeline.tsx` | A transaction's timeline as a Mantine `Timeline` (`role="list"`, labelled "Progress", `aria-live="polite"`): each event's title from `step`+`outcome` (i18n `timeline.*`; unknown pairs "Step recorded"), `by`, the IST time, "Reason: …", "Comment: …" and "Held by …" when present; tick or cross bullets with the words carrying the meaning; an optional `pending` step greyed out with a dashed line | `StatusTimeline` | `StatusTimeline.test.tsx` |
| `src/components/CodeDialog.tsx` | Generic one-time-code modal: `requestCode()` once per opening (a ref guards StrictMode), a six-digit `PinInput` (paste works, first digit focused, `withAria: false` so the error stays linked by `aria-describedby`), a 5:00 countdown from when the code was issued; when it runs out "This code has expired…" and Confirm is disabled until "Send a new code"; `submit({challenge_id, code})` → `onDone(result)`; 401 shows "That code didn't match…" and keeps it open; other failures (including a failed code request) show `ErrorNotice`. Focus trapped and Escape closes (Mantine `Modal`) | `CodeDialog`, `CodeSubmission`, `CODE_LIFETIME_MS` | `CodeDialog.test.tsx` |
| `src/components/ReasonPicker.tsx` | Reason codes for a kind (`useReasonCodes`) as a required radio group with the server's labels; `hideCodes` (default `STOCK_LIMIT`) are left out unless listed in `showCodes`; a code with `requires_text` (Other) reveals a required comment (max 500); `showErrors` shows "Choose a reason." / "Describe the reason." linked to their fields; `reasonComplete(value)` for the parent's submit | `ReasonPicker`, `ReasonValue`, `EMPTY_REASON`, `reasonComplete`, `COMMENT_MAX` | `ReasonPicker.test.tsx` |
| `src/components/PermissionCard.tsx` | A licence card: "type: scope", the number, the status badge in words, buy/sell/transport as tick or cross icons with "Can …"/"Cannot …" text (never colour alone), the stock and per-transaction limits (`Qty`), validity (`DateText`); a red banner when suspended, revoked, or not valid today (`trading_permitted` false); `titleOrder` sets its heading level (3 under a page section) | `PermissionCard` | `PermissionCard.test.tsx` |
| `src/components/StatusBadge.tsx` | A transaction status as a filled badge with its i18n label in the W2 tone (`statusTone`: approved, rejected, cancelled, waiting); "Awaiting you" (saffron) replaces it when `awaitingYou` | `StatusBadge`, `statusTone` | `StatusBadge.test.tsx` |
| `src/components/WhatsNextCard.tsx`, `EmptyState.tsx`, `Action.tsx` | The home "What's next" card (title, one sentence, one primary action, saffron left accent with square corners) and the empty-list state; both take translated strings and an optional `CardAction` (`to` renders a router link, otherwise `onClick`) | `WhatsNextCard`, `EmptyState`, `ActionButton`, `CardAction` | `WhatsNextCard.test.tsx`, `EmptyState.test.tsx` |
| `src/components/ErrorNotice.tsx` | A failure as `role="alert"` fix-it text (`errorText`): 400 "Some answers need fixing…" (field errors go under the fields) or the detail, 401 the wrong-code text, 403 the detail or "You can't do this.", 404 "Not found, or not yours to see." (never the server's detail), 409 the detail, 422 the detail plus the `reasons` list, 429 "Too many tries…", 5xx and non-API failures "Something went wrong…"; raw status codes never shown; nothing for no error | `ErrorNotice`, `errorText` | `ErrorNotice.test.tsx` |
| `src/components/Qty.tsx`, `DateText.tsx` | `Qty`: a decimal string with Indian grouping and trailing zeros dropped, done on the digits (BigInt, no float rounding), plus its unit (none for a mixed-unit class scope). `DateText`: a `<time>` in IST (`Asia/Kolkata`, `en-IN`, e.g. "4 Oct 2026, 5:22 pm"); a plain `YYYY-MM-DD` is shown as that calendar day; null is "Not set" | `Qty`, `formatQuantity`, `DateText`, `formatDate` | `Qty.test.tsx`, `DateText.test.tsx` |
| `src/features/licensee/LicenseeHomePage.tsx` | `/licensee`: "New sale" (primary), What's next from `home.counts.awaiting_your_decision` ("N purchases wait for your confirmation." linking to `?side=purchases&awaiting=me`, or "Start a new sale"), a `PermissionCard` per licence, the stock table (`Qty` with unit; "You hold no stock."), the 5 most recent transactions and a link to all | `LicenseeHomePage` | `LicenseeHomePage.test.tsx` |
| `src/features/licensee/LicenseeTransactionsPage.tsx` | `/licensee/transactions`: tabs All / Sales / Purchases / Waiting for you; the filter lives in the address (`?side=sales\|purchases`, `?awaiting=me`: no personal data) and unknown values are dropped before the request; empty states per tab | `LicenseeTransactionsPage`, `filtersFrom` | `LicenseeTransactionsPage.test.tsx` |
| `src/features/licensee/paths.ts` | The licensee's fixed paths (home, transactions, the awaiting-purchases link, new sale) | `TRANSACTIONS_PATH`, `AWAITING_PURCHASES_PATH`, `NEW_SALE_PATH`, `LICENSEE_HOME_PATH` | — |
| `src/features/transactions/TransactionList.tsx` | Transactions as a table (reference link, substance, quantity with unit, other party, `StatusBadge`, date) or, under 768 px (`useMediaQuery`), a list of stacked cards; only one is rendered. Other party: the buyer for a seller, the seller for a buyer, "seller to buyer" for anyone else | `TransactionList`, `otherParty` | `LicenseeTransactionsPage.test.tsx`, `LicenseeHomePage.test.tsx` |
| `src/features/transactions/TransactionPage.tsx`, `TransactionDetail.tsx` | The `:reference` route (back link to `listPath`, the heading, loading and `ErrorNotice`) and the reusable detail (licensee now, personnel in Task 7): status badge ("Awaiting you" when `can_decide`), `next_action` in a What's next card, the stock-limit sentence in a warning `Alert` **only when `your_role` is buyer**, the decision area, seller cancel, summary (substance, quantity, parties, started, approval chain label, designated officer), transport, and `StatusTimeline` with the pending step from the status | `TransactionPage`, `TransactionDetail` | `TransactionPage.test.tsx` |
| `src/features/transactions/DecisionPanel.tsx` | The decision, driven only by `can_decide` and `allowed_outcomes` (`offeredOutcomes`: a buyer with `stock_limit_problem` is offered REJECT only, even if the server listed CONFIRM). Confirm/Approve/Recommend open `CodeDialog`; Reject first shows `ReasonPicker` (buyer: `BUYER_REJECTION`, others `OFFICER_REJECTION`) and needs a complete reason. Over the stock limit the reject form shows at once with `STOCK_LIMIT` shown and preset (changeable) and no Confirm button. Posts `{challenge_id, code, outcome}` plus `reason_code` and trimmed `comment` for a reject; a success notification; a 422/409 closes the dialog, shows `ErrorNotice` (with the server's reasons) on the page and refetches. Hooks invalidate the transaction, lists, home and alerts | `DecisionPanel`, `offeredOutcomes`, `reasonKindFor` | `TransactionPage.test.tsx` |
| `src/features/transactions/CancelSale.tsx` | "Cancel sale" for the seller while `AWAITING_BUYER` (`canCancel`): a confirmation modal ("Keep the sale" / "Yes, cancel the sale"), `POST …/cancel`, "Sale cancelled." notification; errors in the modal | `CancelSale`, `canCancel` | `TransactionPage.test.tsx` |
| `src/features/sale/NewSalePage.tsx` | `/licensee/sale/new`: a Mantine `Stepper` (Buyer, Goods, Transport, Review and send) with "Step N of 4"; the step's `h2` takes focus on every step change; Next runs the step's checks (`stepErrors`) and shows each message under its field; Back keeps everything. Owns the draft: saved to sessionStorage 300 ms after the last change (`DRAFT_DEBOUNCE_MS`), restored on load onto the furthest step that still holds (`reachableStep`) with a "Draft restored" notice, "Start over" (empty form, draft removed) and "Discard draft" (removed, back home); on send the draft is cleared, no pending save can write it back, "Sent to the buyer for confirmation." is shown and the new transaction opens by its reference | `NewSalePage`, `DRAFT_DEBOUNCE_MS` | `NewSalePage.test.tsx` |
| `src/features/sale/BuyerStep.tsx` | Step 1: the GSTIN (uppercased, no spaces, 15 characters, format help), checked against the backend pattern before "Find buyer" posts `buyer-lookup` (the GSTIN only in the body); the registered name with "Is this the right business?" Yes / Change; a 404 shows the server's own words; any GSTIN change forgets the buyer and the check | `BuyerStep` | `NewSalePage.test.tsx` |
| `src/features/sale/GoodsStep.tsx` | Step 2: substance (`NativeSelect` of `sellableSubstances`, "Name (unit)"; a notice when none can be sold) and quantity labelled with its unit; "Check" posts `transactions/check`: ok shows "This sale can go ahead." (+ `TwoStepNotice` for `OFFICER_THEN_SUPERINTENDENT`), a refusal lists the reasons; any change to substance or quantity drops the check | `GoodsStep`, `TwoStepNotice` | `NewSalePage.test.tsx` |
| `src/features/sale/TransportStep.tsx` | Step 3: transporter name, ID or licence number, vehicle number (uppercased) and route, each with help text and the backend's max length | `TransportStep` | `NewSalePage.test.tsx` |
| `src/features/sale/ReviewStep.tsx` | Step 4: everything in one table, the two-step notice, "Send to buyer" (`useStartSale`, the body from `toNewSale`, trimmed); a 422 shows the detail and reasons with "Change the goods" (back to step 2, check dropped); a 400 lists the field messages | `ReviewStep`, `toNewSale` | `NewSalePage.test.tsx` |
| `src/features/sale/validation.ts`, `stepProps.ts` | The wizard's rules, mirroring the backend: `GSTIN_PATTERN` (licensing/service.py), `VEHICLE_PATTERN` and max lengths (transactions/serializers.py), quantity up to 9 digits and 3 decimals and above 0; `checkKey` ties a passed check to buyer + substance + quantity; per-step errors as i18n keys | `stepErrors`, `checkPassed`, `reachableStep`, `normaliseGstin` | `NewSalePage.test.tsx` |
| `src/features/sale/sellable.ts` | The substances a seller may sell today: licences with `may_sell`, `trading_permitted` and ACTIVE; a substance licence (card `unit` set) covers the substance it names, a class licence (`unit` null) every substance whose `substance_class` it names | `sellableSubstances` | `sellable.test.ts`, `NewSalePage.test.tsx` |
| `src/features/sale/draft.ts` | The draft in `sessionStorage["gj.draft.sale"]` only (the `gj.draft.` prefix that `clearDrafts` removes on sign-out and expiry): `loadDraft` (null when missing or damaged), `saveDraft`, `clearDraft`, `emptyDraft` | `DRAFT_KEY`, `SaleDraft` | `draft.test.ts`, `NewSalePage.test.tsx` |
| `src/theme.ts` | Design W2, the only place for colours: `navy` 10-shade palette as the primary colour (brand shade 6, `#1B365D`), `saffron` for attention only, page `#F5F7FA` (`cssVariablesResolver`), radius `sm`, system font stack, `autoContrast` for readable text on saffron; status colours chosen for AA with their text (a darker green `#1F7A35`, `red.9`, `gray.7`, saffron with dark text); allowance, accent and warning colours for the shared components; modal and drawer headers render as `<div>` (a `<header>` portalled to `<body>` is a second banner landmark) | `theme`, `cssVariablesResolver`, `STATUS_COLORS`, `StatusTone`, `AWAITING_YOU_COLOR`, `ALLOWED_COLOR`, `NOT_ALLOWED_COLOR`, `WARNING_COLOR`, `ACCENT_BORDER`, `NAVY`, `SAFFRON`, `PAGE_BACKGROUND` | `App.test.tsx` (axe), the component tests |
| `src/i18n/index.ts`, `src/i18n/en.json`, `src/i18n/i18next.d.ts` | i18next with English only, no detection, `escapeValue: false` (React escapes); every user-visible string is a key in `en.json`; `t()` keys are type-checked | `resources`, `defaultNS` | `App.test.tsx`, `render.test.tsx` |
| `src/test/setup.ts` | jest-dom and `vitest-axe` matchers; the MSW server with `onUnhandledRequest: "error"` (reset after each test); clears Mantine's notification store, `sessionStorage`, the CSRF cookie and the client's state (`resetClientState`); `matchMedia`, `ResizeObserver`, `scrollIntoView` and canvas stubs for Mantine and axe in jsdom | — | every test |
| `src/test/server.ts` | The shared MSW server, serving the contract handlers by default (`server.use(...)` overrides an endpoint in one test) | `server` | every test |
| `src/test/contracts/*.json` | The API contracts captured from the real backend by `backend/tests/test_api_contracts.py` (synthetic fixture data only). Never edit by hand: regenerate with `UPDATE_CONTRACTS=1` | — | `test_api_contracts.py`, `src/api/contracts.test.ts` |
| `src/test/handlers.ts` | MSW handlers serving the contracts: one default per endpoint (`ENDPOINTS`, fixed paths before `:param` paths), the CSRF view (sets the `csrftoken` cookie), logout (204) and reason codes by `kind`. `createHandlers(selected)` swaps in variants (another role or state); `serveContract(name, target?)` overrides one endpoint in a test (status from the endpoint or an `error_NNN_` name); `contract(name)` returns a fresh copy | `contracts`, `contract`, `createHandlers`, `handlers`, `serveContract` | `hooks.test.tsx`, `browser.test.ts`, `client.test.ts` |
| `src/mocks/browser.ts`, `public/mockServiceWorker.js` | Mock mode (`npm run dev:mock`): the MSW service worker with the same handlers; `?as=seller\|buyer\|buyer-stock\|officer\|superintendent\|la\|head` picks the `me`, `home` and transaction-detail contracts (kept in `sessionStorage` under `gj.mock.as` for the tab; seller by default). The worker file is generated by `npx msw init public --save` and is dev-only | `PERSONAS`, `mockPersona`, `startMockWorker` | `browser.test.ts` |
| `src/api/types.ts` | Hand-written, minimal types for every response (quantities as decimal strings, dates as ISO strings); `stock_limit_problem` is the buyer's only; `drafted_by` is optional (Head Authority and Software Owner only) | `Me`, `Home`, `TransactionSummary`, `TransactionDetail`, `CheckResult`, `LicenceCard`, `StockRow`, `ReasonCode`, `Substance`, `LicenceType`, `ApprovalThreshold`, `Alert`, `AlertList`, `BatchSummary`, `BatchDetail`, `ReviewSetting`, `RuleChange`, `LicenceRegister`, `LicenceDetail`, `ErrorBody` | `contracts.test.ts` |
| `src/api/client.ts` | The only code that calls `fetch`: same-origin credentials; `ensureCsrf()` fetches `/api/auth/csrf` once (again only after a failure) and every non-GET sends `X-CSRFToken` from the `csrftoken` cookie, read fresh each time (Django rotates it at sign-in); every failure becomes `ApiError {status, detail, reasons?, fieldErrors?}` (`fieldErrors` from a 400's field lists, `reasons` from a 422); a 403 on any call except `me` triggers `GET /api/auth/me`, and if that fails the handler registered with `setSessionExpiredHandler` runs (SessionProvider, Task 3) | `apiGet`, `apiPost`, `apiPut`, `ensureCsrf`, `ApiError`, `setSessionExpiredHandler`, `resetClientState`, `query` | `client.test.ts` |
| `src/api/auth.ts`, `home.ts`, `transactions.ts`, `alerts.ts`, `oversight.ts`, `licensing.ts`, `catalogue.ts`, `governance.ts` | Typed functions, one per endpoint. GSTINs, transport details and codes travel only in POST bodies, except the register's exact GSTIN search, which the backend offers only as a GET query (`searchRegister`) | `startLogin`, `verifyLogin`, `logout`, `getMe`, `getHome`, `listTransactions`, `getTransaction`, `checkSale`, `lookupBuyer`, `startSale`, `requestDecisionCode`, `decideTransaction`, `cancelTransaction`, `listAlerts`, `acknowledgeAlert`, `listBatches`, `getBatch`, `flagItem`, `requestSignOffCode`, `signOff`, `listReviewSettings`, `saveReviewSetting`, `myLicences`, `myStock`, `searchRegister`, `getLicence`, `listSubstances`, `listClasses`, `listLicenceTypes`, `listApprovalThresholds`, `listReasonCodes`, `listRuleChanges`, `getRuleChange`, `draftRuleChange`, `withdrawRuleChange`, `requestRuleChangeCode`, `decideRuleChange` | `hooks.test.tsx`, `client.test.ts` |
| `src/api/hooks/keys.ts` | Every query key as a constant (keys with arguments start with their area's key, so invalidating the area refreshes all of them); `POLL_MS` (30 s, W7); `invalidate(client, ...keys)` always adds `["home"]` | `keys`, `POLL_MS`, `invalidate` | `hooks.test.tsx` |
| `src/api/hooks/*.ts` | TanStack Query hooks per area. `useHome` and `useAlerts` poll every 30 s. Mutations store the returned object in its detail key, then invalidate the related lists and home (a decision also alerts; a flag also alerts; an approved rule change also the catalogue); `useLogout` clears the cache. The catalogue is kept fresh for 5 minutes | `useMe`, `useStartLogin`, `useVerifyLogin`, `useLogout`, `useHome`, `useTransactions`, `useTransaction`, `useCheckSale`, `useLookupBuyer`, `useStartSale`, `useRequestDecisionCode`, `useDecideTransaction`, `useCancelTransaction`, `useAlerts`, `useAcknowledgeAlert`, `useBatches`, `useBatch`, `useFlagItem`, `useRequestSignOffCode`, `useSignOff`, `useReviewSettings`, `useSaveReviewSetting`, `useMyLicences`, `useMyStock`, `useRegister`, `useLicence`, `useSubstances`, `useClasses`, `useLicenceTypes`, `useApprovalThresholds`, `useReasonCodes`, `useRuleChanges`, `useRuleChange`, `useDraftRuleChange`, `useWithdrawRuleChange`, `useRequestRuleChangeCode`, `useDecideRuleChange` | `hooks.test.tsx` |
| `src/test/render.tsx` | `renderWithProviders(ui, {route, path})`: the real providers, a fresh query cache and a memory router; `renderApp(route, {contracts, signedOut})`: the whole route table (session, guards, shell) signed in as the contracts' person (licensee by default) or signed out; `serveSignedOut()` makes `me` answer 403. Handlers a test set with `server.use(...)` before `renderApp` stay ahead of the contract handlers it adds (it re-applies them last). Both return a `user` (user-event), the `router` and the `queryClient` | `renderWithProviders`, `renderApp`, `serveSignedOut` | `render.test.tsx`, the auth and layout tests |
| `src/test/vitest-axe.d.ts` | Declares `toHaveNoViolations` on Vitest's `Assertion` (vitest-axe 0.1.0 only types the legacy `Vi` namespace) | — | `npm run typecheck` |

### Repository, CI and local setup

| File | Responsible for | Check name |
|---|---|---|
| `.github/workflows/ci.yml` | Backend: lint, format, migrations check, tests, dependency vulnerability audit, production settings check | `backend` |
| `.github/workflows/ci.yml` | Frontend (Node 22, npm cache on `frontend/package-lock.json`): `npm ci`, lint, type check, tests, build, `npm audit --audit-level=high` | `frontend` |
| `.github/workflows/branch-policy.yml` | Pull requests into `main` must come from `dev` | `source-branch` |
| `.github/workflows/codeql.yml` | Security scanning of Python, GitHub Actions and JavaScript/TypeScript | `analyze (python)`, `analyze (actions)`, `analyze (javascript-typescript)` |
| `.github/dependabot.yml` | Weekly dependency updates: uv (`/backend`), npm (`/frontend`) and GitHub Actions | — |
| GitHub ruleset "Protect dev and main" | Pull request required, the checks above must pass, merge commits only, no force-push, deletion or bypass. `frontend` and `analyze (javascript-typescript)` become required only after the owner confirms | — |
| `.claude/launch.json` | Local preview servers: `backend` (`uv run --env-file .env python manage.py runserver 8000` in `backend/`), `frontend` (`npm run dev`, 5173), `frontend-mock` (`npm run dev:mock`, 5174) | — |
| `docker-compose.yml`, `docker/postgres-init.sh` | Local Postgres 16 with roles `gj_owner` (migrations and tests) and `gj_app` (the running app) | — |

---

## 3. Test catalogue: what each test proves

Run all: `cd backend && uv run --env-file .env.test pytest`. Run one: `... pytest tests/<file>.py::<test> -v`.

Shared fixtures (`make_user`, `make_licence`, `make_licensee`, `trade`, `org`, `catalogue`, `otp_outbox`, `audit_actions`, `settle`) live in `tests/conftest.py`; see its row in section 2.

### `test_env.py`: configuration loading
| Test | Proves |
|---|---|
| `test_required_returns_trimmed_value` | Values are read without surrounding spaces |
| `test_required_fails_fast_when_missing`, `test_required_fails_fast_when_blank` | A missing or blank required setting stops startup |
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
| `test_decrypt_rejects_garbage`, `test_decrypt_rejects_value_encrypted_with_another_key` | Tampered data or a wrong key fails safely |
| `test_blind_index_is_deterministic_and_normalised` | Same value → same key, ignoring case and spaces |
| `test_blind_index_differs_between_values`, `test_blind_index_depends_on_secret_key`, `test_blind_index_differs_by_context` | Keys can't be guessed or linked across fields |
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
| `test_app_role_cannot_update_events`, `test_app_role_cannot_delete_events` | The app can't edit or delete entries |
| `test_trigger_blocks_changes_even_for_table_owner` | Even the database owner is blocked |
| `test_verify_detects_edited_event`, `test_verify_detects_deleted_middle_event`, `test_verify_detects_deleted_last_event` | Every kind of tampering is detected |
| `test_verify_accepts_events_appended_after_head_read` | No false alarm when entries are written during a check |
| `test_only_audit_readers_can_read_events` (every role) | Only Software Owner and Head Authority can read the log |
| `test_anonymous_context_cannot_read_events` | Anonymous requests see nothing |
| `test_verify_command_reports_ok`, `test_verify_command_fails_loudly_on_tampering` | The scheduled check reports correctly |

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
| `test_full_login_requires_password_and_otp` | The password alone doesn't log you in; password plus code does (`/me` then returns the user id and role) |
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

### `test_thresholds.py`: approval thresholds and the approval chain
| Test | Proves |
|---|---|
| `test_no_threshold_means_officer_chain` | With no threshold the officer alone approves, whatever the quantity |
| `test_class_threshold_applies_to_its_substances` | A class threshold (Spirits above 200) makes 201 L of Whisky or Rum two-step; exactly 200 stays with the officer |
| `test_substance_threshold_beats_class` | A substance threshold (Whisky 100) beats the class threshold (Spirits 500); other substances keep the class threshold |
| `test_latest_threshold_version_wins` | A change is a new version (1, 2) of the same threshold and the latest is used |
| `test_threshold_needs_exactly_one_scope` | The database rejects a threshold with both or neither of substance and class |
| `test_threshold_qty_must_be_positive` | The database rejects a zero threshold quantity |
| `test_threshold_versions_cannot_be_edited_by_app_role` | The app role can't update threshold versions |
| `test_threshold_versions_are_append_only_even_for_owner` | A trigger stops even the table owner editing a threshold version |
| `test_approval_chain_cannot_be_updated_by_app_role` | New transactions default to the OFFICER chain, and even SYSTEM under the app role can't change the chain |

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

### `test_licence_register.py`: licence register for authorities

| Test | Proves |
|---|---|
| `test_only_authorities_can_use_register` (each role) | Licensing Authority, Head Authority and Software Owner get 200 on the list and the detail; a licensee and personnel get 403 |
| `test_mine_still_routes_to_my_licences` | `licences/mine` still reaches the licensee-only view (403 for a Head Authority), not the detail route |
| `test_exact_search_by_number_and_gstin` | Number and GSTIN searches ignore case and surrounding spaces; a partial number or GSTIN finds nothing |
| `test_filters_and_pagination` | Exact row fields; 25 per page with the total count; a page beyond the end is empty with the count; status and area filters; a bad page (0, not a number, above 10**6 including a 30-digit page), status or area gives 400 "Unknown filter value."; an unfiltered listing is not audited |
| `test_detail_has_periods_and_permissions_but_no_contact_or_stock` | The detail has the GSTIN, the periods and the permission fields; the response contains neither the contact digits nor the stock balance; an unknown id is 404 |
| `test_search_and_view_are_audited_by_blind_index_only` | Searches are audited with the blind index and result count, the view with the licence id; the raw number and GSTIN appear nowhere in the audit log |

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
| `test_buyer_stock_limit_message` | Buyer stock-limit breach is reported (with the buyer's numbers) when `include_buyer_stock=True` |
| `test_buyer_stock_not_checked_by_default` | Without the flag the buyer's stock cap is not checked |
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

### `test_two_step_approval.py`: severity routing and the two-step approval

| Test | Proves |
|---|---|
| `test_start_records_the_chain` | With Spirits above 200, 150 L starts on the officer chain and 250 L on the two-step chain |
| `test_officer_must_recommend_on_two_step_chain` | On the two-step chain the officer's APPROVE is refused; RECOMMEND leads to waiting for the superintendent |
| `test_officer_cannot_recommend_on_officer_chain` | RECOMMEND is not available on the officer chain |
| `test_two_step_chain_moves_stock_only_on_final_approval` | The recommendation moves no stock and leaves `decided_at` empty; the superintendent's approval moves it, sets `decided_at`, records each step with its position and holder, and audits `transaction.recommended` then `transaction.approved` |
| `test_superintendent_rejects_with_reason` | The superintendent needs an officer-kind reason; the rejection is final, audited and moves nothing |
| `test_only_current_superintendent_can_decide` | After a transfer of the district position only the new holder can decide |
| `test_recommend_rechecks_and_refuses` | A recommendation re-runs the checks; a seller suspended after the confirm is refused, audited, and the transaction stays with the officer |
| `test_final_approval_rechecks_stock` | Stock that left the seller after the recommendation blocks the final approval; nothing moves and it keeps waiting |
| `test_detail_shows_chain_and_allowed_outcomes` | Over HTTP: the chain and its label, each party's allowed outcomes (empty for the seller), and a timeline showing both approval positions with `held_by` for authority viewers only |
| `test_superintendent_sees_final_approval_next_action` | Over HTTP: the superintendent sees "Your decision is needed."; the officer sees the waiting-for-final-approval message |
| `test_settle_drives_the_two_step_chain` | The `settle` fixture drives recommend and final approval |
| `test_dual_holder_approves_both_levels_at_once` | Over HTTP: an officer who also holds the district position sees APPROVE/REJECT and "Your decision is needed." at the officer step; APPROVE makes it APPROVED, moves stock, writes an OFFICER RECOMMEND (area position) and a SUPERINTENDENT APPROVE (district position) row by the same holder with one signing time, audits one `transaction.approved` with `{"both_levels": true}` (no `transaction.recommended`), and the timeline shows both positions |
| `test_dual_holder_reject_is_officer_rejection` | The dual holder cannot RECOMMEND; their REJECT is `REJECTED_BY_OFFICER`, audited `transaction.officer_rejected`, one OFFICER row, no stock moves |
| `test_promoted_recommender_gives_final_approval` | Over HTTP: the officer who recommended, then promoted to the district position (a new holder takes the area position), sees "Your decision is needed.", `can_decide` true and APPROVE/REJECT; their APPROVE moves stock |

### `test_buyer_stock_limit.py`: the buyer decides on their own stock limit

| Test | Proves |
|---|---|
| `test_start_is_not_refused_for_buyer_stock` | A sale that would take the buyer over their limit still starts |
| `test_seller_never_sees_buyer_stock` | Over HTTP: the seller's whole start response, detail and list (timestamps and reference left out) carry no buyer numbers and `stock_limit_problem` is None; after the buyer's STOCK_LIMIT rejection the seller's timeline shows only the reason label |
| `test_buyer_sees_problem_and_only_reject` | Over HTTP: the buyer sees the exact sentence and `allowed_outcomes == ["REJECT"]` |
| `test_buyer_without_problem_may_confirm_or_reject` | Without a problem the buyer sees no sentence and may confirm or reject |
| `test_buyer_confirm_is_refused_with_422` | Over HTTP: CONFIRM is refused (422, the sentence), audited `transaction.confirm_refused`; still waiting for the buyer, no decision written |
| `test_blank_reason_defaults_to_stock_limit` | A REJECT with no reason while the problem exists is stored as STOCK_LIMIT |
| `test_blank_reason_without_problem_still_needs_a_reason` | Without the problem a blank reason is still refused |
| `test_stock_limit_reason_refused_when_no_problem` | STOCK_LIMIT without the problem is refused with the exact message before the code is spent; the same code then works |
| `test_stock_limit_reason_refused_under_lock_is_audited` | The race: the pre-code check sees a stock problem (patched), the in-lock check does not; the STOCK_LIMIT rejection is refused with the exact message, audited `transaction.reject_refused`, and nothing is written (still waiting for the buyer, no decision, no alert) |
| `test_stock_limit_rejection_raises_no_alert_and_is_not_counted` | A STOCK_LIMIT rejection raises no alert (payload `{"alerts_raised": 0}`); a later NOT_ORDERED rejection shows pattern count 1 |
| `test_officer_approval_still_checks_buyer_cap` | Buyer stock that rose after the confirm blocks the officer's approval with the cap message (numbers, for the officer); audited `approval_refused` |
| `test_officer_recommend_checks_buyer_cap` | The officer's recommendation on the two-step chain checks the buyer's cap too |
| `test_stock_limit_reason_is_seeded` | The STOCK_LIMIT buyer reason exists with its label and sort order 50 |

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
| `test_buyer_rejection_audit_counts_alerts_raised` | The buyer-rejection audit event carries `{"alerts_raised": 2}` |

### `test_alerts_api.py`: alerts API

| Test | Proves |
|---|---|
| `test_officer_sees_alert_with_pattern` | The officer lists the alert with reason, pattern wording and registered names, and no licence numbers |
| `test_acknowledge_over_http` | Acknowledging with a note returns the updated alert and the unacknowledged count drops to 0 |
| `test_licensees_see_no_alerts` | A licensee gets an empty list |
| `test_cannot_acknowledge_someone_elses_alert` | The superintendent cannot acknowledge the officer's alert (403) |
| `test_unacknowledged_count_is_not_capped_by_the_list` | With 101 unacknowledged alerts the list holds 100 but the count says 101 |
| `test_acknowledge_rejects_bad_input` | A note over 500 characters, a null note and a non-object body are 400 and acknowledge nothing |
| `test_acknowledge_without_body_works` | An empty body acknowledges with no note |

### `test_review_settings_api.py`: review-settings API

| Test | Proves |
|---|---|
| `test_overview_lists_every_district_position` | Every district position by id (not the taluka position), with and without a setting; current period end and last batch end are correct; no current period before `starts_on`; the Licensing Authority sees the batch dates over HTTP although RLS hides batches from it |
| `test_only_licensing_authority_can_change` (each role) | GET is 200 for Licensing Authority, Head Authority and Software Owner and 403 for personnel and licensees; a PUT from anyone but the Licensing Authority is 403 and saves nothing |
| `test_change_is_saved_and_audited` | A PUT saves the period and start, returns the position's overview row, and is audited as `oversight.review_period_set` with the Licensing Authority's user id |
| `test_invalid_period_is_422_with_reasons` (each case) | 20 days, a taluka position and a start that would skip days each give 422 with the exact reason; the setting is unchanged |
| `test_bad_types_are_400` | A non-integer period, a missing period or a bad date is 400 |
| `test_unknown_position_is_404` | An unknown position id is 404 "Position not found." |
| `test_change_requires_csrf` | A PUT without the CSRF token is 403 and saves nothing; with the token it is 200 |

### `test_oversight_api.py`: oversight API

| Test | Proves |
|---|---|
| `test_superintendent_reviews_flags_and_signs` | List, detail (an officer-only item has `approved_by_superintendent` false), flag and OTP sign-off work end to end; `can_sign` turns false once signed |
| `test_flag_reaches_the_officer_as_an_alert` | A flag appears in the approving officer's alerts with no pattern signal |
| `test_others_cannot_see_or_act_on_batches` | The officer sees no batches (404 on detail) and cannot flag (403) |
| `test_bad_reason_is_400_and_wrong_code_is_401` | A buyer-rejection reason is 400; a wrong code is 401 |
| `test_superintendent_approved_item_is_marked_and_cannot_be_flagged` | Over HTTP: a two-step item shows `approved_by_superintendent` true and flagging it is 403 with the exact message |

### `test_oversight_review.py`: flags and sign-off

| Test | Proves |
|---|---|
| `test_flag_alerts_the_approving_officer` | A flag stores the reason, alerts the officer position that approved, and is audited last |
| `test_flag_needs_a_flag_reason` | A buyer-rejection reason or a blank "other" is refused |
| `test_one_flag_per_transaction` | A second flag on the same transaction is refused |
| `test_only_the_superintendent_can_review` | The officer cannot flag or request a sign-off code |
| `test_transaction_must_be_in_the_batch` | A transaction outside the batch cannot be flagged |
| `test_sign_off_with_code` | A correct code signs the batch, status becomes SIGNED, audited |
| `test_wrong_code_does_not_sign` | A wrong code counts an attempt and signs nothing |
| `test_signed_batch_cannot_be_flagged_or_signed_again` | After sign-off, flagging and a new code are refused |
| `test_batch_status_open_then_overdue` | OPEN through the 30th day after the period, OVERDUE the day after |
| `test_flags_and_sign_offs_are_append_only_even_for_owner` | Triggers stop even the owner editing flags and sign-offs |
| `test_superintendent_approved_items_are_marked` | In a batch with an officer-only and a two-step transaction, `approved_by_superintendent` is false and true, and the approving position is the area officer and the district position |
| `test_superintendent_cannot_flag_own_approval` | Flagging an item the superintendent approved is refused with the exact message; no flag, no alert, no audit |
| `test_officer_only_flag_still_alerts_officer` | Regression: flagging the officer-only item in the same batch still alerts the area officer |
| `test_dual_holder_approval_is_marked_in_oversight_and_cannot_be_self_flagged` | A dual holder's one-step approval is marked `approved_by_superintendent` with the district position in their batch, and flagging it is refused with the exact message; no flag, no audit |

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
| `test_batch_audits_are_written_after_all_batches` | Every batch exists before the first `oversight.batch_created` audit; the audits are the last actions |
| `test_command_refuses_a_future_today` | A `--today` after the real date is refused |
| `test_new_setting_starts_no_later_than_the_earliest_approval` | A new setting defaults to the earliest approval's date and refuses a later explicit start |

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

### `test_home_api.py`: home-screen counts

| Test | Proves |
|---|---|
| `test_home_needs_login` | Anonymous gets 403 |
| `test_licensee_counts` | The buyer's count includes sales over their stock limit (they can only reject) and leaves out the one they rejected; the seller counts their sales in progress |
| `test_sales_in_progress_counts_every_waiting_status` | AWAITING_BUYER, AWAITING_OFFICER and AWAITING_SUPERINTENDENT count; a rejected sale does not |
| `test_personnel_awaiting_includes_promoted_recommender` | The superintendent counts the recommended transaction; once the officer also holds the district position, the one they recommended counts for them too (a superintendent's approval is enough) |
| `test_personnel_alerts_and_batches` | Exact alert, open, overdue and next-due counts for the superintendent with a past `today`; the officer sees no batches; over HTTP every batch is overdue today |
| `test_licensing_authority_counts` | Only ACTIVE licences whose latest period ends within today..today+30 count (renewed, suspended, ended and too-late ones do not); districts without a review period count |
| `test_head_authority_and_owner_counts` | Head Authority and Software Owner see all unacknowledged alerts and all transactions waiting for a superintendent; the Head Authority also gets the rule-change counts |
| `test_rule_change_counts` | Licensing Authority counts own open and all open proposals; each Head officer counts open proposals not drafted by them and their own; a superintendent counts their own; withdrawn ones never count; the HTTP count matches |

### `test_d3_apis.py`: web-app APIs

| Test | Proves |
|---|---|
| `test_me_has_display_name_and_positions` | Licensee gets their holder name; Personnel with two positions get both titles and positions by id; Personnel with none are "Unassigned officer"; Licensing Authority gets the role label |
| `test_awaiting_me_filter_matches_home_count` | `?awaiting=me` returns exactly the home count's set, for an officer holding both positions (including their own recommendation) and for the buyer |
| `test_side_filter` | `side=sales` and `side=purchases` match the user's side; filters combine with AND |
| `test_blank_filter_means_no_filter` | Over HTTP: `?side=&awaiting=me` filters by `awaiting` only; all-blank filters return everything visible |
| `test_filter_serializer_accepts_blanks_from_any_source` | The filter serializer accepts blank values from plain data (not only a query string) |
| `test_approved_by_superintendent_filter` | Only transactions with a superintendent approval match, also combined with `side` |
| `test_unknown_filter_is_400` | Unknown filter values return 400 "Unknown filter value." |
| `test_check_endpoint_ok_and_chain` | The pre-check says ok with the OFFICER chain, and the two-step chain above the threshold |
| `test_check_endpoint_reasons_and_no_writes` | Refusal reasons (including self-sale) with a null chain; each check is audited `transaction.checked` with only `gstin_index` and `ok`, no GSTIN; no transaction is created |
| `test_check_endpoint_hides_buyer_stock` | A sale over the buyer's stock limit checks ok, so the seller learns nothing about the buyer's stock |
| `test_check_requires_licensee_and_csrf` | Personnel get 403; without the CSRF header 403, with it 200 |
| `test_thresholds_api` | Anonymous 403; a licensee reads each threshold's latest version with scope, kind, quantity and unit |
| `test_acknowledge_twice_is_409_with_message` | A second acknowledgement is 409 with "This alert is already acknowledged." |
| `test_acknowledge_not_holder_is_403_with_message` | Someone not holding the position gets 403 with the fixed message |

### `test_governance.py`: rule-change proposals

| Test | Proves |
|---|---|
| `test_licensing_authority_head_and_district_superintendent_may_draft` | The Licensing Authority, Head Authority and a district superintendent may draft; the proposal is SUBMITTED with the drafter's id, role and cleaned payload |
| `test_others_may_not_draft` | A taluka-only officer, a licensee and a software owner are refused with the exact message and nothing is written |
| `test_payload_validation_messages` | Exact messages for a duplicate licence type code, unknown licence type, class and substance codes, a per-transaction limit above the stock limit, both or neither scope, and an unknown kind |
| `test_payload_field_rules` | Bad code pattern, overlong name, zero quantity, validity above 120, missing quantity and a non-object payload are refused |
| `test_payload_is_cleaned` | Names are trimmed, a missing description becomes blank, unknown keys are dropped and quantities are stored as strings with three decimals |
| `test_invalid_payload_is_not_drafted` | An invalid payload writes no proposal |
| `test_justification_required` | A blank, too short (under 10 after trimming) or too long (over 1000) justification is refused |
| `test_justification_limits_are_inclusive` | 10 and 1000 characters are accepted |
| `test_draft_is_audited_without_payload_values` | `rule_change.drafted` carries only `{"proposal_id", "kind"}` |
| `test_withdraw_rules` | Only the drafter may withdraw, only while submitted; withdrawal records who and when and is audited with id and kind |
| `test_withdraw_an_invisible_proposal_is_not_found` | A proposal the caller cannot see, or one that does not exist, is "Rule change not found." |
| `test_visibility` | A superintendent sees only their own proposals; Licensing Authority, Head Authority and Software Owner see all; a licensee and taluka personnel see none |
| `test_only_system_writes_proposals` | A direct insert outside SYSTEM is refused by row-level security |
| `test_decided_proposal_cannot_change_even_for_owner` | Once APPROVED, even the table owner cannot change the note or reopen the status |
| `test_app_role_can_update_only_decision_columns` | As SYSTEM under `gj_app`, updating `payload` is a privilege error while the decision columns can be updated |
| `test_proposals_cannot_be_deleted` | `gj_app` cannot delete a proposal, even as SYSTEM |
| `test_proposals_cannot_be_deleted_even_for_owner` | The no-delete trigger stops the table owner too |

### `test_governance_decisions.py`: deciding rule changes

| Test | Proves |
|---|---|
| `test_approve_new_licence_type_applies_it` | A Head Authority approval creates the licence type and records decider, time, note and `applied_ref` `licence_type:<id>` |
| `test_approve_rule_version_creates_rule_if_missing_and_versions_existing` | An existing rule gets the next version (created by the decider); a missing (type, substance) rule is created with version 1 |
| `test_approve_threshold_changes_new_transactions_only` | A transaction in flight keeps its two-step chain; a new one at the same quantity gets the officer-only chain |
| `test_existing_licence_permissions_unchanged_after_rule_change` | A licence's frozen permission snapshot is untouched by an approved rule version |
| `test_reject_needs_note_and_changes_nothing` | A blank or short reject note is refused before the code is spent ("Say why you are rejecting this change."); the same code then rejects with the trimmed note, no catalogue change, audited with id and kind |
| `test_drafter_cannot_decide_own_change` | A Head drafter is refused at the code request and when spending a valid code from another proposal (exact message, code not spent, nothing changes); another Head officer may decide it |
| `test_drafter_is_refused_under_the_lock` | With the first check bypassed, the re-check under the proposal lock still refuses the drafter |
| `test_only_head_can_decide` | Licensing Authority, a superintendent and a software owner are refused at the code request and at decide |
| `test_unknown_outcome_is_refused` | Only APPROVE and REJECT are accepted |
| `test_code_of_another_user_is_refused` | A code issued to another Head officer cannot sign |
| `test_wrong_code_counts_and_changes_nothing` | A wrong code returns None, counts one attempt, and changes nothing |
| `test_apply_failure_rolls_back_and_is_audited` | Approving the same type code through a second proposal leaves no rows, stays SUBMITTED with no decider, and records only `rule_change.apply_failed` (id and kind) |
| `test_rule_version_apply_failure_leaves_no_rule` | A rule version whose licence type was recoded after drafting fails re-validation, leaves no rule or version, and records `rule_change.apply_failed` |
| `test_already_decided_is_refused` | A decided proposal refuses a new code request and a decide with an earlier code |
| `test_decision_on_invisible_or_missing_proposal_is_not_found` | A missing proposal is "Rule change not found." |
| `test_audit_order_catalogue_then_rule_change_approved_last` | For each kind the catalogue audit (`proposal_id` and the new row's id) comes before `rule_change.approved` (`proposal_id`, `kind`, `applied_ref`), both by the decider |
| `test_duplicate_type_code_at_insert_is_refused_with_the_exact_message` | A code taken after re-validation is refused by `add_licence_type` and becomes `ProposalInvalid` with the exact message, rolled back and audited `apply_failed` |

### `test_governance_api.py`: rule-change API

| Test | Proves |
|---|---|
| `test_end_to_end_licensing_drafts_head_approves` | The Licensing Authority drafts over HTTP (201, no `drafted_by` in their view), Head A sees the drafter's id and approves with a code, and the new type appears in `/api/catalogue/licence-types` |
| `test_rule_version_shows_current_and_proposed` | `proposed` resolves the licence type, scope and unit; `current` is the latest rule version for that type and scope, or null for a scope with no rule; a superintendent sees the role label only |
| `test_decided_proposal_has_no_live_current` | After approval the detail has `current` null and `proposed` unchanged from the draft |
| `test_threshold_shows_current_and_proposed` | `current` is the latest threshold for the scope, or null when that scope has none |
| `test_owner_sees_drafted_by` | The Software Owner sees the drafter's id and can neither withdraw nor decide |
| `test_list_visibility_status_filter_and_order` | Newest first; authorities see all, a superintendent their own, others none; `?status=` filters, blank means none, unknown is 400; invisible or missing detail is 404 with the fixed message |
| `test_needs_login` | Anonymous gets 403 on the list and on licence types |
| `test_others_may_not_draft` | A taluka-only officer, a licensee and the Software Owner get 403 and nothing is written |
| `test_personnel_without_district_position_gets_the_fixed_message` | The 403 body is the exact drafter message |
| `test_invalid_payload_and_justification_are_422` | Payload and justification problems are 422 with plain reasons, field errors with plain labels |
| `test_unknown_kind_is_400` | An unknown kind is a 400 field error |
| `test_withdraw_over_http` | Someone else 403, invisible 404, the drafter 200 (decision outcome WITHDRAWN), a second withdrawal 409 |
| `test_only_head_may_ask_for_a_decision_code` | Licensing Authority, superintendent and Software Owner get 403 with the exact message |
| `test_head_cannot_decide_own_change` | A Head drafter's own proposal shows `can_decide` false and the code request is 403 with the exact message; a missing id is 404 |
| `test_reject_without_note_is_400_and_keeps_the_code` | A blank or short reject note is a 400 field error on `note`, the code's attempts stay 0, and the same code then rejects |
| `test_decide_input_is_validated` | Unknown outcome, a five-digit code and a 501-character note are 400 and change nothing |
| `test_wrong_code_is_401_and_counts` | A wrong code is 401 with the fixed message, the attempt is kept, the proposal stays SUBMITTED |
| `test_already_decided_is_409` | A decided proposal's code request is 409 with the fixed message |
| `test_code_of_another_user_is_403` | A code issued to another Head officer is 403 "This code belongs to someone else." |
| `test_apply_failure_is_422_and_audited` | A failed apply is 422 with the reason, the proposal stays SUBMITTED and `rule_change.apply_failed` is kept |
| `test_posts_need_csrf` | Drafting and withdrawing without the CSRF header are 403, with it 201 and 200 |

### `test_catalogue_api.py`: catalogue reads

| Test | Proves |
|---|---|
| `test_licence_types_show_latest_rule_versions` | Anonymous 403; types by code with only the latest version of each rule (class and substance scopes, units, limits as strings); a type with no rules has an empty list; a rule with no version is left out |
| `test_classes` | Anonymous 403; classes by code with their unit, null for a class with no substances |

### `test_api_contracts.py`: API contracts for the web app

| Test | Proves |
|---|---|
| `test_shape_helpers` | The shape comparison reports missing and unexpected keys and changed value types (including null becoming a value), and treats an empty list as matching any list |
| `test_contract[<name>]` (57 cases) | Each endpoint the web app uses still answers, as the right role, with the status and shape of its committed contract. Cases: `login_start`, `login_verify`; `me_*` and `home_*` for licensee, personnel, superintendent, licensing authority, head authority and software owner; `transactions_list`, `transaction_created`, `transaction_detail_seller`, `_buyer`, `_buyer_stock_limit` (only REJECT allowed), `_officer` (APPROVE/REJECT), `_officer_two_step` (RECOMMEND/REJECT), `_superintendent_final`, `_authority` (two-step, Head Authority view); `transaction_check_ok`, `transaction_check_refused`, `buyer_lookup`, `decision_code`; `licences_mine`, `stock_mine`; `reason_codes_buyer_rejection`, `_officer_rejection`, `_superintendent_flag`; `catalogue_substances`, `_classes`, `_licence_types`, `_approval_thresholds`; `alerts`, `alert_acknowledged`; `oversight_batches`, `oversight_batch_detail` (a flagged item); `review_settings`, `review_setting_saved`; `rule_changes`, `rule_change_new_licence_type` (drafter's view), `rule_change_rule_version` and `rule_change_threshold` (Head Authority, with `current`), `rule_change_decided`; `licences_register`, `licence_detail`; errors `error_400_field_errors`, `error_400_unknown_filter`, `error_401_wrong_code`, `error_403_not_signed_in`, `error_403_not_allowed`, `error_404_not_found`, `error_409_conflict`, `error_422_transaction_refused` |
| `test_every_contract_file_has_a_case` | No stale contract file (its case renamed or removed) is left serving outdated mocks |

### Frontend tests

Run all: `cd frontend && npm test`. Run one: `npx vitest run src/App.test.tsx`. Every page test includes an axe check; unhandled network requests fail the test.

#### `src/App.test.tsx`: the app shell

| Test | Proves |
|---|---|
| `renders the app name and, signed in, the role's home` | The app mounts with all providers and the browser router, shows "Gujarat Restricted Goods" in the header and sends the (mock) licensee from `/` to `/licensee` |
| `has no accessibility violations` | axe finds no violations on the rendered app |

#### `src/test/render.test.tsx`: the test render helper

| Test | Proves |
|---|---|
| `renders at the given route with translations and route params` | `renderWithProviders` supplies i18n and a memory router at `route` with `path` params, and returns a user-event `user` |
| `renderApp`: `keeps a handler the test set before renderApp ahead of the contract handlers` | A `server.use(...)` override set before `renderApp(…, {contracts})` is the one served (an empty licence list shows "You hold no licences.") |

#### `src/api/client.test.ts`: the API client

| Test | Proves |
|---|---|
| `sends the token on POST and PUT, not on GET` | `X-CSRFToken` (from the cookie the CSRF view set) is on every POST and PUT and never on a GET |
| `fetches the CSRF cookie once` | Concurrent and later writes share one `GET /api/auth/csrf` |
| `tries again after a failed CSRF fetch` | A failed CSRF fetch is an `ApiError` and the next call fetches again |
| `reads the cookie fresh on each request` | A rotated `csrftoken` (as after sign-in) is sent from then on |
| `returns the parsed body`, `returns undefined for 204 No Content` | Successful responses |
| `400 carries field errors`, `400 with only a detail has no field errors` | Field lists become `fieldErrors`; a detail-only 400 keeps the detail |
| `error_401_wrong_code`, `error_404_not_found`, `error_409_conflict` `keeps the status and the server's detail` | Each status maps to an `ApiError` with the server's `detail` |
| `422 carries the reasons` | The refusal's `reasons` list reaches the `ApiError` |
| `429 and 5xx without a JSON body still become ApiErrors` | Throttling and server errors (even an HTML body) map to an `ApiError` with the status |
| `a 403 followed by a failed me calls the expiry handler` | Session expiry is detected and reported once |
| `a 403 followed by a working me does not` | A plain refusal keeps the server's detail and leaves the session alone |
| `a 403 from me itself does not check me again` | No loop when `me` is the failing call |

#### `src/api/contracts.test.ts`: contracts against the hand-written types

| Test | Proves |
|---|---|
| `found the contract files` | The contracts are loaded |
| `<contract name>` (one per file) | Each contract has a type guard and carries every key the guard requires (key lists are typed `satisfies (keyof T)[]`, so a renamed type field fails the type check); lists are non-empty |
| `a buyer over their stock limit may only reject, and the seller never sees the problem` | The captured buyer view allows only REJECT with a problem text; the seller's `stock_limit_problem` is null |
| `field errors are lists of messages` | The 400 contract is a field → messages map |

#### `src/api/hooks/hooks.test.tsx`: query and mutation hooks

| Test | Proves |
|---|---|
| `useHome and useAlerts poll every 30 seconds` | Both queries refetch every `POLL_MS` |
| `serves a contract variant for one test` | `serveContract("transaction_detail_buyer_stock_limit")` overrides the detail endpoint |
| `a decision stores the returned transaction and refetches home and the lists` | `useDecideTransaction` caches the returned detail, refetches home and marks the transaction lists stale |

#### `src/mocks/browser.test.ts`: mock mode

| Test | Proves |
|---|---|
| `every persona names captured contracts` | Each `?as=` persona uses existing contracts |
| `?as= picks the persona and keeps it for the tab; seller by default` | Persona selection, its `sessionStorage` memory and the default |
| `the buyer-stock persona sees a sale over their stock limit` | `?as=buyer-stock` serves `transaction_detail_buyer_stock_limit` |
| `the officer persona is answered as the officer` | `createHandlers(PERSONAS.officer)` serves `me_personnel` |

#### `src/auth/SignInPage.test.tsx`: signing in

| Test | Proves |
|---|---|
| `signs in with a password and a pasted code, then lands on the role's home` | The full flow with MSW: the exact login and verify bodies, focus on the first digit after step 1, a pasted code, `me` refetched, then `/licensee` with the user's name in the header |
| `asks for both fields before calling the server` | Required-field errors are linked to their fields (accessible description) |
| `a wrong password shows the server's detail` | A 401 on step 1 shows "Invalid credentials" as sent |
| `too many tries shows the wait text` | A 429 shows "Too many tries. Wait a minute and try again." |
| `a wrong code shows the 401 text, and Send a new code goes back to step 1` | A 401 on step 2 shows "That code didn't match…", linked to each digit (accessible description) with `aria-invalid`; the user stays on sign-in; going back keeps the user ID and clears the password |
| `shows the session-expired notice after ?expired=1`, `has no expiry notice on a plain visit` | The notice appears (`role="status"`) only after expiry |
| `has no accessibility violations on either step` | axe passes on both steps |

#### `src/auth/SessionProvider.test.tsx`: sign-out and session expiry

| Test | Proves |
|---|---|
| `signing out calls the server, clears drafts and the cache, and goes to sign-in` | `POST /api/auth/logout` is sent, `gj.draft.sale` is removed (other keys stay), the query cache is empty, and the user is on `/sign-in` without the expiry notice |
| `when the session ends, clears drafts and the cache and shows the expiry notice` | A 403 whose `me` check also fails (client expiry handler) clears the draft and the cache and lands on `/sign-in?expired=1` with the notice |

#### `src/auth/RequireRole.test.tsx`: landing and guards

| Test | Proves |
|---|---|
| `the <role> lands on their home` (6 cases) | `/` sends licensee → `/licensee`, officer and superintendent → `/personnel`, Licensing Authority → `/authority`, Head Authority → `/head`, Software Owner → `/overview` |
| `sends a signed-out visitor to sign-in, without an expiry notice` | A guarded page without a session goes to `/sign-in` (no `?expired`, no `?next=`) |
| `sends the wrong role to their own home` | A licensee at `/authority/licences` lands on `/licensee` |
| `lets a role shared screen through (rule changes for personnel)` | `/rule-changes` is open to personnel |
| `sends an unknown path home` | Unknown paths go to `/`, then the role's home |

#### `src/layout/AppShell.test.tsx`: the app shell

| Test | Proves |
|---|---|
| `shows the app name, who is signed in, a skip link and the licensee's links` | Header content, the skip link to `#main`, `<main id="main">`, the licensee's links in order with the current one marked |
| `has no bell for a licensee`, `shows the bell to the Head Authority` | The bell only for personnel and the Head Authority |
| `shows the bell with the unacknowledged count to personnel and opens the drawer` | The count from `home` in the bell's name; clicking opens the Alerts drawer |
| `gives a superintendent the batch and rule-change links`, `gives an area officer no batch links` | Navigation follows the positions held |
| `has a burger to open the navigation on small screens` | The burger is there (shown under 768 px) |
| `has no accessibility violations` | axe passes on the shell with the bell |

#### `src/components/*.test.tsx`: shared components

Every component test file includes an axe check of its main states.

| Test file | Proves |
|---|---|
| `StatusTimeline.test.tsx` (4) | Titles from step and outcome for the two-step authority contract, who acted, the IST time and "Held by" only when sent; a rejection's reason and comment; every step/outcome pair the server sends (cancel, approve, reject) is mapped; a pending step comes last, greyed (`data-pending`); the list is labelled and `aria-live="polite"` |
| `CodeDialog.test.tsx` (9, fake timers) | Opening requests one code and shows 5:00; a full code is submitted with the challenge and `onDone` gets the result; fewer than six digits is refused without calling the server; a 401 shows the wrong-code text linked to the digits, keeps the dialog open and a retry succeeds; another error (403) shows its detail; a failed code request shows "Too many tries…" with Confirm disabled until a new code arrives; "Send a new code" resets the countdown (3:30 → 5:00) and the next submit uses the new challenge; at 0:00 the expiry alert shows and Confirm is disabled until a new code; Escape closes; focus starts on the first digit and Tab stays inside the dialog |
| `ReasonPicker.test.tsx` (7) | Buyer reasons load with `STOCK_LIMIT` hidden by default and shown with `showCodes`; the officer kind loads its own reasons; picking a reason reports a complete value; Other reveals a required comment with `maxlength=500`, incomplete until written; a blank comment is incomplete; `showErrors` links "Choose a reason." and "Describe the reason." to their fields |
| `PermissionCard.test.tsx` (5) | Type and scope, number, status in words, "Can buy / Can sell / Cannot transport" as list text, limits with Indian grouping, validity dates, no banner when usable; the unit when the scope has one; banners for suspended, revoked and expired (`trading_permitted` false) |
| `StatusBadge.test.tsx` (4) | The status label; "Awaiting you" replaces it; every status maps to its tone; rejections are named in words |
| `ErrorNotice.test.tsx` (11) | Nothing without an error; 422 detail and the reasons list from the contract; 400 field-errors text; 401 wrong code; 403 detail or "You can't do this."; 404 never echoes the server; 409 detail; 429 wait; 5xx without the raw status; a network `TypeError` |
| `WhatsNextCard.test.tsx` (3), `EmptyState.test.tsx` (2) | Heading, sentence and one action (a router link that navigates, or a callback); no action renders no button or link |

#### `src/features/licensee/*.test.tsx`: the licensee's home and transactions

| Test | Proves |
|---|---|
| `LicenseeHomePage`: `shows what waits, the licences, the stock and recent transactions` | "2 purchases wait…" linking to `?side=purchases&awaiting=me`, the licence card, the stock table ("400 L"), recent transactions linking to their detail, "New sale" to `/licensee/sale/new`; axe passes |
| `uses the singular for one purchase`, `suggests a new sale when nothing waits`, `says so when there is no stock` | The plural form; "Start a new sale" when nothing waits; the empty stock text |
| `LicenseeTransactionsPage`: `lists the transactions with reference, substance, quantity, other party, status and date` | One row with each column (the buyer as other party for the seller); axe passes |
| `each tab sends its filter`, `opens on the purchases waiting for the viewer from the home link`, `ignores unknown filter values in the address` | Tabs send `""`, `?side=sales`, `?side=purchases`, `?awaiting=me` and set the address; the home link sends both filters with Waiting for you selected; unknown values are not sent |
| `shows an empty state when nothing matches`, `becomes stacked cards under 768 px` | "Nothing waits for your decision."; with a narrow `matchMedia` a labelled list of cards replaces the table; axe passes |

#### `src/features/transactions/TransactionPage.test.tsx`: transaction detail and decisions

| Test | Proves |
|---|---|
| `shows the summary, transport, officer, approval chain, timeline and next action`, `says when the transaction is not found` | Every part of the seller contract in its labelled region, the pending buyer step, the back link; axe passes; a 404 shows "Not found, or not yours to see." (not retried) |
| `the seller can cancel while the sale waits for the buyer, after confirming` | "Keep the sale" posts nothing; "Yes, cancel the sale" posts once, notifies "Sale cancelled." and invalidates home and transactions; axe passes on the modal |
| `cannot cancel once the buyer has acted` | No cancel outside `AWAITING_BUYER` |
| `never sees the buyer's stock, even if the server sent it`, `on the plain contract shows no stock text either` | **Review focus 2:** the seller's page has no "stock" text and no stock figures, even with a leaked `stock_limit_problem`, and no Reject or Confirm |
| `the buyer is offered only the server's outcomes and cannot cancel` | Exactly "Confirm purchase" and "Reject"; "Awaiting you" |
| `confirms through the code dialog` | The code dialog, the posted `{challenge_id, code, outcome: CONFIRM}`, the notification and the invalidation of home and transactions; axe passes |
| `rejects with a reason, the stock limit not among them` | No STOCK_LIMIT reason in the normal state; a reason is required; Other with a comment posts `reason_code` and `comment` |
| `sees the server's reasons when the decision is refused` | A 422 closes the dialog and shows the detail and every reason on the page |
| `over their stock limit`: `sees why, has no confirm button anywhere, and the reason is preset`, `still has no confirm button if the server listed CONFIRM`, `rejects with the stock limit, or another reason if changed`, `can change the preset reason` | **Review focus 2:** the stock-limit sentence, no button named Confirm anywhere, STOCK_LIMIT checked; a defensive filter drops CONFIRM; the reject posts STOCK_LIMIT, or the reason the buyer changed it to; axe passes |
| `Qty.test.tsx` (4), `DateText.test.tsx` (4) | "1,50,000.5 L"; whole, fractional, negative and 17-digit values without precision loss; non-decimals as is; no unit for a mixed-unit scope. A UTC evening is the next IST day, inside `<time datetime>`; the time as "4 Oct 2026, 5:22 pm"; a plain date stays its calendar day; null is "Not set" |


#### `src/features/sale/*.test.ts(x)`: the new-sale wizard

| Test | Proves |
|---|---|
| `sellable.test.ts` (5) | A class licence covers every substance in its class; a substance licence only that substance, never a class of the same name; licences that may not sell, are not trading today or are not active cover nothing |
| `draft.test.ts` (4) | Saved and loaded under `gj.draft.sale`; null for no draft or a damaged one; removed by `clearDraft` and by the sign-out `clearDrafts`; every write goes to sessionStorage, none to localStorage |
| `NewSalePage` step 1: `shows the progress…`, `won't go on until the buyer is found and confirmed…`, `refuses a malformed GSTIN…`, `finds the buyer by a POST body…`, `shows the server's words when no buyer is found`, `moves focus to the next step's heading` | "Step 1 of 4", the GSTIN's format help as its description; Next shows the format error, then "Find the buyer, then confirm…", linked by `aria-describedby` and `aria-invalid`; a short GSTIN posts nothing; the lookup posts `{gstin}` uppercased and the URL never carries it; Yes/Change, Change refocuses the field; a 404 shows the server's detail; the next heading takes focus; axe passes |
| step 2: `offers only the substances…`, `says when no licence lets the seller sell`, `validates the substance and quantity before Next, and needs a check`, `checks the sale: ok lets Next through…`, `says when the superintendent gives final approval`, `lists the reasons when refused, and Next stays blocked`, `a change to the quantity or substance needs a new check`, `Back returns to the buyer with the buyer kept` | Only "Whisky (L)" under a Whisky licence; the no-sale notice; linked field errors and "Check the sale before you continue." on the Check button; the posted `{buyer_gstin, substance_code, quantity}`; the two-step notice only for `OFFICER_THEN_SUPERINTENDENT`; every refusal reason with Next blocked; a changed quantity or substance drops the check; axe passes on ok and refused |
| step 3: `labels every field with help, validates before Next and passes axe` | Each transport field has a description; empty fields and a malformed vehicle number (uppercased as typed) block Next with linked messages |
| step 4: `shows everything, sends, then opens the new transaction and clears the draft`, `on a refusal shows the reasons and a way back to the goods` | Every value in the review region; the full POST body (vehicle uppercased, GSTIN never in the URL); 201 opens `/licensee/transactions/<reference>` with "Sent to the buyer for confirmation." and the draft gone, and still gone after the debounce; a 422 shows the detail and reasons and "Change the goods" returns to step 2 with the check dropped; axe passes |
| drafts: `saves to sessionStorage as the seller types, and restores it`, `restores the step it was on`, `Start over…`, `Discard draft…`, `is cleared on sign-out`, `never writes to localStorage during the whole flow` | **Review focus 3:** the draft appears in sessionStorage after typing and comes back with "Draft restored" (axe passes); a draft on step 3 reopens there; Start over empties the form and storage; Discard draft removes it and goes home; Sign out removes it; over the whole flow to a sent sale every `Storage.setItem` call is on sessionStorage |

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
| Catalogue tables are reference data with no row-level security, written only through `catalogue/service.py`; from D2d a catalogue change reaches the catalogue only through an approved rule-change proposal (ruling D-R12) | Everyone may read the catalogue; writes go through `catalogue/service.py` | Code review |
| Reason codes are data. Add a row, never rename a code | Stored decisions keep pointing at the same meaning | Code review |
| Decision lock order (buyer, officer and superintendent steps alike): user row → OTP challenge rows → transaction row → stock balance rows (sorted by GSTIN index; final approval only, never on a recommendation) → alert inserts → audit (`record()` last). Under the transaction lock `_apply` re-checks the decider and the outcomes offered to them (`decision_role`, `_step_outcomes`) and the buyer's stock limit (buyer step) before any write. Transaction writes happen only through services under SYSTEM. Alert inserts (`alerts.service`) go inside the decision's SYSTEM block, after the decision row and before `record()` | Prevents deadlocks; no path lets a user write a transaction directly | `transactions/migrations/0002_rls_and_append_only.py`, code review |
| Buyer stock-limit rule: the buyer decides on their own stock limit. The seller never sees the buyer's stock numbers: start and the pre-check refuse nothing for the buyer's cap, the cap message (`include_buyer_stock=True`) goes to officers and superintendents only, and `stock_limit_problem` is shown to the buyer only. While the problem exists the buyer may only reject (a CONFIRM is refused with 422 and audited). A `STOCK_LIMIT` rejection is accepted only while the problem exists (one refused under the transaction lock rolls back and is audited `transaction.reject_refused`), raises no alert and is not counted in the pattern | The buyer's stock is the buyer's business; the alert pattern can't be gamed | `test_buyer_stock_limit.py`, `test_d3_apis.py::test_check_endpoint_hides_buyer_stock` |
| Chain rule: the approval chain is fixed at start (`approval_chain_for`: two-step only above the governing threshold) and never changes (no column grant). Every (role, outcome) has one row in `_NEXT`, `_AUDIT` and `_STEP`; on the two-step chain the officer may only recommend or reject; only APPROVE moves stock and every approval or recommendation re-runs the checks first | Severity routing can't be bypassed | `test_two_step_approval.py`, `test_thresholds.py::test_approval_chain_cannot_be_updated_by_app_role` |
| A superintendent's approval is enough (owner decision 2026-10-04, replaces rulings C-R2/C-R5 separation of duties): a holder of both positions approves both levels in one signed step (an OFFICER RECOMMEND and a SUPERINTENDENT APPROVE row, one `transaction.approved` audit with `{"both_levels": true}`); a promoted recommender may give final approval; a superintendent cannot flag in oversight what they gave final approval to (`OWN_APPROVAL`), so the Head Authority reviews superintendent-approved items | One superintendent approval is the senior sign-off; it is never reviewed by the person who gave it | `test_two_step_approval.py::test_dual_holder_approves_both_levels_at_once`, `test_two_step_approval.py::test_dual_holder_reject_is_officer_rejection`, `test_two_step_approval.py::test_promoted_recommender_gives_final_approval`, `test_home_api.py::test_personnel_awaiting_includes_promoted_recommender`, `test_oversight_review.py::test_superintendent_cannot_flag_own_approval`, `test_oversight_review.py::test_dual_holder_approval_is_marked_in_oversight_and_cannot_be_self_flagged` |
| Decisions verify the code BEFORE writing; a wrong code returns (commits the attempt); a refused approval or buyer confirm raises (rolls back its writes) and is audited after the rollback (`approval_refused`, `confirm_refused`; a buyer `STOCK_LIMIT` rejection refused under the lock: `reject_refused`) | A failed guess is counted and a failed approval leaves no half-moved stock | `test_transaction_decisions.py` |
| Periods run back to back from `starts_on`; a batch is created only after its period ends; sign-off is due 30 days later | Predictable, idempotent oversight batches | `test_oversight_batches.py` |
| Oversight lock order: user row → OTP challenge row → per-batch advisory lock → flag/sign-off/alert inserts → audit last (batches are append-only, so no row lock exists) | Flag and sign-off on one batch serialise without deadlock | `test_oversight_review.py`, code review |
| The review setting has no row-level security (configuration, ruling D-R6 style) | Written only through `set_review_period`, which audits every change | `oversight/service.py`, code review |
| Batch-job lock order: job lock (`_lock_batch_job`) → batch/item inserts → audit (all `oversight.batch_created` records at the end); `set_review_period` takes the same job lock first | Concurrent runs and period changes wait instead of racing; no audit lock held while inserting | `test_oversight_batches.py::test_batch_audits_are_written_after_all_batches`, code review |
| Schedule create_due_batches after midnight (about 01:00 IST) so late-evening approvals have committed. | A batch must not miss a just-committed approval | Operations (D4) |
| Demo reset must recreate the database (append-only tables block TRUNCATE). | TRUNCATE triggers reject the reset | Operations (D4) |
| `set_review_period` has no caller check: only the Licensing Authority may set review periods, which the review-settings API enforces (`role_required(LICENSING_AUTHORITY)` on the PUT) | The service trusts its caller; the HTTP layer is the only caller path for people | `test_review_settings_api.py::test_only_licensing_authority_can_change` |
| Maker-checker for rule changes: the drafter never decides their own proposal. Only a Head Authority officer whose `user_id` differs from `drafted_by` decides, with a fresh DECISION code; the rule is checked at the code request, before the code is spent and again under the proposal lock. An approval applies the change in the same SYSTEM block (all or nothing); a failed apply rolls back and is audited `rule_change.apply_failed` after the rollback | One person can't change the rules alone | `governance/service.py`, `test_governance_decisions.py` |
| Rule-change decision lock order: user row → OTP challenge → proposal row (`select_for_update`) → catalogue row (rule or threshold `select_for_update`) → audit (catalogue audit, then `rule_change.approved` last) | Prevents deadlocks between decisions and other catalogue writes | `governance/service.py`, code review |
| Rule-change proposals are written only by SYSTEM through `governance.service` after the plain-Python who-may-act check; `gj_app` may update only the decision columns, a decided proposal is final (trigger, even for the owner) and proposals are never deleted. Audit payloads hold only the proposal id and kind (ruling D-R3) | Only an approved change reaches the catalogue; the record of who proposed and decided what can't be rewritten | `governance/migrations/0002_rls_and_guards.py`, `test_governance.py` |
| Frontend: all user-visible text comes from `src/i18n/en.json` through `t()`; server refusal text (`detail`, `reasons`) is shown as is | One place to review wording and translate later | Typed `t()` keys (`src/i18n/i18next.d.ts`), code review |
| Frontend: only `src/api/` talks to the server; components use the TanStack Query hooks in `src/api/hooks/` | CSRF, error mapping and session expiry live in one place | Code review; MSW `onUnhandledRequest: "error"` in tests |
| Frontend: no `localStorage` (wizard drafts use `sessionStorage` only) and no `dangerouslySetInnerHTML` | No personal data left in the browser; server text renders as plain text | `eslint.config.js` (`no-restricted-syntax`) |
| API contracts: every endpoint the web app calls has a case in `backend/tests/test_api_contracts.py` and a committed `frontend/src/test/contracts/<name>.json`, regenerated only with `UPDATE_CONTRACTS=1` (never edited by hand), built from synthetic fixtures only; the MSW handlers serve these files and `src/api/types.ts` is checked against them | The mocks and types can't drift from the real API without a failing test | `test_api_contracts.py`, `src/api/contracts.test.ts` |
| Frontend: MSW and the mock worker never ship: `src/mocks/browser.ts` is imported dynamically only when `import.meta.env.DEV && VITE_MOCK_API === "1"`, and the build drops `mockServiceWorker.js` | Production never answers with fake data | `vite.config.ts` (`dropMockWorker`), `src/main.tsx`; check `dist/` for `msw` after `npm run build` |
| **Update this file in the same PR** | Keeps the map trustworthy | Code review |

Open follow-ups from the reviews: [`superpowers/plans/2026-09-29-phase1-followups.md`](superpowers/plans/2026-09-29-phase1-followups.md).

