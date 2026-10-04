# Phase 1 Follow-ups

Open items from the Phase 1 reviews. None of them block D1. Pick them up in the phase shown.

## Security and robustness

| Item | When |
|---|---|
| Rate-limit key: read `NUM_PROXIES` and `SECURE_PROXY_SSL_HEADER` from env, set per deployment (behind a load balancer, `NUM_PROXIES=0` makes the login limit global) | Phase 6 deploy |
| Account-lockout DoS: anyone who knows a user ID can keep it locked; add per-(IP, user) counting or progressive delay | Phase 2/6 |
| Absolute session lifetime, alongside session listing (idle timeout alone never expires an active session) | Phase 2 |
| `failed_login_count` never decays (old failures count toward a new lock) | Phase 2 |
| Five-codes-in-15-minutes cap counts successful logins too (Ruling R12); revisit if real users hit it | After the demo |
| Audit chain is unkeyed SHA-256, and `gj_app` can UPDATE the chain head: anchor to a WORM store and tighten the head update | Phase 5 |
| `audit.record()` actor is caller-supplied; default it to the RLS actor so the two can't drift | Phase 2 |
| DRF exception handler assumes an open transaction; guard with `connection.in_atomic_block` | Phase 2 |
| Throttle counts roll back on raised 4xx and 5xx (they live in the request transaction via DatabaseCache) | When choosing the production cache |
| `issue()` accepts inactive users and unknown purposes; no minimum strength check on `OTP_HMAC_KEY`; `OutboxOtpSender` has no production guard | Phase 2 |
| GitHub Actions pinned by tag, not commit SHA | Phase 6 |
| `_fernet()` rebuilt per call; switch to MultiFernet with key rotation | Phase 6 |
| `create_software_owner`: add a "repeat contact" prompt (a typo leaves the only owner without OTP) | Phase 2 |

## Test gaps

- Owner-level DELETE and TRUNCATE on the audit table, and TRUNCATE by `gj_app`.
- `ConsoleOtpSender` refusing when DEBUG is off; verifying with the wrong purpose; `closed_at` set on expiry and at the attempt limit; a correct code on the last allowed attempt.
- The `locked_until` defence-in-depth branch in `LoginVerifyView`; the `login.otp_failed` audit has no subject; the R10 test doesn't assert that exactly 5 codes were sent or that `login.locked` was audited.

## Style

- Module docstrings missing on `config/urls.py`, `config/wsgi.py`, `manage.py`, `core/apps.py`, `audit/apps.py` and `tests/test_db_privileges.py`, and on `audit.hashing.event_fields`.
- `core/middleware.py` `__init__` and `__call__` have no type hints.
- `blind_index` explains itself in a comment instead of a docstring, and doesn't check that the context is lowercase.
- `record()` docstring: narrow the wording "does not open its own top-level transaction" to say it holds only inside the request.

---

# Demo D1 follow-ups (added 2026-09-30)

Open items from the D1 reviews. None of them block D2.

## Decisions to confirm

| Decision | Current behaviour | Revisit when |
|---|---|---|
| A renewal recorded in advance applies immediately (Ruling D-R8) | The newest permission snapshot wins as soon as it is recorded | Confirm against spec D3 before real renewals |
| Areas, positions and assignments have no row-level security (Ruling D-R6) | Any logged-in user can see who holds which position | If the authority treats officer identities as sensitive |
| The catalogue is reference data with no row-level security (Ruling D-R12) | `gj_app` can write catalogue tables from any role context | Add role checks on write paths with the D3 Licensing Authority screens |
| One position per area (Ruling D-R11) | A second position type in an area would need a "kind" field | If the authority needs more than one approving post per area |
| One unit per substance class | Quantities in a class share the class's unit | If a class ever mixes L and kg |
| `Substance`, `LicenceType` and `LicenceTypeRule` rows can still be changed | Changing a rule's scope changes its meaning for existing versions | After the demo |

## Robustness

