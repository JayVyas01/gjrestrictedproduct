# Demo D2c: Severity Routing, Buyer Stock Limit and D3 APIs Implementation Plan

> **For agentic workers:** implement task by task with TDD (write the failing test, see it fail, implement, see it pass). Steps use checkbox (`- [ ]`) syntax. Never push or merge: the controller pushes, and the owner merges.

**Goal:**
1. **Approval threshold.** A quantity threshold per substance or class decides whether the area officer alone approves, or the officer recommends and the superintendent gives final approval.
2. **Buyer stock limit.** The seller is never refused because of the buyer's stock limit. The buyer sees the problem and can only reject; the rejection raises no alert and doesn't count toward the pattern.
3. **Oversight.** Superintendent-approved items are marked in batches and can't be flagged.
4. **D3 APIs.** The read and filter APIs the web app needs (B1–B4) and the B6 message fix.

**Spec:** [Revision 4](../specs/2026-10-03-routing-and-rule-governance-design.md) §1–3 and §5 (D2c row); [D3 design](../specs/2026-10-03-demo-d3-web-app-design.md) §4 B1–B4 and B6. **Builds on:** `dev` after PR #6.

**Tech stack:** Django 5.2, DRF 3.17, PostgreSQL 16, pytest-django.

**Run tests:**
- all: `cd backend && uv run --env-file .env.test pytest -q`
- lint: `uv run ruff check . && uv run ruff format --check .`
- migrations: `uv run --env-file .env.test python manage.py makemigrations --check --dry-run`

Docker must be running: `export PATH="$HOME/.docker/bin:$PATH"; docker compose up -d db` from the repository root.

## Global constraints

Every convention in `docs/CODEMAP.md` §4 applies. In brief:
- **Rollback:** raise to roll back, return to commit.
- **Audit:** `record()` takes the last lock. Audit payloads hold IDs and blind indexes only.
- **Tests:** tests use `app_db`.
- **Append-only tables:** REVOKE plus `reject_append_only_change()` triggers.
- **Row-level security:** policies go in the migration that creates the table.
- **CODEMAP:** every task updates `docs/CODEMAP.md` (roles table, the file rows and the test catalogue).

**Lock order is unchanged:** user row → OTP challenge → transaction row → stock rows (sorted) → alert inserts → audit.

**Approval chain**
- `Transaction.approval_chain` is either `OFFICER` or `OFFICER_THEN_SUPERINTENDENT`. It is resolved at **start** and never changes.
- **Rule:** the chain is `OFFICER_THEN_SUPERINTENDENT` when `quantity > superintendent_above_qty` of the governing threshold. When no threshold exists, the chain is `OFFICER`.
- **Which threshold governs:** a substance threshold beats a class threshold.

**Statuses** (add these): `AWAITING_SUPERINTENDENT` ("Waiting for the superintendent") and `REJECTED_BY_SUPERINTENDENT` ("Rejected by the superintendent").

**Steps and outcomes** (add these): step `SUPERINTENDENT` ("Superintendent") and outcome `RECOMMEND` ("Recommended for approval"). Widen the columns: `status` to 32, `step` to 16, `outcome` to 12.

**Officer step on the two-step chain**
- The officer's outcomes are `RECOMMEND` or `REJECT`. On the `OFFICER` chain they stay `APPROVE` or `REJECT`.
- `RECOMMEND` re-runs every check, including the buyer stock cap, **but moves no stock**. Status becomes `AWAITING_SUPERINTENDENT` and `decided_at` stays null.

**Superintendent step**
- **Who:** the current holder of `tx.superintendent_position`, with outcomes `APPROVE` or `REJECT`. A rejection needs an `OFFICER_REJECTION` reason.
- **Approval:** `APPROVE` does exactly what the officer approval does today: re-check everything, move stock, set `decided_at`.
- **Separation of duties:** if the user who made the officer decision tries this step, refuse with `NotAllowed("You made the officer decision on this transaction; another officer must give final approval.")`.

