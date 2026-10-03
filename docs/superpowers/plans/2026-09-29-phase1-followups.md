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
