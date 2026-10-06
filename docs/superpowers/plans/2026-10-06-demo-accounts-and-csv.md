# Demo Accounts, Sign-up and CSV: Design and Implementation Plan

> **For agentic workers:** implement task by task with TDD. Never push or merge: the controller pushes, and the owner merges. Every task updates `docs/CODEMAP.md`.

**Status:** The owner approved the design in chat on 2026-10-06 and asked for implementation straight away. They will review the result.

**Branch:** `feature/demo-d4-tooling`. This comes before D4 Task 6, the demo script, which waits for the owner's review.

## Owner decisions (2026-10-06)

| # | Decision |
|---|---|
| A1 | **Sign-in asks for the role first.** The roles are Party, Licensing Authority, Area Officer, Superintendent and Head Authority. Each then needs its own identity and password, followed by the usual one-time code. |
| A2 | **A party signs in with its GSTIN and password.** Officials sign in with their **email** and password. The internal `user_id` (`GJ…`) is kept as the system key for audit, links and RLS. |
| A3 | **Officials' passwords are issued by the system and must be changed at the first sign-in.** Until the new password is saved, every API except change-password, logout and `me` answers 403. This applies in production too. |
| A4 | **Party self sign-up (demo only).** The form asks for GSTIN, phone, email, password, business name and address. Every licence, and so all stock, already on record for that GSTIN joins the account automatically. |
| A5 | **The phone must be ownership proof.** It has to match the contact on file of an ACTIVE licence for that GSTIN. The code goes to that contact on file, never to anything the request supplies. Every failure looks the same. This keeps the existing enrolment guarantee: a GSTIN is public, so typing one must never be enough to claim a business. |
| A6 | **CSV files (demo only)** in `demo-data/` (gitignored, mounted into the backend container): `parties.csv`, `officials.csv` and `transactions.csv`. They are **rebuilt from the database** after every relevant change and on reset, so they can never drift from what is stored. |
| A7 | **The CSV records current passwords in plain text, in demo mode only.** This is acceptable because the data is synthetic and the file is local, gitignored and never present outside demo mode. Passwords live in a demo-only `DemoCredential` table, written at seed, sign-up and password change. The persona picker reads the same table. |
| A8 | **Status wording depends on the viewer.** While a transaction waits for the buyer: the buyer sees "Requires your approval" and the seller "Requires buyer approval". When it waits for an officer, the deciding officer sees "Requires your approval". Everyone else keeps the plain status label. |
| A9 | **No visibility changes.** RLS already limits parties and officers; the owner said to skip this. |
| A10 | **More seed data:** |
| | • about 20 parties, about 6 of them **licensed but not yet signed up**, so sign-up can be tried |
| | • Area Officers in every seeded taluka |
| | • about 80 transactions |
| | • officials with emails such as `officer.sanand@demo.gujarat.example` (the reserved `example` domain) |
| A11 | **Lockout counts per account,** whatever the identifier. Demo mode keeps the 30-code allowance. |

## Interfaces

**User:**
- `email_encrypted` and `email_index` (blind index context `"email"`; unique when not blank)
- `address_encrypted` (blank allowed)
- `must_change_password` (bool, default False)
- A migration adds them all. A party's email is stored but is not a login identifier.

**Login step 1:** `POST /api/auth/login` takes `{role, identifier, password}`.

| `role` | Identifier | Account must be |
|---|---|---|
| `PARTY` | GSTIN (normalised; through `licensee_gstin_index`) | a Licensee |
| `LICENSING_AUTHORITY` | email (through `email_index`) | a Licensing Authority |
| `AREA_OFFICER` | email | Personnel currently holding a TALUKA position |
| `SUPERINTENDENT` | email | Personnel currently holding a DISTRICT position |
| `HEAD_AUTHORITY` | email | a Head Authority |
| `SOFTWARE_OWNER` | email | a Software Owner (API only; not shown in the UI) |

- **Same answer for every failure:** a mismatch, an unknown identifier or a wrong password all return the same 401 `"Invalid credentials"`, with the same timing (password hashed on every path) and the same lockout rules as today.
- **Old request shape:** `{user_id, password}` is removed. Update every caller (tests, e2e helpers, the frontend).
- **Response after the code:** `login/verify` and `me` return `must_change_password`.