**Buyer stock limit**
- `start_transaction` and the new dry-run check **no longer check the buyer's stock cap**.
- New `transactions.checks.buyer_stock_problem(tx) -> str | None`. It returns `f"Confirming would take your {substance} stock to {after} {unit}, above your licence limit of {max} {unit}. You can only reject this sale."`
- **CONFIRM** while that problem exists is refused (422) with that sentence. The check runs inside the decision's SYSTEM block under the transaction lock.
- **Reason code:** new buyer-rejection reason `STOCK_LIMIT` ("This would take me over my licence's stock limit"), added by a data migration.
  - **Default:** a buyer REJECT with a blank reason code while the problem exists uses `STOCK_LIMIT`.
  - **Refusal:** choosing `STOCK_LIMIT` when no problem exists gets `InvalidReason("Your stock limit allows this sale, so choose another reason.")`.
- **Alerts and pattern:**
  - a `STOCK_LIMIT` rejection raises **no alerts**, and its audit payload is `{"alerts_raised": 0}`
  - `_recent_rejections` **excludes** transactions whose buyer decision reason code is `STOCK_LIMIT`
- **Officer approval** (OFFICER chain) and superintendent approval still check the buyer's cap, with the existing wording and the numbers. Only authorities see those.

**Messages, exactly as given**
- `next_action`:
  - AWAITING_SUPERINTENDENT: "Waiting for the superintendent's final approval."
  - the viewer's own turn: "Your decision is needed." (unchanged)
- Flag refused on a superintendent-approved item: "You approved this transaction; the Head Authority reviews it."
- B6:
  - not the holder: "Only the officer holding this position can acknowledge this alert."
  - already acknowledged: "This alert is already acknowledged."

**Out of scope:** rule-change proposals, licence register, review-settings APIs (D2d), screens (D3), seed data (D4).

## Review focus

1. **Order of the two approvals.** On the two-step chain, the officer recommend moves no stock. Only the superintendent's approval moves it, and it re-checks everything first. *(Task 2: `test_two_step_chain_moves_stock_only_on_final_approval`)*
2. **Same person at both steps.** The person who made the officer decision cannot give the final approval, even if they also hold the district position. *(Task 2: `test_officer_cannot_also_give_final_approval`)*
3. **The seller never sees the buyer's stock.** Not at start, not in the check endpoint, not on the timeline. *(Task 3: `test_seller_never_sees_buyer_stock`)*
4. **A stock-limit rejection is invisible to the pattern.** It raises no alert, and later rejections are counted without it. *(Task 3: `test_stock_limit_rejection_raises_no_alert_and_is_not_counted`)*
5. **Superintendent-approved items in batches.** They are marked and can't be flagged. *(Task 4)*

## File structure

| File | Change |
|---|---|
| `catalogue/models.py`, `catalogue/service.py`, `catalogue/migrations/0005_approval_thresholds.py` | `ApprovalThreshold`, `ApprovalThresholdVersion` (append-only), `resolve_threshold`, `add_threshold_version`, `approval_chain_for` |
| `transactions/models.py`, `transactions/migrations/0005_approval_chain.py` | New statuses, step, outcome, `ApprovalChain`, `approval_chain` field, wider columns |
| `transactions/checks.py` | Buyer cap removed from `transaction_problems` unless `include_buyer_stock=True`; `buyer_stock_problem` |
| `transactions/service.py` | Chain at start, superintendent step, recommend, buyer stock-limit rules, `allowed_outcomes`, `check_transaction` (B4) |
| `transactions/presenters.py` | Chain, allowed outcomes, buyer-only `stock_limit_problem`, timeline for both approvals |
| `reasons/migrations/0003_stock_limit_reason.py` | Seeds `BUYER_REJECTION / STOCK_LIMIT` |
| `alerts/service.py`, `alerts/views.py` | No alert for STOCK_LIMIT, pattern exclusion; `AlreadyAcknowledged` (B6) |
| `oversight/presenters.py`, `oversight/service.py` | Approval decision generalised; `approved_by_superintendent`; flag refusal |
| `identity/views.py` | `/me` with `display_name` and `positions` (B1) |
| new `home/` app *or* `core/home.py` + route | `GET /api/home` (B2). Use `core/home.py` plus a view in `core/views.py` (no new app, no models) |
| `transactions/views.py`, `transactions/urls.py`, `transactions/serializers.py` | List filters (B3), `POST /api/transactions/check` (B4) |
| `catalogue/views.py`, `catalogue/urls.py` (new) | `GET /api/catalogue/approval-thresholds` |
| `tests/` | New: `test_thresholds.py`, `test_two_step_approval.py`, `test_buyer_stock_limit.py`, `test_home_api.py`, `test_d3_apis.py`; existing tests updated where wording or shapes change |

---

