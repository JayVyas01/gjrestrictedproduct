# Demo D4: Demo Tooling, Seed Data and Script Implementation Plan

> **For agentic workers:** implement task by task with TDD (write the failing test, see it fail, implement, see it pass). Steps use checkbox (`- [ ]`) syntax. Never push or merge: the controller pushes, and the owner merges.

**Goal:** one command (`make demo`) starts the whole product on the owner's Mac, fully offline. It comes up with:
- a convincing, synthetic, history-rich dataset
- a demo-only persona picker and SMS inbox
- strict security headers
- Playwright end-to-end tests that drive the real stack

A written 10–12 minute demo script and a rehearsal and reset checklist go with it.

**Spec:**
- parent spec §6 "Demo tooling"
- [D3 design](../specs/2026-10-03-demo-d3-web-app-design.md) §6 (CSP) and §10
- follow-ups "For D4"

**Owner decisions (2026-10-05):**
- **Where it runs:** the owner's laptop, **fully offline**, with no hosted URL for now.
- **How it is served:** **Chrome or Edge**, at `http://localhost:8080`. Chrome treats localhost as a secure context, so `Secure` cookies work without TLS. The script says to use Chrome.

**Builds on:** `dev` after PR #9.

## Global constraints

**Conventions:** all CODEMAP §4 conventions apply.
- The backend uses raise-to-roll-back, `record()` last, `app_db` in tests, RLS, audit payloads with IDs only, and fixed error messages.
- The frontend uses i18n only, `src/api` only, no `localStorage`, and axe on every page.
- Every task updates `docs/CODEMAP.md`.

**`DEMO_MODE` is fenced off from production:**
- **Setting:** `DEMO_MODE = env.flag("DEMO_MODE")`.
- **Startup check:** `config/checks.py` (a Django system check plus an import-time guard in settings) **refuses to start** when `DEMO_MODE` is on and any of these hold:
  - an `ALLOWED_HOSTS` entry is not `localhost`, `127.0.0.1` or `[::1]`
  - `DJANGO_SSL_REDIRECT` is on
  - `OTP_SENDER` is not the demo inbox sender
- **Message:** "DEMO_MODE may only run on localhost with the demo SMS inbox."
- **Demo endpoints** answer **404** (not 403) when `DEMO_MODE` is off, as if they did not exist.

**Demo-only code** lives in a new `demo` app (models, sender, views, seed command). Production paths never import from `demo`, except settings choosing the sender by dotted path.

**The demo runs with `DEBUG` off** (no error pages) and `DJANGO_SSL_REDIRECT=0`.

**Synthetic data only.** For example, the businesses are "Sanand Spirits Pvt Ltd" and "Bopal Bar & Kitchen".

| Data | Rule |
|---|---|
| Places | Real Gujarat district and taluka names |
| GSTINs | State code **99** (never matches a real business) |
| Phone numbers | `+91 98000 0xxxx` reserved demo range |
| Licence numbers | Prefix `DEMO/` |

**Demo password** is one shared value, `DEMO_PASSWORD`, from `.env.demo` (committed as `.env.demo.example` with a fixed non-secret value; synthetic accounts only). The seed refuses to run without it.

**The seed drives the real services, back in time.**
- **Where:** `demo/management/commands/seed_demo.py` builds history by calling the **real services** (licence recording, enrolment-equivalent account creation, `start_transaction`, `decide`, `set_review_period`, `create_due_batches`, `flag_item`, `sign_off`, governance `draft`/`decide`).
- **How it backdates:** each event happens at a scripted moment in the past by patching `django.utils.timezone.now` (the clock helper `demo/clock.py`), in chronological order.
- **What that gives:**
  - `auto_now_add` timestamps, `decided_at`, OTP expiry and audit entries are consistent
  - the audit chain stays valid (`verify_audit_chain` passes after seeding)
- **Codes during seeding:** OTP-signed steps take their codes from the demo inbox sender's latest message for that user, not by bypassing verification.
- **Dates:** relative to today, so batch due dates, the 30-day pattern window and the "expiring in 30 days" count look right on any demo day.
- **Same data every time:** randomness (references, user IDs) comes from Python's `secrets`; the dataset's *content* (who, what, how much, when) is fixed.