| Item | When |
|---|---|
| Enrolment: add a per-licence cooldown on code resends (today only 10/min per IP; someone could flood the holder with SMS) | Phase 2 |
| Enrolment `complete` shares the `otp` rate-limit bucket with login; failed completes aren't audited and have no reason codes | Phase 2 |
| Two concurrent completes on one GSTIN: the loser gets a 500 instead of the uniform 401 | Phase 2 |
| Duplicate licence number raises a raw IntegrityError; error texts don't say what to do next | D3 (Licensing Authority screen) |
| REVOKED → ACTIVE transitions have no policy | Phase 2 |
| `current_permissions` return type should be Optional; `licence_card` returns 500 if a snapshot is missing | Phase 2 |
| `assign()` ignores `is_active`; `PersonnelAssignment` can be changed and has no `ended_at >= started_at` check | Phase 2 |

## Test gaps

- **One-time codes (subject path):** the XOR constraint's "neither set" case, and expiry and max attempts. The `locks[0]` lock-order assertion is weak.
- **Delete and truncate:** these aren't asserted for rule versions, periods or snapshots. Add `match=` to the RLS-error assertions.
- **Enrolment:**
  - a revoked licence
  - a licence suspended between start and complete
  - the audit payload holds no raw values
  - the first complete returns 201
- **Licence card:** an expired or suspended card. The API test can't isolate the row-level-security layer, which is covered in `test_licensing.py` instead.
- **Style:** some tests lack docstrings; tests import the private `_permissions` helper; `SubstanceListView` lives in `licensing` rather than `catalogue`.

---

# Demo D2a follow-ups (added 2026-10-01)

## Fixture expiry (resolved 2026-10-03)

- `make_licence` now defaults to a validity ending **2047-12-31**, at the user's request, so tests that use the real `timezone.localdate()` keep passing until then. The tests that deliberately check expiry pass explicit 2026 dates.
- **Before 2047:** either extend the date again or pin "today" in tests. Demo seed data (D4) uses dates relative to the day it runs.

## Hardening (Phase 2 or later)

| Item | Note |
|---|---|
| A decision code's owner is checked only after the code is verified | The challenge id is a random UUID and is only ever returned to its owner. Pass the expected user into `otp.verify` so another user's id can't burn attempts. |
| The decision SMS should name the transaction reference | The code stays bound to the user, but the signer should see what they are signing. |
| No test that `StockLimitExceeded` is mapped to a refusal inside `_approve` | The `InsufficientStock` branch is tested end to end. |
| `transfer()` has no guard against a quantity of zero or less, or against transferring to the same business | The only caller passes `Transaction.quantity`, which database CHECKs already guard. |
| `set_opening_balance` checks then inserts, so a race gives an IntegrityError | Seeding is single-threaded. |
| No database indexes on `seller_gstin_index` and `buyer_gstin_index` | Add them with D2b's 30-day pattern count. |
| A licence recorded on a district or state area gets the misleading "no officer" message | Require a taluka-level area for licences on the D3 Licensing Authority screen. |
| The transaction list runs about 6 queries per row | Batch `positions_held` and party names in D3. |

## Test gaps

- **Stock:** row-level-security tests for Head Authority and Software Owner reads, personnel and other licensees being denied, a non-SYSTEM update, and the `gstin_index` column grant.
- **Transactions:**
  - decisions read through row-level security
  - SYSTEM updating the status
  - a transfer removing an officer's visibility
  - the superintendent's view and list ordering over HTTP
  - an expired code
  - the reject audit actions
- **Service:** a seller without a selling licence, an outsider getting `NotAllowed`, and a refused start writing no audit event.
- **Naming:** `test_stock_and_buyer_capacity_messages` only checks the seller's stock.

---

# Demo D2b follow-ups (added 2026-10-04)

## Decisions to confirm

| Decision | Current behaviour |
|---|---|
| Alert content | Alerts show registered names and the reason, not licence numbers, and have no inline timeline; the officer opens the transaction for that. Spec §5a lists licence numbers. This was minimised deliberately under DPDP; please confirm. |
| Sign-off deadline | 30 days after the period ends, as you decided. |
| One-time codes | Transaction decisions and batch sign-off share the `DECISION` code purpose. Codes are bound to the user, so they can't be misused, but a sign-off code would also work for a pending transaction decision of the same user. |