### Task 1: Approval thresholds and the transaction model

**Files:**
- `catalogue/models.py`, `catalogue/service.py`, `catalogue/migrations/0005_approval_thresholds.py`
- `transactions/models.py`, `transactions/migrations/0005_approval_chain.py`
- `tests/test_thresholds.py`
- `docs/CODEMAP.md`

**Models**
- `ApprovalThreshold` has `substance` (nullable FK) and `substance_class` (nullable FK), with exactly one set. Constraint name: `threshold_exactly_one_scope`. It has unique partial constraints per substance and per class, and no other fields.
- `ApprovalThresholdVersion` has:
  - `threshold` (FK, `related_name="versions"`)
  - `version` (positive integer; unique per threshold)
  - `superintendent_above_qty` (Decimal 12,3; check `> 0`, constraint `threshold_qty_positive`)
  - `created_at`
  - `created_by` (CharField 64)
- **Migration `0005`:** creates both tables. Versions are append-only: REVOKE UPDATE, DELETE and TRUNCATE from `gj_app`, plus the row and statement `reject_append_only_change()` triggers (copy the pattern of `0002` and `0003`). Make it reversible. There is no RLS: thresholds are reference data, per ruling D-R12.

**Service (`catalogue/service.py`)**
- `resolve_threshold(substance) -> ApprovalThresholdVersion | None`: the latest version of the substance's threshold, else the latest of its class, else None.
- `add_threshold_version(*, substance=None, substance_class=None, superintendent_above_qty, created_by) -> ApprovalThresholdVersion`:
  - get or create the threshold
  - `select_for_update` it
  - write version = latest + 1
- `approval_chain_for(substance, quantity) -> str` returns `"OFFICER_THEN_SUPERINTENDENT"` when `quantity > resolve_threshold(substance).superintendent_above_qty`, else `"OFFICER"`.

**Transactions (`transactions/models.py`)**
- Add the two statuses, the `SUPERINTENDENT` step and the `RECOMMEND` outcome. Widen the columns as listed in the global constraints.
- `class ApprovalChain(TextChoices)`: `OFFICER` = "Officer", `OFFICER_THEN_SUPERINTENDENT` = "Officer, then superintendent".
- `approval_chain` is a CharField of length 32 with those choices and default `OFFICER`. Add a check constraint `transaction_chain_valid`.
- **Migration `0005`:**
  - existing rows get `OFFICER`
  - Django regenerates `transaction_status_valid`
  - `GRANT UPDATE (status, decided_at)` is unchanged, because `approval_chain` must not be updatable by `gj_app`
  - add a test that it can't be updated

**Tests (`tests/test_thresholds.py`)**
- [ ] `test_no_threshold_means_officer_chain`
- [ ] `test_class_threshold_applies_to_its_substances`: Spirits above 200, so Whisky at 201 gives the two-step chain and 200 gives the officer chain
- [ ] `test_substance_threshold_beats_class`: Whisky 100, Spirits 500, so Whisky at 150 is two-step
- [ ] `test_latest_threshold_version_wins`
- [ ] `test_threshold_needs_exactly_one_scope`
- [ ] `test_threshold_qty_must_be_positive`
- [ ] `test_threshold_versions_are_append_only_even_for_owner`: update as the owner raises
- [ ] `test_approval_chain_cannot_be_updated_by_app_role`: as SYSTEM under `gj_app`, `Transaction.objects.update(approval_chain=...)` raises a privilege error

**Steps**
- [ ] Write the tests and run them to see the failures.
- [ ] Implement the models, migrations and service.
- [ ] Run the full suite: all green. Run ruff and the makemigrations check.
- [ ] Add the CODEMAP rows (catalogue table, transactions model and migration, test catalogue).
- [ ] Commit `feat: approval thresholds and approval chain on transactions`.

---

### Task 2: Routing at start and the two-step approval

**Files:**
- `transactions/service.py`, `transactions/presenters.py`
- `tests/conftest.py` (add a `threshold` fixture and extend `settle`)
- `tests/test_two_step_approval.py`
- existing transaction tests where shapes change
- `docs/CODEMAP.md`

