# Demo D2d: Rule Governance, Licence Register and Review-Settings APIs: Implementation Plan

> **For agentic workers:** implement task by task with TDD (write the failing test, see it fail, implement, see it pass). Steps use checkbox (`- [ ]`) syntax. Never push or merge: the controller pushes, and the owner merges.

**Goal:**
1. **Maker-checker rule changes** (Revision 4 R6). Authorities draft a new licence type, a rule version or an approval threshold. A *different* Head Authority user approves or rejects it with a one-time code, and only an approved change reaches the catalogue.
2. **Read APIs for D3:**
   - the licence register (B7)
   - licence types and classes
   - review settings, with a write that only the Licensing Authority can make (B8)

**Spec:**
- [Revision 4](../specs/2026-10-03-routing-and-rule-governance-design.md) §4–5
- [D3 design](../specs/2026-10-03-demo-d3-web-app-design.md) §4 B7–B8 and §3 (Licensing Authority and Head Authority screens)

**Builds on:** D2c (PR #7). This branch is stacked on `feature/demo-d2c-routing` until PR #7 is merged into `dev`.

**Run:** the commands are the same as in the D2c plan (pytest, ruff check/format, makemigrations check). Docker must be up (`export PATH="$HOME/.docker/bin:$PATH"`).

## Global constraints

**Conventions.** All CODEMAP §4 conventions apply:
- Raise to roll back.
- `record()` is the last lock taken; audit payloads hold only IDs, codes and blind indexes.
- Tests use `app_db`.
- RLS goes in the creating migration.
- Every task updates `docs/CODEMAP.md`.

**Where the proposals live.** A new app, `governance`, holds `RuleChangeProposal`. It is separate from `catalogue`, because the proposal lifecycle is not reference data. This is a deliberate refinement of the spec's "`catalogue.RuleChangeProposal`"; note it in the spec in Task 6.

**Kinds and payloads** (JSON, validated by a per-kind serializer at draft time and again at apply):

| Kind | Payload |
|---|---|
| `NEW_LICENCE_TYPE` | `{"code": "^[A-Z][A-Z0-9_]{1,31}$", "name": str ≤100, "description": str ≤500 (may be blank)}`. The code must not exist yet. |
| `RULE_VERSION` | `{"licence_type_code", exactly one of "substance_code" / "class_code", "may_buy", "may_sell", "may_transport", "max_stock_qty" > 0, "max_per_transaction_qty" > 0 and ≤ max_stock_qty, "validity_months" 1–120}`. The licence type and scope must exist. A rule for (type, scope) is created on apply if missing. |
| `APPROVAL_THRESHOLD` | `{exactly one of "substance_code" / "class_code", "superintendent_above_qty" > 0}`. |

Quantities are stored in the payload as strings (Decimal-safe).

**Proposal status:** `SUBMITTED` → `APPROVED` / `REJECTED` / `WITHDRAWN`. All three are final.

**Who may act:**

| Action | Allowed | Notes |
|---|---|---|
| Draft | `LICENSING_AUTHORITY`, `HEAD_AUTHORITY`, or `PERSONNEL` currently holding a `DISTRICT`-level position | A `justification` of 10–1000 characters is required. |
| Withdraw | The drafter, while the proposal is `SUBMITTED` | No code needed. |
| Approve / reject | A `HEAD_AUTHORITY` user whose `user_id` ≠ `drafted_by` | A fresh `DECISION` code is required. A reject needs a `decision_note` (10–500). An approve's note is optional. |
| Read | The drafter (own proposals); `HEAD_AUTHORITY`, `SOFTWARE_OWNER`, `LICENSING_AUTHORITY` and SYSTEM (all proposals) | Enforced by RLS. |

**Database rules for proposals:**
- **Writes:** SYSTEM only, through services, after the plain-Python who-may-act check.
- **Updates:** `gj_app` may update only `status`, `decided_by`, `decided_at`, `decision_note` and `applied_ref`. Grant UPDATE on those columns only. No DELETE or TRUNCATE (REVOKE).
- **After a decision:** a row that is no longer `SUBMITTED` cannot change, enforced by a trigger. Write a dedicated `reject_decided_proposal_change()` function that raises when `OLD.status <> 'SUBMITTED'`.

**Applying a change on approval:**
- It happens in the same SYSTEM block as the decision, through `catalogue.service`:
  - `add_licence_type(code, name, description, created_by)` (new)
  - `add_rule_version` (existing; create the rule first if missing)
  - `add_threshold_version` (D2c)
- **On failure:** if applying fails validation (for example, the code now exists or a substance was removed), raise `ProposalInvalid(reasons)`. Everything rolls back, the proposal stays `SUBMITTED`, and `rule_change.apply_failed` is audited after the rollback, mirroring `approval_refused`.
- **Unaffected:** existing licences keep their frozen permissions, and transactions in flight keep their chain.

**Audit actions** (payload `{"proposal_id": id, "kind": kind}` plus `applied_ref` on approval):
- `rule_change.drafted`
- `rule_change.withdrawn`
- `rule_change.approved`
- `rule_change.rejected`
- `rule_change.apply_failed`

The approval also writes the catalogue audit `catalogue.licence_type_added`, `catalogue.rule_version_added` or `catalogue.threshold_version_added`. Then `rule_change.approved` is recorded last.

**Lock order:** user row → OTP challenge → proposal row (`select_for_update`) → catalogue row (rule or threshold `select_for_update`) → audit.

**Exact messages:**

| Situation | Message |
|---|---|
| Not a drafter | "Only the Licensing Authority, a district superintendent or the Head Authority can draft rule changes." |
| Own approval | "You drafted this change, so another Head Authority officer must decide it." |
| Not Head | "Only the Head Authority can approve or reject rule changes." |
| Already decided | "This change has already been decided." |
| Withdraw by someone else | "Only the officer who drafted this change can withdraw it." |
| Reject without note | "Say why you are rejecting this change." (400, field error) |
| Type code exists | "A licence type with code {code} already exists." |
| Unknown licence type | "No licence type has code {code}." |
| Unknown substance | "No substance has code {code}." |
| Unknown class | "No substance class has code {code}." |
| Per-transaction limit above stock limit | "The per-transaction limit can't be above the stock limit." |

**Licence register (B7):**
- **Who:** `role_required(LICENSING_AUTHORITY, HEAD_AUTHORITY, SOFTWARE_OWNER)`.
- **Search:** `?number=` or `?gstin=` (exact, through the blind index, normalised like `find_by_number`). Optional filters `?status=` and `?area=<area id>`, and `?page=` (25 per page, 1-based).
- **Audit:**
  - searches are audited as `licence.register_search` with `{"number_index"|"gstin_index": ..., "results": n}`
  - unfiltered listing is not audited
  - the detail view is audited as `licence.viewed` (`subject_id` is the licence id)
- **List row:** `id`, `licence_number`, `holder_name`, `licence_type`, `scope`, `area`, `status`, `valid_to` (the latest period's `ends_on`).
- **Detail:** adds `gstin`, `periods` (`[{starts_on, ends_on}]` sorted) and `permissions` (the `licence_card` permission fields). **Never** the contact or stock.

**Review settings (B8):**
- `GET /api/oversight/review-settings`: `role_required(LICENSING_AUTHORITY, HEAD_AUTHORITY, SOFTWARE_OWNER)`. For every DISTRICT-level position (by id) it returns `{position_id, title, area, period_days|null, starts_on|null, current_period_end|null, last_batch_end|null}`.
- `PUT /api/oversight/review-settings/<position_id>`: `role_required(LICENSING_AUTHORITY)` only. The body is `{period_days, starts_on?}` and it calls `set_review_period(by=user.user_id)`.
  - Unknown position: 404.
  - `InvalidSetting`: 422 `{"detail": "This review period can't be saved.", "reasons": [..]}`. Give `InvalidSetting` a `reasons` list, as `TransactionRefused` has; never use `str(exc)`.
- This closes the CODEMAP §4 note that the service trusts its caller.

## Review focus

1. **No self-approval.** A Head Authority drafter cannot decide their own proposal, even with a valid code from elsewhere. *(Task 2)*
2. **All or nothing.** An approval whose apply fails leaves no catalogue rows and no status change. It is audited after the rollback. *(Task 2)*
3. **Frozen once decided.** A decided proposal is unchangeable even for the table owner, and `gj_app` can update only the listed columns. *(Task 1)*
4. **Proposal visibility.** A superintendent sees only their own proposals; a licensee and other personnel see none. *(Task 1)*
5. **Licence register.** It never returns contact or stock, and searches never put the raw number or GSTIN in the audit log. *(Task 4)*

## File structure

| File | Purpose |
|---|---|
| `governance/` (new app: `apps.py`, `models.py`, `payloads.py`, `service.py`, `presenters.py`, `serializers.py`, `views.py`, `urls.py`, `migrations/0001_initial.py`, `migrations/0002_rls_and_guards.py`) | Proposals |
| `catalogue/service.py` | `add_licence_type` |
| `catalogue/views.py`, `catalogue/urls.py` | `GET /api/catalogue/licence-types`, `GET /api/catalogue/classes` |
| `licensing/views.py`, `licensing/urls.py`, `licensing/register.py` (new) | B7 |
| `oversight/views.py`, `oversight/urls.py`, `oversight/serializers.py`, `oversight/service.py` | B8, `InvalidSetting.reasons` |
| `core/home.py` | New counts |
| `config/settings.py` | `INSTALLED_APPS` |
| `config/urls.py` | Routes |
| Tests (new) | `test_governance.py`, `test_governance_decisions.py`, `test_governance_api.py`, `test_licence_register.py`, `test_review_settings_api.py`, `test_catalogue_api.py` |

---

### Task 1: Proposal model, drafting and withdrawal

**Model.** `RuleChangeProposal` has these fields:
- `kind` (choices; check constraint)
- `payload` (JSONField)
- `justification` (TextField)
- `drafted_by` (CharField 12)
- `drafted_role` (CharField 32)
- `drafted_at` (auto)
- `status` (choices; default SUBMITTED; check constraint)
- `decided_by` (CharField 12, blank)
- `decided_at` (null)
- `decision_note` (TextField, blank)
- `applied_ref` (CharField 64, blank)

**Migration `0002`:**
- **RLS:**
  - read for the drafter (`drafted_by = app.user_id`), for the roles HEAD_AUTHORITY, SOFTWARE_OWNER, LICENSING_AUTHORITY and SYSTEM
  - insert and update for SYSTEM only
- **Grants:** column-level UPDATE grants, and REVOKE DELETE and TRUNCATE.
- **Triggers:**
  - a decided-row trigger (`reject_decided_proposal_change`)
  - the shared no-delete and no-truncate triggers
- The migration is reversible.

**`governance/payloads.py`:**
- `validate_payload(kind, payload) -> dict` returns the cleaned payload (strings for decimals) or raises `ProposalInvalid(reasons)`.
- It checks existence (licence type, substance, class) and the rules in the table above.
- It is used at draft time and at apply.

**`governance/service.py`:**
- `draft(*, user, kind, payload, justification) -> RuleChangeProposal` checks the drafter rule, validates the payload, inserts as SYSTEM, and audits.
- `withdraw(*, proposal_id, user)`: the proposal is loaded under the caller's RLS (None means not found), then locked; only the drafter, and only while SUBMITTED.
- `may_draft(user) -> bool` is public, because the presenter and home use it.

**Tests (`test_governance.py`):**
- [ ] `test_licensing_authority_head_and_district_superintendent_may_draft`: parametrise over the three, plus refusals for a taluka-only officer, a licensee and a software owner (exact message)
- [ ] `test_payload_validation_messages`: each exact message, including a duplicate code, unknown codes, a per-transaction limit above the stock limit, and both or neither scope
- [ ] `test_justification_required`: 10–1000 characters
- [ ] `test_draft_is_audited_without_payload_values`: the audit payload has only id and kind
- [ ] `test_withdraw_rules`: only the drafter, only while submitted, audited
- [ ] `test_visibility`:
  - a superintendent sees their own proposals and not another drafter's
  - the Licensing Authority and Head Authority see all
  - a licensee and taluka personnel see none
- [ ] `test_decided_proposal_cannot_change_even_for_owner`: `gj_owner` update after APPROVED raises
- [ ] `test_app_role_can_update_only_decision_columns`: updating `payload` as SYSTEM under `gj_app` raises a privilege error
- [ ] `test_proposals_cannot_be_deleted`

**Steps:**
- [ ] TDD
- [ ] add the app to `INSTALLED_APPS`
- [ ] run the full suite green, ruff, and the makemigrations check
- [ ] update the CODEMAP: a new section for `governance`; the roles table (Licensing Authority, Personnel superintendent, Head Authority); the test catalogue
- [ ] commit `feat: rule-change proposals — drafting, withdrawal, RLS and decided-row guard`

### Task 2: Decide with a one-time code, and apply

**`governance/service.py`:**
- `request_decision_code(*, proposal_id, user) -> OtpChallenge` checks Head, not drafter and SUBMITTED, then issues a DECISION code.
- `decide(*, proposal_id, user, challenge_id, code, outcome, note) -> RuleChangeProposal | None`:
  1. **Checks before the code is used:** outcome in {APPROVE, REJECT}; who may act; a note for REJECT.
  2. **Code:** a wrong code returns None (the attempt counts). A signer other than the user raises NotAllowed.
  3. **SYSTEM block:**
     - lock the proposal and re-check SUBMITTED and the decider rule
     - on APPROVE, re-validate the payload and apply it through `catalogue.service`
     - set the decision columns, then audit last
  4. **On `ProposalInvalid` during apply:** the block rolls back, then `rule_change.apply_failed` is recorded and the exception re-raised.
- `apply_change(proposal, by) -> str` returns `applied_ref`:
  - `licence_type:<id>`
  - `rule_version:<id>`
  - `threshold_version:<id>`

**`catalogue/service.py`:** `add_licence_type(*, code, name, description, created_by) -> LicenceType`, plus the catalogue audits listed above. These are called inside the decision's SYSTEM block, before `rule_change.approved`.

**Tests (`test_governance_decisions.py`):**
- [ ] `test_approve_new_licence_type_applies_it`
- [ ] `test_approve_rule_version_creates_rule_if_missing_and_versions_existing`
- [ ] `test_approve_threshold_changes_new_transactions_only`: a transaction in flight keeps its chain; a new one gets the new chain
- [ ] `test_existing_licence_permissions_unchanged_after_rule_change`
- [ ] `test_reject_needs_note_and_changes_nothing`
- [ ] `test_drafter_cannot_decide_own_change`: a Head drafter is refused at the code request, and also when spending a valid code obtained elsewhere (exact message); nothing changes
- [ ] `test_only_head_can_decide`
- [ ] `test_wrong_code_counts_and_changes_nothing`
- [ ] `test_apply_failure_rolls_back_and_is_audited`: the same type code is approved twice through two proposals; the second leaves no rows, stays SUBMITTED, and is audited `apply_failed`
- [ ] `test_already_decided_is_refused`
- [ ] `test_audit_order_catalogue_then_rule_change_approved_last`

**Steps:**
- [ ] TDD, run the suite green
- [ ] update the CODEMAP: lock-order convention row; maker-checker convention row
- [ ] commit `feat: Head Authority approves rule changes with a one-time code; all-or-nothing apply`

### Task 3: Governance API, catalogue reads, home counts

**Routes:**
- `GET /api/rule-changes` (any logged-in user; RLS scopes the rows; `?status=` filter; newest first; maximum 100)
- `POST /api/rule-changes` (draft; drafter roles via `role_required(LICENSING_AUTHORITY, HEAD_AUTHORITY, PERSONNEL)` plus the service check)
- `GET /api/rule-changes/<id>` (404 when not visible)
- `POST /api/rule-changes/<id>/withdraw`
- `POST /api/rule-changes/<id>/decision-code` (`otp` throttle)
- `POST /api/rule-changes/<id>/decide` (`otp` throttle)

**Status codes:**
- not allowed: 403 with a fixed message per case (use a `code` attribute on `NotAllowed` subclasses, or constants, so `str(exc)` is never used)
- `ProposalInvalid`: 422 with `reasons`
- wrong code: 401
- already decided: 409

**Presenter `proposal_view(p, viewer)`:**
- `id`, `kind`, `kind_label`, `status`, `justification`, `drafted_at`
- `drafted_by_role`. Show the role label, not the user id, unless the viewer is HEAD_AUTHORITY or SOFTWARE_OWNER; then also `drafted_by`.
- `proposed`: the cleaned payload, with display names resolved
- `current`: the latest existing values for the same scope (rule version or threshold), or null. This drives the before/after view in D3.
- `decision`: `{outcome, decided_at, note}` or null
- `can_withdraw`, `can_decide`

**Catalogue reads (any logged-in user):**
- `GET /api/catalogue/licence-types` returns `[{code, name, description, rules: [{scope, scope_kind, unit, version, may_buy, may_sell, may_transport, max_stock_qty, max_per_transaction_qty, validity_months}]}]`, with the latest version per rule.
- `GET /api/catalogue/classes` returns `[{code, name, unit}]`.

**`core/home.py`:**
- HEAD_AUTHORITY: `rule_changes_awaiting_you` (SUBMITTED, not drafted by them).
- Every drafter: `your_open_rule_changes` (their own SUBMITTED). For PERSONNEL, only when `may_draft`.
- LICENSING_AUTHORITY additionally gets `rule_changes_submitted` (all SUBMITTED).

**Tests:**
- `test_governance_api.py`: an end-to-end HTTP flow (the Licensing Authority drafts, Head A decides over HTTP, the catalogue changes), status codes, CSRF on POST, visibility over HTTP, `current` vs `proposed`, and that `drafted_by` is hidden from the Licensing Authority.
- `test_catalogue_api.py`
- Additions to `test_home_api.py`

**Steps:**
- [ ] TDD
- [ ] update the CODEMAP: URL row; roles table "Any logged-in user"
- [ ] commit `feat: rule-change and catalogue APIs; home counts for proposals`

### Task 4: Licence register (B7)

**`licensing/register.py`:**
- `search(user, *, number=None, gstin=None, status=None, area_id=None, page=1) -> (rows, total)`, which audits searches
- `detail(user, licence_id) -> dict | None`, which audits the view
- Runs under the caller's RLS (these roles read all licences).
- Uses `licence_card` fields for the permissions.

**Views and routes:** `GET /api/licences` and `GET /api/licences/<int:licence_id>`. Keep `licences/mine` working and add the routes so `mine` isn't captured.
- An invalid page or status gives 400 "Unknown filter value."
- The response is `{"count", "page", "page_size": 25, "results": [...]}`.

**Tests (`test_licence_register.py`):**
- [ ] `test_only_authorities_can_use_register`: Licensing Authority, Head Authority and Software Owner get 200; a licensee and personnel get 403
- [ ] `test_exact_search_by_number_and_gstin`: case and spaces are normalised, and partial input finds nothing
- [ ] `test_filters_and_pagination`
- [ ] `test_detail_has_periods_and_permissions_but_no_contact_or_stock`: scan the JSON for the contact digits and the stock quantity
- [ ] `test_search_and_view_are_audited_by_blind_index_only`

**Steps:**
- [ ] TDD
- [ ] update the CODEMAP
- [ ] commit `feat: licence register API for authorities (exact search, audited)`

### Task 5: Review-settings API (B8)

**`oversight/service.py`:**
- `InvalidSetting(reasons: list[str])`, with every existing raise site updated.
- `review_settings_overview(today) -> list[dict]`, run as SYSTEM, because batches are hidden from the Licensing Authority by RLS and only dates are returned. Comment why.

**Views, serializer, routes:** as described in the global constraints.

**Tests (`test_review_settings_api.py`):**
- [ ] `test_overview_lists_every_district_position`: with and without a setting; batch dates are correct
- [ ] `test_only_licensing_authority_can_change`: a PUT from Head Authority, Software Owner or Personnel gets 403; GET is allowed for the three authority roles
- [ ] `test_change_is_saved_and_audited`
- [ ] `test_invalid_period_is_422_with_reasons`: covers 20 days, a taluka position, and a start that would skip days
- [ ] `test_unknown_position_is_404`
- [ ] Existing oversight tests stay green after the `InvalidSetting` change.

**Steps:**
- [ ] TDD
- [ ] update the CODEMAP; the §4 "service trusts its caller" row now says the API enforces the Licensing Authority role
- [ ] commit `feat: review-settings API; only the Licensing Authority changes periods`

### Task 6: CODEMAP sweep, spec note, follow-ups

- [ ] Run the coverage scripts from the D2c Task 6, for files and test names. Both must print nothing.
- [ ] Update "Last updated" with the real test count.
- [ ] Add a note to spec Revision 4 §4: the model lives in the `governance` app.
- [ ] Add a "D2d" section to `docs/superpowers/plans/2026-09-29-phase1-followups.md` listing anything deferred, plus:
  - D4: seed one approved and one pending proposal, and two Head Authority users so the maker-checker flow can be demoed
  - D3: the before/after diff screen uses `current` / `proposed`
- [ ] Commit `docs: D2d CODEMAP sweep and follow-ups`.

## Spec coverage (D2d)

| Item | Task |
|---|---|
| R6 drafting roles, maker-checker, code, apply all or nothing, frozen licences | 1, 2 |
| R6 read rules | 1, 3 |
| D3 B7 register | 4 |
| D3 B8 review settings (Licensing Authority only) | 5 |
| Licence types and classes for D3 drafting forms | 3 |