**Change password:** `POST /api/auth/password` takes `{current_password, new_password}`.
- It uses Django's password validators. A wrong current password gives 400 on that field. A successful change clears `must_change_password` and is audited as `auth.password_changed`.
- In demo mode, the `demo` app (through a signal or a small hook) updates `DemoCredential` and rebuilds the CSV.
- **Gate:** while `must_change_password` is set, every authenticated API except `auth/me`, `auth/password` and `auth/logout` returns 403 `{"detail": "Choose a new password before continuing.", "code": "password_change_required"}`. Implement it as a DRF permission applied by default, so new endpoints get it automatically.

**Party sign-up (demo only, 404 otherwise):**
- `POST /api/demo/signup/start` takes `{gstin, phone, email, business_name, address, password}`.
- It validates the password before anything else.
- **Matching:** the GSTIN must have no account yet, at least one ACTIVE licence, and a phone equal to one of those licences' contacts on file, compared after normalising both.
- **On a match:** a code goes to that contact through `issue_for_subject` (purpose ENROL, subject `"gstin:<index>"`). Store the pending profile (email, business name, address, password hash) in a demo-only `DemoPendingSignup` row keyed by challenge, so the password is never in the URL or the session.
- **Response:** `{challenge_id}` on a match. Every failure gives the same 401 `"We couldn't match those details to a licensed business."`. Audited by blind index.
- `POST /api/demo/signup/complete` takes `{challenge_id, code}`. It creates the Licensee account the same way enrolment does (contact taken from the licence on file; `licensee_gstin_index`; email; address) and records the password in `DemoCredential`. Audited as `signup.completed`.
- `GET /api/demo/signup/candidates` lists the GSTINs that are licensed but not signed up, with their phone on file and business name, so testers can pick one. Demo only, and also listed in `parties.csv`.

**Personas:** `GET /api/demo/personas` now returns `{key, label, description, role, identifier, password}`, with `role` in login-role terms and the current password from `DemoCredential`.

**Transactions:** `transaction_summary` and `transaction_detail` gain `status_for_you`, the A8 wording, or the status label when nothing is waiting on the viewer. Existing `status_label` is unchanged.

**CSV files (`demo/csv_export.py`):** `export_all(directory)` writes the three files atomically (temp file, then rename), UTF-8 with a header row.

| File | Columns |
|---|---|
| `parties.csv` | business_name, gstin, phone_on_file, email, password, signed_up (yes/no), licence_numbers (`;`-joined), licence_types, scopes, talukas, may_buy, may_sell, stock_limits, per_transaction_limits, valid_until, current_stock (e.g. `Whisky 380 L; Rum 40 L`) |
| `officials.csv` | name_or_position, login_role, email, password, must_change_password |
| `transactions.csv` | reference, created_at (IST), seller, buyer, substance, quantity, unit, status, approval_chain, waiting_for |

- **Triggered by** the demo app through `transaction.on_commit` after user, transaction, decision, stock, licence and `DemoCredential` changes, in demo mode only. Debounce to one export per commit.
- **Also run** by `seed_demo` at the end, and as `manage.py export_demo_csv`.
- **Directory:** `settings.DEMO_DATA_DIR` (env `DEMO_DATA_DIR`, default `/app/demo-data`). The compose file bind-mounts `./demo-data` there. `make demo-env` creates the folder. `.gitignore` covers `demo-data/`.
- **A failed export never fails the user's request.** It is logged and retried at the next change.

## Tasks

### Task 1: Identity: role-based sign-in, emails and the forced password change
- **Model and migration:** add the User fields and the migration.
- **`identity/login.py`:** `start_login(role, identifier, password)`, resolved per the table. Keep the timing safety and lockouts.
- **Endpoints:** the login serializer and view, `me` and verify carrying `must_change_password`, and the change-password endpoint.
- **Gate:** the default permission, added to `REST_FRAMEWORK` `DEFAULT_PERMISSION_CLASSES` together with `IsAuthenticated` where that applies. Keep the `AllowAny` views working.
- **`create_software_owner`:** asks for an email. Officials made by any service or seed get `must_change_password=True`.
- **Callers:** update every test that logs in (conftest helpers, `test_login_api.py` and the others) and the contract cases `login_start`, `login_verify` and `me_*`.
- **Tests:**
  - each role's identifier works
  - a wrong role or identifier looks identical to a wrong password
  - Area Officer vs Superintendent is decided by position
  - the gate returns 403 with the code
  - change password: wrong current password, weak new password, success clears the flag, audit
  - lockout per account
  - the email blind index is unique