**Service**
- **`start_transaction`:** sets `approval_chain=approval_chain_for(substance, quantity)`, inside the existing SYSTEM block.
- **`decision_role`:** adds `"superintendent"` when `status == AWAITING_SUPERINTENDENT` and `tx.superintendent_position in positions_held(user)`.
- **`allowed_outcomes(tx, role) -> set[str]`**, public, used by `decide` and the presenter:

  | Role | Allowed outcomes |
  |---|---|
  | buyer | `{CONFIRM, REJECT}`, or just `{REJECT}` when a buyer stock problem exists (Task 3 adds that part) |
  | officer | `{APPROVE, REJECT}` on the OFFICER chain; `{RECOMMEND, REJECT}` on the two-step chain |
  | superintendent | `{APPROVE, REJECT}` |

- **`_REASON_KIND`:** superintendent maps to `OFFICER_REJECTION`.

**`_apply`**
- **Officer `RECOMMEND`:** re-run the same checks as `_approve`, including the buyer cap with `include_buyer_stock=True`, without `transfer`. Set status `AWAITING_SUPERINTENDENT`. The decision row records `position=designated_position`. Audit `transaction.recommended`.
- **Superintendent:**
  - first check that no OFFICER-step decision on this transaction has `actor_user_id == user.user_id`; if one does, raise the separation-of-duties `NotAllowed`
  - `APPROVE`: `_approve(locked)`; status `APPROVED`; `decided_at` set; audit `transaction.approved`
  - `REJECT`: status `REJECTED_BY_SUPERINTENDENT`; `decided_at` set; audit `transaction.superintendent_rejected`
  - the decision row has step `SUPERINTENDENT` and `position=superintendent_position`
- Replace the `_NEXT` and `_AUDIT` dicts so that `(role, outcome)` covers every case, and keep them readable.
- `decided_at` is set for every final status: not `AWAITING_OFFICER`, and not `AWAITING_SUPERINTENDENT`.

**Presenters**
- `_NEXT_ACTION` adds AWAITING_SUPERINTENDENT with the exact message.
- `_next_action` returns "Your decision is needed." for `(AWAITING_SUPERINTENDENT, "superintendent")`.
- The detail adds:
  - `"approval_chain"`
  - `"approval_chain_label"`
  - `"allowed_outcomes"`: a sorted list, empty when `can_decide` is false
- **Timeline:** `held_by` is shown to authorities for the `OFFICER` and `SUPERINTENDENT` steps. `by` is the decision's position title, as now.

**Conftest**
- `threshold` fixture: `add_threshold_version(substance_class=catalogue.spirits, superintendent_above_qty=Decimal("200"), created_by="test")`, run as SYSTEM.
- `settle(..., superintendent=None)`: when the chain is two-step and `officer == "RECOMMEND"`, sign with `trade.superintendent` if `superintendent` is given.

**Tests (`tests/test_two_step_approval.py`)**
- [ ] `test_start_records_the_chain`: 150 L gives OFFICER and 250 L gives OFFICER_THEN_SUPERINTENDENT, with the `threshold` fixture
- [ ] `test_officer_must_recommend_on_two_step_chain`: APPROVE is refused ("That decision is not available at this step."); RECOMMEND is accepted
- [ ] `test_two_step_chain_moves_stock_only_on_final_approval`: after RECOMMEND, the seller and buyer balances are unchanged and the status is AWAITING_SUPERINTENDENT; after the superintendent APPROVEs, stock has moved, the status is APPROVED, `decided_at` is set, and the audit has `transaction.recommended` then `transaction.approved`
- [ ] `test_superintendent_rejects_with_reason`: needs an officer-kind reason; the status is REJECTED_BY_SUPERINTENDENT; no stock moves
- [ ] `test_only_current_superintendent_can_decide`: after `assign(org.district_officer, other)`, the old superintendent's `request_decision_code` raises NotAllowed and the new one works
- [ ] `test_officer_cannot_also_give_final_approval`: assign the district position to the officer too; after their RECOMMEND, their superintendent decision is refused with the exact message
- [ ] `test_recommend_rechecks_and_refuses`: the seller's licence is suspended after the buyer confirms; RECOMMEND raises TransactionRefused, is audited `transaction.approval_refused`, and the status stays AWAITING_OFFICER
- [ ] `test_final_approval_rechecks_stock`: after the recommend, the seller's stock drops (opening balance on another substance won't do; use `transfer` as SYSTEM to move whisky away); the superintendent's approval is refused with the stock reason and nothing moves
- [ ] `test_detail_shows_chain_and_allowed_outcomes`: over HTTP, the officer sees `allowed_outcomes == ["RECOMMEND", "REJECT"]` and the seller sees `[]`; the timeline after final approval shows both approval positions, and `held_by` only for authority viewers
- [ ] `test_superintendent_sees_final_approval_next_action`: over HTTP