**Reset recreates the database.** Append-only tables block TRUNCATE (CODEMAP §4): `make demo-reset` runs `docker compose … down -v`, then `up`, `migrate` and `seed_demo`.

**Offline.** `make demo-build` needs the internet once (pull images, install packages, build). After that `make demo` and `make demo-reset` need no network. No CDN fonts or scripts: the frontend already bundles everything, and the CSP blocks other origins anyway.

**Scheduler.** The backend container's entrypoint runs `migrate` and then `create_due_batches` on every start (idempotent). Real scheduling (01:00 IST) remains a production follow-up.

**Exact strings:**

| Where | Text |
|---|---|
| Persona picker heading | "Demo: sign in as" |
| SMS inbox title | "Demo SMS inbox" |
| SMS inbox empty | "No messages yet. Codes appear here when the app sends them." |
| Demo ribbon | "DEMO — synthetic data" |

## Review focus

1. **Demo features are dead outside demo mode.** With `DEMO_MODE` off, the persona and inbox endpoints are 404, the inbox sender refuses to send, and the frontend shows no picker, inbox or ribbon. *(Tasks 1 and 4)*
2. **The startup guard.** `DEMO_MODE` with any non-localhost host, SSL redirect or another sender refuses to start. *(Task 1)*
3. **The seed is honest.** Every seeded transaction went through the real services: the audit chain verifies, and RLS reads behave as for real data. No rows are written behind the services' backs. *(Task 2)*
4. **CSP and headers.** Caddy serves the exact CSP from design §6, plus `X-Content-Type-Options`, `Referrer-Policy` and `frame-ancestors 'none'`. The app works under it (no inline scripts). *(Task 3)*
5. **Codes in the inbox.** They appear only in demo mode and are stored only in the demo table, which is cleared by reset. Inbox entries show the recipient's display name and the last 4 digits of the contact, never the full number. *(Tasks 1 and 4)*

## File structure

```
backend/demo/                      apps.py, models.py (DemoInboxMessage), sender.py (DemoInboxOtpSender),
                                   views.py, urls.py, clock.py, dataset.py (the scripted story as data),
                                   management/commands/seed_demo.py, migrations/0001_initial.py
backend/config/checks.py           DEMO_MODE guard
backend/Dockerfile, backend/docker-entrypoint.sh
frontend/Dockerfile                (node build stage → caddy:2 runtime), frontend/Caddyfile
docker-compose.demo.yml, .env.demo.example, Makefile
frontend/src/demo/                 PersonaPicker.tsx, SmsInbox.tsx, DemoRibbon.tsx, useDemo.ts (+ tests)
frontend/e2e/                      playwright.config.ts, *.spec.ts, helpers (inbox code reader)
.github/workflows/e2e.yml          (manual + PR, not a required check)
docs/demo/script.md, docs/demo/rehearsal.md, README.md (Run the demo)
```

---

### Task 1: Demo mode, the guard, the SMS inbox and the persona list

**Settings:**
- `DEMO_MODE`.
- Register the `demo` app. The `demo` URLs mount at `/api/demo/` always; the views 404 when demo mode is off.

**`config/checks.py`:**
- `demo_mode_problems(settings) -> list[str]`, a pure function that is easy to test.
- Settings call it at import time and raise `ImproperlyConfigured` with the exact message when it returns problems.

**`DemoInboxMessage` model:**

| Field | Type |
|---|---|
| `user_id` | char 12, blank |
| `display_name` | char 200 |
| `contact_last4` | char 4 |
| `code` | char 6 |
| `created_at` | timestamp |

- No RLS. The table is demo-only and holds synthetic data; document why in the migration docstring.
- The app role may INSERT and SELECT only; REVOKE UPDATE and DELETE. Reset recreates the database.

**`DemoInboxOtpSender.send(contact, code)`:**
- Raises `ImproperlyConfigured` unless `settings.DEMO_MODE`.
- Stores a row, resolving the display name from the account that owns the contact. It looks up users by exact contact match as SYSTEM. **Contacts are encrypted**, so instead pass the user from `otp.issue` if the protocol allows; otherwise add an optional `recipient` to the sender protocol, keeping the console and outbox senders compatible.
- For subject codes (enrolment), the display name is "Enrolment".