- **Commit:** `feat: sign in by role with GSTIN or email; issued passwords must be changed`

### Task 2: Party sign-up through the GSTIN, with the phone as ownership proof (demo)
- **Models:** `DemoPendingSignup` and `DemoCredential` in the `demo` app. No RLS, as with the other demo tables; REVOKE UPDATE and DELETE where possible, or document why `DemoCredential` needs UPDATE (password changes).
- **Service and views:** start, complete and candidates, as specified above.
- **Tests:**
  - a match sends the code to the contact on file
  - every failure looks the same (wrong phone, unknown GSTIN, already signed up, suspended-only licences)
  - complete creates the account linked to **every** licence of the GSTIN, with its stock visible through `licences/mine` and `stock/mine`
  - the password is never stored in plain text outside `DemoCredential`
  - everything is 404 outside demo mode
- **Commit:** `feat: demo party sign-up by GSTIN with the phone on file as proof`

### Task 3: CSV export, kept in step with the database
- **Build:** `demo/csv_export.py`, the on-commit hooks, the `export_demo_csv` command and the settings.
- **Wiring:** the compose bind mount, `make demo-env` creating the folder, `.gitignore`, and `DemoCredential` written by the seed, sign-up and password change.
- **Tests:**
  - the export writes three files with exact headers
  - a new transaction, a decision, a sign-up and a password change each update the files after commit
  - nothing runs outside demo mode
  - an export failure doesn't fail the request
- **Commit:** `feat: demo CSV files kept in step with the database`

### Task 4: More seed data
- **Extend `demo/dataset.py`** per A10:
  - about 20 parties, about 6 licensed but not signed up, across all talukas
  - Area Officers for every seeded taluka
  - officials with emails and issued passwords (`must_change_password=True`)
  - about 80 transactions over 75 days, still including every demo moment D4 relies on (3rd buyer rejection, buyer stock limit, two-step, open and overdue batches, the pending rule change for Head A)
- **Personas** use the new identifiers. Persona passwords are issued passwords, so the first sign-in of an official persona shows the change-password screen, which then updates the CSV and picker.
- **Tests:** update `test_seed_demo.py` (counts, candidates, emails, CSV written at the end, every persona signs in through the new API, including the forced change for an official).
- **Commit:** `feat: a larger demo dataset with sign-up candidates and officials' emails`

### Task 5: Viewer-aware status, and the web app
- **Backend:** `status_for_you` per A8 in the presenters, tested for buyer, seller, officer, superintendent and others.
- **Frontend sign-in:**
  - step 1 is a role choice (a segmented control or radio cards, accessible)
  - Party shows GSTIN (with format help); the others show email
  - then password, then code
- **Frontend persona picker:** fills role, identifier and password.
- **Frontend change password:** `/change-password` (current, new and confirm, with rules shown). The app routes there whenever `me.must_change_password` is true, and also on a 403 with `code=password_change_required`.
- **Frontend sign-up page** `/sign-up` (demo only; a link on the sign-in page): GSTIN, phone, email, business name, address, password and confirm, then the code (inbox hint), then a success screen "Your account is ready. Sign in as Party with GSTIN …". It includes a "Pick a demo business" list from `signup/candidates` that fills GSTIN, phone and business name.
- **Status everywhere:** lists, badges and detail use `status_for_you` for the main status text. Awaiting-you styling stays.
- **Contracts and checks:** update contracts and handlers. Run the axe sweep with the new routes.
- **Commit:** `feat: role-first sign-in, password change, demo sign-up page and viewer-aware status`

### Task 6: End-to-end tests and docs
- **e2e:** update the helpers (role-first sign-in, the first-sign-in password change for officials) and every spec, and add `signup.spec.ts` (a candidate signs up, signs in, sees their licences and stock, and the CSV gains them; read the CSV through `docker compose exec`).
- **Runs:** run e2e twice.
- **Docs:** update the CODEMAP (roles table, identity rows, demo rows, conventions, Last updated: replace the very long history line with a short summary plus a pointer to git history), the follow-ups, and the Revision 4 or D3 specs where sign-in is described.
- **Commit:** `test: end-to-end journeys for role-first sign-in and sign-up; docs`