**Steps**
- [ ] Write the tests and see them fail. Implement. Run the full suite green (update any existing test that relied on the old `_NEXT` shape, without weakening it).
- [ ] Update the CODEMAP (roles table: Personnel; the transactions rows; the conventions row for the chain).
- [ ] Commit `feat: severity routing — officer recommends, superintendent gives final approval`.

---

### Task 3: Buyer stock limit is the buyer's decision

**Files:**
- `transactions/checks.py`, `transactions/service.py`, `transactions/presenters.py`
- `reasons/migrations/0003_stock_limit_reason.py`
- `alerts/service.py`
- `tests/test_buyer_stock_limit.py`
- updates to `test_transaction_rules.py` and `test_transaction_api.py`
- `docs/CODEMAP.md`

**Checks**
- `transaction_problems(..., include_buyer_stock: bool = False)`: the buyer cap message (existing wording, for authorities) is added only when the flag is True.
- `buyer_stock_problem(tx) -> str | None` reads the balance and permissions. **Callers run it as SYSTEM.**

**Service**
- **`start_transaction`:** calls `_refusals` without buyer stock.
- **`_approve` and the recommend check:** pass `include_buyer_stock=True`.
- **`allowed_outcomes` for the buyer:** `{REJECT}` when `buyer_stock_problem(tx)` is set. Compute it inside `acting_as_system("buyer_stock_check")`.
- **`decide`, buyer role:**
  - **CONFIRM** with a stock problem (re-checked in `_apply` under the transaction lock): raise `TransactionRefused([problem])`. The view already maps this to 422.
  - **REJECT with `reason_code` blank** while a problem exists: use `STOCK_LIMIT`.
  - **REJECT with `STOCK_LIMIT`** and no problem: raise `InvalidReason` with the exact message, before the code is used.
  - **Audit:** a refused CONFIRM is audited `transaction.confirm_refused` after the rollback, mirroring `approval_refused`.
- **`_apply`:** for a buyer REJECT whose reason code is `STOCK_LIMIT`, raise no alerts; the payload is `{"alerts_raised": 0}`.

**Alerts**
- `_recent_rejections` excludes transactions that have a BUYER decision with reason code `STOCK_LIMIT`. Use `.exclude(decisions__step="BUYER", decisions__reason__code="STOCK_LIMIT")`.

**Presenters**
- The detail adds `"stock_limit_problem"`. It is set only when the viewer's role is `buyer` and the status is AWAITING_BUYER (computed as SYSTEM); otherwise it is None.

**Migration `reasons/0003`**
- Insert `BUYER_REJECTION / STOCK_LIMIT` with label "This would take me over my licence's stock limit" and `sort_order` 50. Make it reversible: delete only that row.

**Tests (`tests/test_buyer_stock_limit.py`)**

Set the buyer's opening balance close to the limit (Retail/Spirits `max_stock_qty` is in conftest; use a balance so that 10 L breaches it).
- [ ] `test_start_is_not_refused_for_buyer_stock`: the seller starts successfully
- [ ] `test_seller_never_sees_buyer_stock`:
  - the seller's start response and detail contain no buyer balance, limit number or `stock_limit_problem`
  - the check endpoint (Task 5) is covered there
  - after the buyer's STOCK_LIMIT rejection, the seller's timeline shows only the reason label
- [ ] `test_buyer_sees_problem_and_only_reject`: the exact sentence, and `allowed_outcomes == ["REJECT"]`
- [ ] `test_buyer_confirm_is_refused_with_422`: over HTTP; the status stays AWAITING_BUYER; `transaction.confirm_refused` is audited
- [ ] `test_blank_reason_defaults_to_stock_limit`
- [ ] `test_stock_limit_reason_refused_when_no_problem`: exact message; the OTP stays usable
- [ ] `test_stock_limit_rejection_raises_no_alert_and_is_not_counted`: no AuthorityAlert rows and payload `{"alerts_raised": 0}`; a later NOT_ORDERED rejection shows `pattern_count == 1`
- [ ] `test_officer_approval_still_checks_buyer_cap`: the buyer's stock rises between confirm and approval (opening balance as SYSTEM); the approval is refused with the cap message (it has numbers, and the officer may see them)
- [ ] `test_stock_limit_reason_is_seeded`
- [ ] Update `test_transaction_rules.py::test_buyer_stock_limit_message` to pass `include_buyer_stock=True`, and add `test_buyer_stock_not_checked_by_default`.