**`GET /api/demo/inbox`:**
- Anonymous, because codes are needed before sign-in. Demo only, otherwise 404.
- Returns the newest 20: `[{display_name, contact_last4, code, created_at}]`.
- Uses the `lookup` throttle.

**`GET /api/demo/personas`:**
- Anonymous, demo only, otherwise 404.
- Returns the seeded personas in a fixed order: Seller, Buyer, Area Officer (Sanand), Superintendent (Ahmedabad), Licensing Authority, Head Authority A, Head Authority B.
- Each entry is `{key, label, description, user_id, password}`. `password` is `DEMO_PASSWORD`.
- Personas come from `demo/dataset.py` (user IDs are looked up from a `DemoPersona` table that the seed fills: `key → user_id`; no RLS, demo only).

**Tests (`test_demo_mode.py`):**
- [ ] the guard's problems for each bad combination, and none for the good one
- [ ] the endpoints 404 when demo mode is off (`override_settings(DEMO_MODE=False)`)
- [ ] the sender refuses outside demo mode
- [ ] a login with the inbox sender stores a message with the display name and last 4 digits and no full contact; the inbox lists it newest first, at most 20
- [ ] personas are listed in order with the password
- [ ] the table rejects UPDATE and DELETE for `gj_app`

**Commit:** `feat: demo mode with a startup guard, demo SMS inbox and persona list`.

### Task 2: The seed: a scripted history through the real services

**`demo/clock.py`:** `at(moment)`, a context manager patching `django.utils.timezone.now`, plus `days_ago(n, hour=…)` in IST.

**`demo/dataset.py`:** the story as plain data (no logic), for easy review and editing.

- **Catalogue:**
  - classes Spirits, Beer and Wine, all in L
  - substances Whisky, Rum, Vodka, Beer and Wine
  - licence types (placeholders that the admin updates later): **Wholesale Distributor**, **Retail Vendor**, **Hotel Permit Room** and **Transport Carrier**, each with rules and limits
  - a rule-specific override: Retail may not sell Rum
- **Areas and positions:**
  - Gujarat state
  - districts **Ahmedabad** (talukas Sanand, Daskroi, Bavla) and **Vadodara** (talukas Vadodara City, Padra)
  - one position per area; Personnel users hold Sanand, Daskroi, the Ahmedabad district and the Vadodara district
  - the Licensing Authority user and **two Head Authority users**
- **Review periods:** a 15-day period for Ahmedabad, starting 75 days ago; 30 days for Vadodara.
- **Approval threshold:** **Whisky above 200 L** needs the superintendent.
- **Businesses (about 10)**, each with licences and opening stock. Licence numbers are `DEMO/AHD/0001`-style and GSTINs use state code 99. They include:
  - the demo seller **Sanand Spirits Pvt Ltd** (Wholesale)
  - the demo buyer **Bopal Bar & Kitchen** (Hotel Permit Room, close to its Whisky stock limit, so the stock-limit scene works)
  - a business whose licence expires in 20 days (for "expiring soon")
  - a suspended licence
  - a Vadodara pair
- **Licensee accounts** for the businesses used by personas and for some others, created as enrolment would create them (same service rules) with `DEMO_PASSWORD`.
- **Transactions (about 40)** spread over the last 75 days, mixed:
  - approved (some two-step)
  - rejected by the officer
  - rejected by the superintendent
  - cancelled
  - waiting for the buyer, the officer and the superintendent (today: at least one each for the demo personas)
  - **two buyer rejections ("I did not place this order") of the demo seller within the last 30 days**, so the next one shows "3rd buyer rejection…"
  - one stock-limit rejection, which shows that it doesn't count
- **Oversight:**
  - batches created by `create_due_batches` run as of each past period end
  - one older batch flagged and signed
  - one batch open and due soon
  - one overdue (Vadodara)
- **Alerts:** the alerts that follow from the rejections. Some are acknowledged, and at least one is unacknowledged for the Area Officer persona.
- **Rule changes:**
  - one **approved** (by Head A; drafted by the Licensing Authority): a Beer threshold
  - one **pending** (drafted by Head B): a Retail stock-limit increase, so **Head A** can approve it live
  - one **withdrawn**