## For D3 (screens) and D4 (demo tooling)

- **Scheduling:** run `create_due_batches` around 01:00 IST, so late-evening approvals have committed before the batch is made.
- **Demo reset:** recreate the database. The append-only tables block TRUNCATE.
- **Seed data:** create review settings with a start date before the backdated approvals.
- **D3 review-period screen:** check the Licensing Authority role (`set_review_period` itself has no caller check), and keep the call short, because it holds the batch-job lock until the request commits.
- **Batch list:** paginate it. Also batch the alert, summary and item queries (they currently run several queries per row).

## Test gaps

- **Alerts:** a non-SYSTEM insert or delete, Head Authority unable to acknowledge, and an alert failure rolling back the decision.
- **Oversight:**
  - row-level-security reads of batch items, flags and sign-offs
  - inclusive period boundaries
  - two settings in one run
  - another user's code at sign-off
  - a former position holder acting after a transfer
  - a flag racing a sign-off
- **API:** 403 on the sign-off code and sign-off endpoints, `can_sign` for Head Authority and after signing, and throttling.

---

# Demo D2c follow-ups (added 2026-10-04)

## For D2d (Licensing Authority APIs)

- **Rule-change proposals:** the flow for proposing and approving rule and threshold changes.
- **Licence register APIs:** recording, renewing, suspending and revoking licences over HTTP.
- **Review-settings API:** restricted to the Licensing Authority with `role_required`. This closes the CODEMAP note "the service trusts its caller" (`set_review_period` has no caller check).

## For D3 (screens) and D4 (demo tooling)

- **D4 seed data:** seed a Whisky threshold above 200 L, so the demo shows both chains, and the Head Authority persona.
- **D3 buyer reject dropdown:** hide the `STOCK_LIMIT` reason unless `stock_limit_problem` is set. The backend refuses it otherwise, but the buyer should not be offered it.
- **D3 home screen:** `next_due` is the earliest due date of an OPEN batch only. Overdue batches are counted separately (`overdue_batches`), so the screen must show both.

## Hardening (later)

| Item | Note |
|---|---|
| `/me` queries the area level once per held position | Fine for the demo (a person holds one or two positions); add `select_related` later. |
| Gujarati | Backend messages are English sentences. They need stable message codes so the web app can translate them (W6). |

## Test gaps

- None open. The `STOCK_LIMIT` in-lock re-check is covered (`test_stock_limit_reason_refused_under_lock_is_audited`).

# Demo D2d follow-ups (added 2026-10-04)

## Deferred from D2d

- **Licence write APIs: out of scope (owner decision, 2026-10-04).** The government records, renews, suspends and revokes licences in a separate tool, so this product never does. Licences reach it through the existing services (`record_licence`, `record_renewal`, `set_status`): the seed and a future import from that tool. The register (B7) stays read-only.

## For D3 (screens) and D4 (demo tooling)

- **D4 seed data:** seed one approved and one pending rule-change proposal, and two Head Authority users, so the maker-checker flow can be demoed (the drafter cannot decide their own change).
- **D3 before/after diff:** the rule-change detail screen shows `current` against `proposed`. `current` is null once the proposal is decided or withdrawn, so a decided proposal shows `proposed` only.
- **D3 `current` is same-scope only:** `current` is the latest rule version for the same licence type and scope (or the latest threshold for the same scope). It does not show the rule that would actually resolve for a substance when a class rule governs it today. The screen should say so, or D3 can add the resolved rule.
- **D3 licence register area filter:** `?area=` is an exact match, so a district does not include its talukas. D3 may want a hierarchy filter.

## Later optimisations (D2d final review)

- **`proposal_view` queries:** each row costs about 4 to 6 queries (licence type, scope, rule, latest version or threshold). The list is capped at 100, so this is fine for the demo; batch the lookups if the list grows.
- **`LicenceTypeListView`:** one query per rule for its latest version. Prefetch or annotate the latest versions when the catalogue grows.
- **`ReviewSettingChangeView`:** rebuilds the whole review-settings overview to return one position's row. Build only that row when there are many district positions.

## Decisions to confirm