**Steps**
- [ ] TDD as above. Run the full suite green. Update the CODEMAP (roles: Licensee; transactions/checks/alerts rows; test catalogue).
- [ ] Commit `feat: buyer decides on their own stock limit; no seller-visible stock leak`.

---

### Task 4: Oversight marks superintendent approvals

**Files:**
- `oversight/presenters.py`, `oversight/service.py`
- `tests/test_oversight_review.py` (add tests)
- `docs/CODEMAP.md`

**Changes**
- A helper `final_approval(tx) -> TransactionDecision` in `transactions/service.py` returns the decision with outcome `APPROVE` (step OFFICER or SUPERINTENDENT). Use it everywhere that currently looks up the `OFFICER`/`APPROVE` decision: `oversight/presenters._item` and `oversight/service.flag_item`. **Read it as SYSTEM**, as now.
- `_item` adds `"approved_by_superintendent": approval.step == "SUPERINTENDENT"`. `approved_by_position` comes from that decision's position.
- `flag_item` raises `NotAllowed("You approved this transaction; the Head Authority reviews it.")` for those items, before any write.

**Tests**
- [ ] `test_superintendent_approved_items_are_marked`: a batch holds one officer-only and one two-step transaction; the flags are false and true
- [ ] `test_superintendent_cannot_flag_own_approval`: exact message; no flag row and no alert
- [ ] `test_officer_only_flag_still_alerts_officer`: regression

**Steps**
- [ ] TDD. Run the full suite green. Update the CODEMAP. Commit `feat: oversight marks superintendent-approved items; no self-flagging`.

---

### Task 5: APIs for the web app (B1–B4, B6, thresholds read)

**Files:**
- `identity/views.py`
- `core/home.py` (new), `core/views.py`, `config/urls.py`
- `transactions/views.py`, `transactions/serializers.py`, `transactions/service.py`, `transactions/urls.py`
- `catalogue/views.py`, `catalogue/urls.py` (new)
- `alerts/service.py`, `alerts/views.py`
- `tests/test_home_api.py`, `tests/test_d3_apis.py`
- `docs/CODEMAP.md`

**B1 `GET /api/auth/me`**
- The response adds `display_name` and `positions`.
- `display_name`:
  - Licensee: the `holder_name` of their first licence by id (read under their own RLS)
  - Personnel: their position titles joined with ", ", or "Unassigned officer"
  - every other role: `get_role_display()`
- `positions`: `[{"id", "title", "level"}]` from `positions_held(user)`, ordered by id.

**B2 `GET /api/home`** (any logged-in user)
- Returns `{"role": ..., "counts": {...}}`, computed in `core/home.py::home_counts(user, today)` under the caller's RLS.

| Role | Counts |
|---|---|
| Licensee | `awaiting_your_decision` (AWAITING_BUYER where they are the buyer), `sales_in_progress` (they sell, status AWAITING_*) |
| Personnel | `awaiting_your_decision` (AWAITING_OFFICER with the designated position held, plus AWAITING_SUPERINTENDENT with the superintendent position held, **excluding** transactions where this user made the officer decision); `unacknowledged_alerts`; `open_batches`, `overdue_batches` and `next_due` (ISO date or null), over batches of held positions using `batch_status` |
| Licensing Authority | `expiring_licences_30d` (ACTIVE licences whose latest validity period ends between today and today + 30), `districts_without_review_period` (DISTRICT-area positions with no `SuperintendentSetting`) |
| Head Authority, Software Owner | `unacknowledged_alerts` (all), `awaiting_superintendent` (all) |

**B3 `GET /api/transactions` filters.** `?awaiting=me`, `?side=sales|purchases` and `?approved_by=superintendent` combine with AND. Any other value gets 400 "Unknown filter value."
- `awaiting=me` matches `home_counts`' `awaiting_your_decision` set exactly. Share one queryset function, `awaiting_decision_for(user)`, in `transactions/service.py`.
- `approved_by=superintendent` means there is a decision with step SUPERINTENDENT and outcome APPROVE.