**`seed_demo` command:**
- Refuses unless `DEMO_MODE` is on and the database has no licences, so it never adds to real data.
- Wraps everything in one transaction and runs events in chronological order under `clock.at(...)`.
- Takes OTP codes from `DemoInboxMessage` (latest for that user).
- Fills `DemoPersona`.
- Prints a short summary.
- Ends by running `verify_chain` and fails if the audit chain is broken.

**Tests (`test_seed_demo.py`, one seed per module through a module-scoped fixture if feasible, otherwise per test, while keeping the run time reasonable):**
- [ ] it refuses outside demo mode and on a non-empty database
- [ ] the counts match the dataset
- [ ] the audit chain verifies
- [ ] at least one transaction waits for each persona's decision (home counts through the real `home_counts`)
- [ ] the next buyer rejection by Bopal against Sanand gets `pattern_count == 3`
- [ ] the Ahmedabad superintendent has an OPEN batch and Vadodara an OVERDUE one
- [ ] Head A can decide the pending proposal and Head B cannot
- [ ] the buyer persona's open purchase has a `stock_limit_problem` (if the dataset includes that scene), or the next scripted sale would
- [ ] every persona can log in through the real login API with `DEMO_PASSWORD` and an inbox code

**Commit:** `feat: seed_demo — a scripted, back-dated history through the real services`.

### Task 3: The offline Docker demo stack

**`backend/Dockerfile`:**
- python:3.12-slim with uv; `uv sync --frozen --no-dev`.
- Add **gunicorn** as a runtime dependency (pinned), with 3 workers.
- Runs as a non-root user and exposes 8000. No secrets in the image.