| Item | Note |
|---|---|
| `review_settings_overview` reads batch dates as SYSTEM with no audit event | Read-only and returns dates only, so no audit was added. Confirm this is acceptable. |
| A REJECT note that is mostly spaces | Raised in review: if such a note passed the serializer's length check, the service (which trims it) would still refuse it, giving 422 instead of the 400 field error. Harmless either way, since nothing is written and the code is not spent. Note that DRF's `CharField` trims surrounding whitespace by default, the same way the service does, so over HTTP the two checks should agree; add a test to confirm before changing anything. |
| `max_stock_qty` in the register detail | It is a permission limit from the licence's frozen snapshot, not a stock figure, so it appears by design. The register still never shows stock balances. |

# Demo D3 follow-ups (added 2026-10-04)

## From Task 9 (Licensing Authority screens)

- **Register area filter left out:** the licences page filters by status only. `?area=` takes an area ID, but no endpoint lists the areas with their IDs (`review-settings` gives district names only, and the register rows give taluka names). Add `GET /api/areas` (or area IDs in the review settings) and a district/taluka select, ideally with the hierarchy filter noted under D2d.
- **Register search moved to POST:** `POST /api/licences/search` replaced the `?number=`/`?gstin=` query on `GET /api/licences` (which now answers 400 for them), so no licence number or GSTIN reaches server or proxy logs. Any other client of the old query must move to the POST.
- ~~**A class licence's unit:**~~ **Done in Task 11.** `licence_card` now sends the class's unit (`catalogue.service.class_unit`; null only for a class with no substances) and a `scope_kind`, which the sale wizard uses instead of reading a null unit as "class".

## From Task 10 and the Task 11 sweep

- **react-router 6 advisories (moderate, `npm audit`):** an open redirect through a backslash in `<Link>` and `useNavigate` (a bypass of CVE-2025-68470), and constructor injection in SSR hydration's `deserializeErrors()` (SSR only; this app renders on the client). Mitigation today: the app never navigates to a user- or server-supplied path (every `to` is a fixed path or one built from a reference or numeric ID), and there is no SSR. The fix is react-router 7, a breaking upgrade: plan it for after the demo. `npm audit --audit-level=high` passes.
- **Software Owner has the bell (ruling):** the Software Owner sees the bell and the alerts drawer read-only (no Acknowledge), as the Head Authority does.
- **TDD was partial on Task 10 pages:** the governance and overview page tests were written after the pages. They cover the specified behaviour and pass axe, but were not seen failing first.
- **Rule-version form doesn't prefill:** a new rule version starts from empty fields, not from the current rule for the chosen licence type and scope. Prefill from `catalogue/licence-types` so the drafter changes only what differs.
- **Status tab in the URL uses server values:** `/rule-changes?status=SUBMITTED` (and the other tabs) carry the server's status names. Harmless (no personal data, unknown values fall back to Open), but a rename on the server would break bookmarked links.
- **Bundle split (Task 11):** pages load lazily, one chunk per feature area plus four vendor chunks (`vite.config.ts`); the largest chunk is `vendor-mantine` at about 225 kB (67 kB gzip). If it grows past 500 kB again, split Mantine's less-used components out.

## For D4 (demo tooling and deployment)

- **Caddy CSP** from design §6: `default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'` (Mantine injects styles); `frame-ancestors 'none'`.
- **Persona picker:** a demo-only way to switch between the seeded people without typing codes (mock mode has `?as=`; the real backend needs its own, demo-only, never in production).
- **SMS inbox:** a demo page that shows the one-time codes the fake SMS sender "sent", so codes can be read on screen.
- **Playwright on the real backend:** end-to-end runs of the transaction journey, the two-step approval, the buyer's stock-limit reject, batch sign-off and a rule change against the seeded backend.
- **Seed data:** a Whisky approval threshold above 200 L (so the two-step approval shows), two Head Authority users (the drafter can't decide their own change), and one approved and one pending rule-change proposal.

## Needs the owner's confirmation

- **Adding `frontend` and `analyze (javascript-typescript)` to the required checks of the ruleset needs the owner's confirmation.** Both jobs run on every PR today but are not required, so a red frontend build or CodeQL finding would not block a merge.