**B4 `POST /api/transactions/check`**
- **Who:** Licensee only. CSRF applies, and it uses the `lookup` throttle.
- **Request:** `NewTransactionSerializer` without the transport fields; add a `CheckTransactionSerializer`.
- **Service:** `check_transaction(seller, buyer_gstin, substance, quantity) -> tuple[list[str], str]` runs the same selection and `_refusals` as start, without the buyer stock check, plus `_route` (its refusals included). It writes nothing except the audit record: `transaction.checked`, payload `{"gstin_index": ..., "ok": bool}`.
- **Response:** 200 `{"ok": bool, "reasons": [...], "approval_chain": "OFFICER" | "OFFICER_THEN_SUPERINTENDENT" | null}` (null when not ok).
- A self-sale reason works as in start.

**Thresholds read:** `GET /api/catalogue/approval-thresholds` (any logged-in user) returns, for each threshold, `{"scope": "<substance or class name>", "scope_kind": "substance" | "class", "superintendent_above_qty": str, "unit": ..., "version": n}` with the latest version only. For a class, the unit comes from any of its substances, since a class shares one unit (CODEMAP convention).

**B6**
- Add `class AlreadyAcknowledged(NotAllowed)` in `alerts/service.py` and raise it in both "already acknowledged" places.
- In `AcknowledgeView`:
  - `except AlreadyAcknowledged:` returns 409 with the fixed message
  - `except NotAllowed:` returns 403 with "Only the officer holding this position can acknowledge this alert."
- The view never uses `str(exc)`, to keep CodeQL clean.

**Tests**
- [ ] `test_home_api.py`: one test per role row above, with exact counts. Include the separation-of-duties exclusion and an overdue batch (use `set_decided_on` plus `create_due_batches` with a past `today`).
- [ ] `test_d3_apis.py`:
  - `test_me_has_display_name_and_positions` (Licensee, Personnel with 2 positions, Licensing Authority)
  - `test_awaiting_me_filter_matches_home_count`
  - `test_side_filter`
  - `test_approved_by_superintendent_filter`
  - `test_unknown_filter_is_400`
  - `test_check_endpoint_ok_and_chain`
  - `test_check_endpoint_reasons_and_no_writes` (no Transaction rows; audit `transaction.checked` with no GSTIN)
  - `test_check_endpoint_hides_buyer_stock`
  - `test_check_requires_licensee_and_csrf`
  - `test_thresholds_api`
  - `test_acknowledge_twice_is_409_with_message`
  - `test_acknowledge_not_holder_is_403_with_message`

**Steps**
- [ ] TDD. Run the full suite green. Update the CODEMAP (URL routing row, new rows, roles table "Any logged-in user", test catalogue).
- [ ] Commit `feat: web-app APIs — me, home counts, filters, pre-check, thresholds; fixed ack messages`.

---

### Task 6: CODEMAP sweep and follow-ups

- [ ] **CODEMAP coverage.** Every `backend/**/*.py` except `tests/`, `__init__.py` and `apps.py` has a row. Today these are missing:
  - `identity/migrations/0001,0003–0006,0009`
  - `alerts/0001`, `audit/0001`, `catalogue/0001`, `oversight/0001`, `stock/0001`, `transactions/0001`
  - `config/wsgi.py`
  - Add a single line above section 2 saying `apps.py` files only register the app.
- [ ] Every test function name appears in §3 (abbreviated `…_x` forms are fine where the existing style uses them).
- [ ] Update the "Last updated" line with the test count.
- [ ] **CODEMAP §4.** Update the lock-order row for the superintendent step. Add the chain rule, the separation-of-duties rule and the buyer stock-limit rule.
- [ ] **Follow-ups.** Add a "D2c" section to `docs/superpowers/plans/2026-09-29-phase1-followups.md` listing anything deferred, plus:
  - D2d: rule-change proposals, register APIs, review-settings API (closes the "service trusts its caller" note)
  - D4: seed a Whisky threshold above 200 L
- [ ] Commit `docs: D2c CODEMAP sweep and follow-ups`.

## Spec coverage (D2c)

| Spec item | Task |
|---|---|
| R1 buyer stock limit, R2 no alert or pattern | 3 |
| R3 thresholds and chain | 1, 2 |
| R4 two levels, levels as data | 1 (chain enum; positions unchanged) |
| R5 oversight marking | 4 |
| D3 B1–B4, B6, thresholds read | 5 |
| CODEMAP review | 6 |