**`backend/docker-entrypoint.sh`:**
1. Wait for the database.
2. `manage.py migrate`, using the `gj_owner` credentials from the environment (follow the README's migration-role approach).
3. `create_due_batches` as SYSTEM.
4. Start gunicorn as `gj_app`.

The entrypoint never seeds; that is a separate make target.

**`frontend/Dockerfile`:**
- Build stage: `node:22-slim`, `npm ci`, `npm run build`.
- Runtime stage: `caddy:2-alpine`, with `dist/` copied to `/srv` and the Caddyfile.

**`frontend/Caddyfile`:**
- `:8080`; `/api/*` goes to `backend:8000`.
- Everything else uses `file_server` with an SPA fallback (`try_files {path} /index.html`).
- **Security headers:**
  - `Content-Security-Policy: default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'`
  - `X-Content-Type-Options: nosniff`
  - `Referrer-Policy: same-origin`
  - `Permissions-Policy: camera=(), microphone=(), geolocation=()`
  - remove the `Server` header
- Long cache for `/assets/*` and no-cache for `index.html`.

**`docker-compose.demo.yml`:**
- Services `db` (postgres:16 with the existing init script), `backend` and `web`.
- Only `web` publishes a port: `127.0.0.1:8080`. The database is not published.
- It uses a named volume.
- It reads `.env.demo`: demo keys generated by `make demo-env`, the `DEMO_PASSWORD`, `DEMO_MODE=1`, `DJANGO_DEBUG=0`, `DJANGO_SSL_REDIRECT=0`, `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1`, `OTP_SENDER=demo.sender.DemoInboxOtpSender`, and the database passwords.

**`.env.demo.example`:** explains each value. `make demo-env` creates `.env.demo` with freshly generated keys (Python one-liners, as in `.env.example`) if it is missing. `.env.demo` is gitignored.

**`Makefile` targets** (each with a one-line `help`):

| Target | What it does |
|---|---|
| `demo-build` | Online, once: build the images and pull Postgres |
| `demo` | `up -d`, wait for health, print "Open http://localhost:8080 in Chrome" |
| `demo-seed` | Run `seed_demo` in the backend container (first run after `demo`) |
| `demo-reset` | `down -v`, `up -d`, then seed |
| `demo-stop` | Stop the stack |
| `demo-logs` | Show the logs |
| `demo-check` | Curl the health endpoint and the CSP header, then print OK |

**Verification (manual, report it):**
- Run `make demo-env demo-build demo demo-seed demo-check` on this Mac.
- Load the app in the preview browser at http://localhost:8080 and sign in as a persona through the inbox.
- Confirm in the browser console that the CSP produces no violations.
- Then switch the network off, or set `docker compose … --pull never`, and confirm `make demo-reset` works without network access.

**Tests:**
- [ ] `test_demo_mode.py` covers the env combinations the compose file uses, so the guard passes.
- [ ] A shell-free check (`backend/tests/test_compose_demo.py`) parses `docker-compose.demo.yml` with yaml and checks:
  - only `web` publishes a port
  - it binds to 127.0.0.1
  - `DEMO_MODE` and `OTP_SENDER` are as expected
- [ ] The CI frontend job also runs `caddy validate` (`docker run --rm -v …/Caddyfile caddy:2-alpine caddy validate`).

**Commit:** `feat: offline demo stack — Docker images, Caddy with strict headers, make targets`.

### Task 4: Demo features in the web app

**`useDemo()`:** queries `GET /api/demo/personas` once. A 404 means not a demo, and the app shows nothing demo-related. Mock mode returns a fixed persona list.

**`PersonaPicker`**, on the sign-in page and only in demo mode:
- a card "Demo: sign in as" with one button per persona (label and description)
- clicking fills the user ID and password and submits step 1; **the real password and code login still runs**
- the code step shows a hint: "Your code is in the Demo SMS inbox."

**`SmsInbox`:**
- A header button (and on sign-in) opens a drawer titled "Demo SMS inbox".
- It lists the newest messages: display name, ••••last4, the **code in large digits** and the time.
- It polls every 3 s while open, and the newest message is announced.
- **"Use this code"** fills the open code input when the code belongs to the person signing in (a small context API: the code steps register a fill callback). Otherwise it copies the code to the clipboard.

**`DemoRibbon`:** a fixed, non-interactive "DEMO — synthetic data" tag in the header (saffron outline, AA contrast) and on sign-in.

**Production builds** still include this code, because demo is a runtime mode, but it is dormant without the endpoint. A test proves nothing renders when personas give a 404.

**Contracts:** add `demo_personas` and `demo_inbox` contracts (backend contract test with `override_settings(DEMO_MODE=True)`), and add both endpoints to the mock handlers.

**Tests:**
- [ ] nothing renders on a 404
- [ ] the picker fills and submits and the code step shows the hint
- [ ] the inbox lists messages, "Use this code" fills the PinInput and completes sign-in
- [ ] polling only while open
- [ ] the ribbon is shown
- [ ] axe passes on the sign-in page with the picker, and with the inbox open

**Commit:** `feat: demo persona picker, SMS inbox drawer and demo ribbon`.

### Task 5: Playwright end-to-end tests against the real stack

**Setup:**
- `frontend/e2e/` with `@playwright/test` (pinned) and Chromium only.
- `baseURL` is http://localhost:8080. The stack is started by the caller (`make demo` with a fresh `make demo-reset`).
- Add the script `npm run e2e`.

**`e2e/helpers.ts`:**
- `signInAs(page, personaKey)` uses the persona picker plus the inbox API (`GET /api/demo/inbox`) to read the code.
- `codeFor(displayName)` returns the latest code for that person.
- `decide(page, button, opts)` handles the CodeDialog through the inbox.

**Specs (each independent; each starts from a fresh seed via a `globalSetup` that runs `make demo-reset` once per run, and tests do not depend on each other's side effects; where two tests would touch the same transaction, use different seeded transactions):**
1. **`sale-two-step.spec.ts`:** the seller creates a 250 L Whisky sale (the two-step notice shows) → the buyer confirms → the officer recommends → the superintendent gives final approval → stock moved on both homes, and the timeline shows four steps.
2. **`buyer-rejection.spec.ts`:** the seller sells → the buyer rejects with "I did not place this order" → the officer's bell count increases and the alert shows "3rd buyer rejection…" → the officer acknowledges and the count drops.
3. **`stock-limit.spec.ts`:** a sale that would breach Bopal's limit is started → the buyer sees the warning and only Reject → rejects → no new alert for the officer.
4. **`blocked-sale.spec.ts`:** over the per-transaction limit, the check shows the plain reason and Next is blocked.
5. **`batch-signoff.spec.ts`:** the superintendent opens the due batch, flags one transaction with a reason, signs off with a code → status Signed, and the officer gets the flag alert.
6. **`rule-change.spec.ts`:** Head A opens Head B's pending change, sees the comparison, approves with a code; the licence types page shows the new limit. Head B sees no decide button on their own draft (use the pre-seeded one).
7. **`security-headers.spec.ts`:** the response headers on `/` include the exact CSP; no console CSP violations on the main pages.

**`.github/workflows/e2e.yml`:**
- Runs on `workflow_dispatch` and on PRs touching `frontend/**`, `backend/**`, `docker-compose.demo.yml` or `Makefile`.
- Steps: build the stack, `make demo-env demo demo-seed`, `npx playwright install --with-deps chromium`, `npm run e2e`; upload the report on failure.
- **Not a required check** (owner decides later).

**Commit:** `test: Playwright end-to-end demo journeys on the real stack`.

### Task 6: The demo script, rehearsal checklist and docs

**`docs/demo/script.md`:** a 10–12 minute storyline in scenes. Each scene lists the persona, the clicks, what the audience sees and the **talking point** (plain English, aimed at officials: compliance, tamper-evident records, positional authority, DPDP minimisation).

| # | Scene | Approx. |
|---|---|---|
| 1 | Seller home: licences with permission cards, stock, What's next | 1 min |
| 2 | **Blocked sale:** the per-transaction limit, a plain explanation | 1 min |
| 3 | A valid 250 L Whisky sale, "superintendent gives final approval" | 2 min |
| 4 | Buyer confirms with an SMS code (inbox on screen) | 1 min |
| 5 | Area Officer recommends; superintendent gives final approval; stock moves; the timeline shows who held each position | 2 min |
| 6 | **Buyer rejection:** "I did not place this order", the officer's bell lights, "3rd buyer rejection…", acknowledge | 1.5 min |
| 7 | **Oversight:** the superintendent flags "quantity unusually high", signs the batch | 1.5 min |
| 8 | **Governance:** Head A approves Head B's rule change with a before/after view; maker-checker | 1 min |
| 9 | Close: tamper-evident audit, data minimisation, Gujarati-ready; questions | 1 min |

The script also has an "If something goes wrong" box (reset, persona picker, inbox).

**`docs/demo/rehearsal.md`:**
- the day-before checklist: `make demo-build` while online, a full rehearsal, then `make demo-reset`
- 30 minutes before: offline check, `make demo-reset`, Chrome zoom 110%, close other tabs, do-not-disturb on
- after the meeting: `make demo-stop`
- how to change the seeded story (`demo/dataset.py`)

**`README.md`:** a "Run the demo" section with the five commands and a link to the script.

**CODEMAP:**
- a `demo` app section
- the Docker, Caddy and Makefile rows
- the e2e tests in the catalogue
- the §4 conventions (`DEMO_MODE` guard, seed through services, reset recreates the database)
- Last updated with all counts

**Follow-ups:** a D4 section with anything deferred, plus:
- production deployment (managed Postgres in an India region, real SMS provider, TLS, scheduler at 01:00 IST)
- the hosted demo (not requested)
- the ruleset required checks (owner confirmation still pending)

**Commit:** `docs: demo script, rehearsal checklist, README and CODEMAP`.

## Spec coverage (D4)

| Spec item | Task |
|---|---|
| `make demo`, offline | 3 |
| `DEMO_MODE` and its refusal with production settings | 1 |
| `seed_demo` / `reset_demo` with the data list (GSTIN 99, dummy phones, near-limit and suspended licences, dozens of mixed transactions, two earlier buyer rejections) | 2, 3 |
| Persona picker (real login still runs) | 1, 4 |
| SMS inbox and `DemoInboxOtpSender` refusing outside demo | 1, 4 |
| `docs/demo/script.md` and the rehearsal checklist | 6 |
| Playwright | 5 |
| Caddy CSP (design §6) | 3 |
