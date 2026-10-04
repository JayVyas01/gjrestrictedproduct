# Demo D3: Web App Implementation Plan

> **For agentic workers:** implement task by task with TDD (write the failing test, see it fail, implement, see it pass). Steps use checkbox (`- [ ]`) syntax. Never push or merge: the controller pushes, and the owner merges.

**Goal:** the web app the authorities will see in the demo. It covers:
- every role's screens, built on the D1–D2d APIs
- the transaction journey, including the two-step approval and the buyer's stock-limit reject
- buyer-rejection alerts
- the superintendent's batch review and sign-off
- the Licensing Authority's register and review periods
- rule-change drafting and Head Authority approval

**Specs:**
- [D3 web app design](../specs/2026-10-03-demo-d3-web-app-design.md): decisions W1–W7, the screens table, shared components, security, accessibility and testing
- [Revision 4](../specs/2026-10-03-routing-and-rule-governance-design.md)
- parent spec §6–7 (UX principles)

**Builds on:** `dev` after PR #8.

## Global constraints

**Stack** (design W1):
- React 18 and TypeScript (`strict`)
- Vite 5
- Mantine 7 (`@mantine/core`, `hooks`, `form`, `notifications`, `dates`), with Tabler icons
- React Router 6
- TanStack Query 5
- react-i18next
- Tests: Vitest, Testing Library, MSW 2 and `vitest-axe`
- ESLint with typescript-eslint, react-hooks and jsx-a11y
- npm, with a committed `package-lock.json`
- Node 22

**Layout:** everything lives in `frontend/`. Source is in `frontend/src/`; tests sit next to their code (`*.test.tsx`) or in `src/test/`.

**Theme** (design W2), in `src/theme.ts` only:
- navy `#1B365D` (primary, app bar)
- page `#F5F7FA`
- cards white
- saffron `#E8A33D`, for attention only: bell count, What's next accent, "Awaiting you"
- status colours: approved green, rejected red, cancelled grey, waiting saffron
- contrast must meet WCAG 2.1 AA

**All user-visible text** comes from `src/i18n/en.json`, through `t()` (design W6). Server-supplied refusal text (`detail`, `reasons`) is shown as is. Dates are shown in IST with `en-IN`. Quantities are always shown with their unit.

**API access:**
- Only `src/api/*` talks to the server. Components use TanStack Query hooks from `src/api/hooks/*`.
- **Same origin:** `credentials: "same-origin"`.
- **CSRF:** call `GET /api/auth/csrf` once, read the `csrftoken` cookie, and send `X-CSRFToken` on every non-GET request.

**Error mapping**, in `api/client.ts`. Every failure becomes `ApiError {status, detail, reasons?, fieldErrors?}`. `ErrorNotice` shows the text from the table below; `detail` and `reasons` are shown whenever the server sends them.

| Status | Shown to the user |
|---|---|
| 400 | Field errors under each field |
| 401 | "That code didn't match. Check the SMS or send a new code." on code steps |
| 403 | The session is checked (see below); otherwise the server's `detail` |
| 404 | "Not found, or not yours to see." |
| 409 | The server's `detail` |
| 422 | The `reasons` list |
| 429 | "Too many tries. Wait a minute and try again." |
| 5xx | "Something went wrong. Try again." |

**Session expiry:** a 403 on any call triggers a `GET /api/auth/me`. If that also fails, the app clears the query cache and drafts, then goes to `/sign-in?expired=1`, which shows "Your session ended after 15 minutes without activity. Sign in again."

**Privacy** (design §6):
- no tokens or personal data in `localStorage`
- wizard drafts only in `sessionStorage` under `gj.draft.sale`, cleared on submit, sign-out and session end
- no personal data in URLs: GSTINs, transport details and codes only in POST bodies; URLs carry references and numeric IDs only
- no `dangerouslySetInnerHTML`

**Accessibility** (design §7):
- every page passes `vitest-axe` in its test
- a skip link, visible focus, labelled fields, and errors linked to fields with `aria-describedby`
- the timeline and notifications are announced (`aria-live`)
- the layout works down to 360 px wide

**Polling** (W7): home counts and alerts refresh every 30 s, and refetch after every user action that changes data.

**API contracts:**
- **Captured from the real backend.** `backend/tests/test_api_contracts.py` drives real endpoints and writes their JSON to `frontend/src/test/contracts/<name>.json` when `UPDATE_CONTRACTS=1`.
- **Checked on every run.** Otherwise it compares the **shape** (keys and value types, recursively) with the committed file, and fails when they differ.
- **Used by the mocks.** MSW handlers (`src/test/handlers.ts`) serve these files, so the mocks always match the real API.
- **Adding an endpoint later** means adding a contract case.

**Mock mode:** `npm run dev:mock` sets `VITE_MOCK_API=1` and starts the MSW browser worker with the same handlers, so you can review the screens without a seeded backend. The worker is imported only when `import.meta.env.DEV && VITE_MOCK_API`, and never ships in `vite build`.

**CODEMAP:** every task updates `docs/CODEMAP.md`. Task 1 adds a "frontend" section (file → responsibility → tests) and a frontend part of the test catalogue.

**Commands** (from `frontend/`):

| Purpose | Command |
|---|---|
| Install | `npm ci` |
| Develop | `npm run dev` (proxies `/api` → `http://127.0.0.1:8000`) |
| Mock mode | `npm run dev:mock` |
| Test | `npm test` (vitest run) |
| Lint | `npm run lint` |
| Type check | `npm run typecheck` |
| Build | `npm run build` |
| Audit | `npm audit --audit-level=high` |

Run the backend suite as before. Docker must be up. Node is at `/opt/homebrew/opt/node@22/bin` if it isn't on PATH.

**Out of scope** (D4):
- the persona picker
- the SMS inbox
- the seed data
- the Compose and Caddy setup
- the Playwright end-to-end tests
- the demo script

## Review focus

1. **Session and CSRF.** No API call can be made without the CSRF header. A session that ends mid-task lands on sign-in with the expiry message, with the cache and draft cleared. *(Tasks 2 and 3)*
2. **Buyer stock limit.** When the sale would breach the buyer's stock limit, only Reject is offered, with the reason filled in and no confirm path in the UI. The seller's screens never show buyer stock (none of the contract data has it). *(Task 5)*
3. **The wizard draft** never reaches `localStorage`, and it is cleared on submit and on sign-out. *(Task 6)*
4. **Decisions use the server's `allowed_outcomes`.** The UI never shows a decision the server wouldn't accept: recommend vs approve, the dual holder, the superintendent's final approval. *(Task 7)*
5. **Maker-checker in the UI.** The Head Authority's own proposals show no decide button. Rejecting needs a note. *(Task 10)*

## File structure

```
frontend/
  package.json, package-lock.json, vite.config.ts, tsconfig*.json, eslint.config.js, index.html, README.md
  public/mockServiceWorker.js                 (generated by msw init; dev only)
  src/
    main.tsx, App.tsx, routes.tsx, theme.ts
    i18n/index.ts, i18n/en.json
    api/client.ts, api/types.ts, api/<area>.ts, api/hooks/<area>.ts
    auth/SessionProvider.tsx, auth/SignInPage.tsx, auth/RequireRole.tsx
    layout/AppShell.tsx, layout/Bell.tsx, layout/AlertsDrawer.tsx
    components/WhatsNextCard.tsx, StatusTimeline.tsx, CodeDialog.tsx, ReasonPicker.tsx, StatusBadge.tsx,
               PermissionCard.tsx, ErrorNotice.tsx, Qty.tsx, DateText.tsx, EmptyState.tsx
    features/licensee/…, features/sale/…, features/personnel/…, features/batches/…,
    features/authority/…, features/governance/…, features/overview/…
    mocks/browser.ts                            (dev:mock only)
    test/setup.ts, test/render.tsx, test/handlers.ts, test/contracts/*.json
backend/tests/test_api_contracts.py
.github/workflows/ci.yml (frontend job), codeql.yml (javascript-typescript), dependabot.yml (npm)
.claude/launch.json (backend, frontend and frontend-mock preview configs)
```

---

### Task 1: Scaffold, tooling and CI

- [ ] **Scaffold:** create `frontend/` (Vite React-TS template, then trimmed) with the stack above. Pin exact versions with `npm install --save-exact`.
  - **TypeScript:** `tsconfig` strict.
  - **Path alias:** `@/` maps to `src/`.
- [ ] **Vite:** the dev server proxies `/api` to `127.0.0.1:8000`. `build.sourcemap` is false.
- [ ] **`src/theme.ts`:** the Mantine theme (W2), with a custom `navy` 10-shade palette as `primaryColor` and `saffron` as an extra colour. Default radius `sm`, and a system font stack.
  - Also export the token constants for the status colours.
- [ ] **i18n:** `i18n/index.ts` (react-i18next, `en` only, no detection, `escapeValue: false` because React escapes). `en.json` starts with the app name "Gujarat Restricted Goods" and a few common keys.
- [ ] **App providers:** `App.tsx` wraps `MantineProvider`, `Notifications`, `QueryClientProvider` (retry 1, no refetch on window focus) and `RouterProvider`. A placeholder home renders the app name.
- [ ] **Test setup:**
  - `test/setup.ts`: jest-dom, `vitest-axe` matchers, an MSW server with `onUnhandledRequest: "error"`, and matchMedia/ResizeObserver stubs for Mantine.
  - `test/render.tsx`: `renderWithProviders(ui, {route, user})`.
  - First test, `App.test.tsx`: it renders the app name and has no axe violations.
- [ ] **ESLint:** flat config with typescript-eslint, react-hooks, jsx-a11y, and `no-restricted-syntax` banning `dangerouslySetInnerHTML` and `localStorage`. `npm run lint` must be clean.
- [ ] **Scripts:** `dev`, `dev:mock`, `build` (`tsc -b && vite build`), `test` (`vitest run`), `test:watch`, `lint`, `typecheck`.
- [ ] **CI:**
  - `ci.yml` gets a `frontend` job on ubuntu-latest: setup-node 22 with npm cache on `frontend/package-lock.json`, then `npm ci`, lint, typecheck, test, build and `npm audit --audit-level=high` (working-directory `frontend`).
  - `codeql.yml` adds `javascript-typescript` to the matrix.
  - `dependabot.yml` adds npm for `/frontend`, weekly.
- [ ] **`.claude/launch.json`:** add configurations:
  - `backend`: `uv run --env-file .env.dev python manage.py runserver 8000` with cwd `backend`. Check which env file development uses (`backend/.env*`) and use it.
  - `frontend`: `npm run dev`, port 5173.
  - `frontend-mock`: `npm run dev:mock`, port 5174.
- [ ] **`frontend/README.md`:** how to run, test and use mock mode.
- [ ] **CODEMAP:** a new "frontend" section in §2 and a frontend test catalogue in §3. The §4 conventions get: text only through i18n, API only through `src/api`, no `localStorage`.
- [ ] **Commit:** `feat: web app scaffold — Vite, React, Mantine, i18n, tests, CI`.

### Task 2: API contracts, client and hooks

- [ ] **Contract test** (`backend/tests/test_api_contracts.py`): uses the existing fixtures (`trade`, `settle`, `threshold`, `review_setting`, the governance helpers, `make_licence`) to drive each endpoint the frontend uses, as the right role.
  - **Endpoints covered:**
    - `me`, `home` (one case per role)
    - `transactions` list and detail: seller, buyer (with and without `stock_limit_problem`), officer, superintendent and authority views, both chains
    - `check`, `buyer-lookup`
    - `licences/mine`, `stock/mine`
    - `reason-codes`, `catalogue/substances`, `classes`, `licence-types`, `approval-thresholds`
    - `alerts`, `oversight/batches` list and detail
    - `rule-changes` list and detail, `licences` register and detail
    - `review-settings`
    - error bodies: 400, 401, 403, 404, 409, 422
  - **Output:** each case writes `frontend/src/test/contracts/<name>.json`. The shape is compared recursively: same keys; value types string, number, boolean, null, list (comparing the first element's shape) or object. Null is allowed where the sample also has null. Write the shape helper simply, in about 30 lines.
  - **Stability:** randomness such as references, dates and IDs is fine, because only the shape is compared.
  - **Commit** the generated JSON.
- [ ] **`api/types.ts`:** TypeScript types for every contract, written by hand and kept small.
  - A frontend test, `contracts.test.ts`, imports every contract JSON and checks it against a type guard (a few required keys per type), so a type that drifts from its contract is caught.
- [ ] **`api/client.ts`:** `apiGet`, `apiPost`, `apiPut` and `ensureCsrf()`, with the error mapping and session expiry from the global constraints. Session expiry is a callback that `SessionProvider` registers.
  - **Tests:**
    - the CSRF header is sent on POST and PUT and not on GET
    - `ensureCsrf` runs once
    - each status maps to the right `ApiError`
    - a 403 followed by a failed `me` calls the expiry callback
    - a 403 followed by a working `me` does not
- [ ] **Endpoint modules:** `api/auth.ts`, `home.ts`, `transactions.ts`, `alerts.ts`, `oversight.ts`, `licensing.ts`, `catalogue.ts`, `governance.ts`, each with typed functions. `api/hooks/*.ts` hold the query and mutation hooks.
  - **Query keys** are constant arrays.
  - **Invalidation:** mutations invalidate the related keys and `["home"]`.
  - **Polling:** `useHome` and `useAlerts` poll every 30 s.
- [ ] **Test handlers:** `test/handlers.ts` serves the contracts (default per endpoint), with helpers like `useContract("transaction_detail_buyer_stock_limit")` to override one per test.
- [ ] **Mock mode:** `mocks/browser.ts` uses the same handlers. Run `npx msw init public` (the worker file is committed). In mock mode the app treats you as signed in, with a role from `?as=seller|buyer|officer|superintendent|la|head`.
- [ ] **CODEMAP:** add the contracts convention and the `api/*` rows.
- [ ] **Commit:** `feat: API contracts from the real backend; typed client with CSRF, errors and session expiry`.

### Task 3: Sign-in, session and the app shell

- [ ] **`SignInPage`, step 1:** user ID and password.
  - Calls `POST /api/auth/login`. Use the backend's `identity/views.py` for the exact request and response.
  - **Errors:** a wrong password shows the server's `detail`; 429 shows the "too many tries" text.
- [ ] **`SignInPage`, step 2:** the six-digit code (Mantine `PinInput`, accepts a paste), then `login/verify`.
  - "Send a new code" goes back to step 1.
  - On success: `invalidate(["me"])`, then route to the role's landing page.
  - **`?expired=1`** shows the expiry notice (`role="status"`).
- [ ] **`SessionProvider`:** `useMe()`, which exposes `user` with role, `display_name` and positions.
  - **Signing out:** `signOut()` calls `POST /api/auth/logout`, clears the query cache, removes `gj.draft.*` from `sessionStorage`, and goes to `/sign-in`.
  - **Expiry** does the same as signing out, without the server call.
- [ ] **`RequireRole`:** guards routes by role. A logged-out user goes to sign-in; the wrong role goes to their own home.
- [ ] **Landing routes:**

  | Role | Landing route |
  |---|---|
  | LICENSEE | `/licensee` |
  | PERSONNEL | `/personnel` |
  | LICENSING_AUTHORITY | `/authority` |
  | HEAD_AUTHORITY | `/head` |
  | SOFTWARE_OWNER | `/overview` |

- [ ] **`AppShell`:**
  - a navy header with the app name and the `display_name` with its role label
  - the `Bell` (PERSONNEL and HEAD_AUTHORITY only), showing the unacknowledged count from `useHome` and opening `AlertsDrawer` (Task 7 fills it)
  - a sign-out button
  - a skip link to `#main`
  - role-specific navigation links: Mantine `AppShell` with a burger menu under 768 px
- [ ] **Tests:**
  - the full sign-in flow with MSW
  - a wrong code shows the 401 text
  - the expiry notice
  - each role lands on its route
  - `RequireRole` redirects
  - sign-out clears the draft key
  - axe passes on the sign-in page and the shell
- [ ] **CODEMAP**, then **commit** `feat: sign-in with one-time code, session handling and the app shell`.

### Task 4: Shared components

Build each component in `src/components/` with tests: its states plus an axe check.

- [ ] **`WhatsNextCard({title, body, action?})`:** one sentence and one primary action button. It has a saffron left accent; a single-sided border means `border-radius: 0`.
- [ ] **`StatusBadge({status, awaitingYou})`:** colour by status. "Awaiting you" (saffron) takes precedence when `awaitingYou` is set.
- [ ] **`StatusTimeline({events, pending})`:** a vertical Mantine `Timeline`. Each event shows its title from `step`/`outcome` (i18n map), `by`, the time (`DateText`), the reason, the comment, and `held_by` when present.
  - A pending step shows greyed out.
  - The latest change is announced (`aria-live="polite"`).
- [ ] **`CodeDialog({open, title, requestCode, submit, onDone})`:**
  - **Opening it:** calls `requestCode()` to get a `challenge_id`, then shows a `PinInput` and a 5-minute countdown.
  - **Submitting:** calls `submit({challenge_id, code})`.
  - **On 401:** shows the wrong-code text and keeps the dialog open.
  - **"Send a new code"** requests another code.
  - **Other errors** show `ErrorNotice`.
  - **Focus** is trapped and Escape closes the dialog.
  - **Tests:** success, wrong code, resend, and the countdown expiring (fake timers).
- [ ] **`ReasonPicker({kind, value, onChange, hideCodes?})`:** loads `reason-codes?kind=`. Choosing OTHER reveals a required comment. `hideCodes` hides `STOCK_LIMIT` unless it applies (D2c follow-up).
- [ ] **`PermissionCard({licence})`:**
  - **Allowances:** buy, sell and transport shown as ticks and crosses with text, never colour alone.
  - **Details:** the stock limit, the per-transaction limit (`Qty`), validity, the status and a banner for suspended, revoked or expired.
- [ ] **`ErrorNotice({error})`**, **`Qty({value, unit})`**, **`DateText({iso, withTime})`** (IST, `en-IN`) and **`EmptyState({title, body, action?})`**.
- [ ] **CODEMAP**, then **commit** `feat: shared components — timeline, code dialog, reasons, permission card, notices`.

### Task 5: Licensee home, transactions and the buyer's decision

- [ ] **`/licensee` home:**
  - **What's next:** from `home.counts`. "N purchases wait for your confirmation" links to the purchases filter with `awaiting=me`. When nothing waits, "Start a new sale".
  - **Your licences:** `PermissionCard` for each.
  - **Your stock:** a table.
  - **Recent transactions:** the latest 5.
  - **Primary button:** "New sale".
- [ ] **`/licensee/transactions`:** tabs for All, Sales, Purchases and Waiting for you (`side`, `awaiting=me`). Rows show the reference, substance, quantity, the other party's name, `StatusBadge` and the date. Under 768 px they become stacked cards.
- [ ] **`/licensee/transactions/:reference`:**
  - **Contents:** a summary, the transport details, the designated officer, the approval chain label, `StatusTimeline` and `next_action`.
  - **Seller,** while it waits for the buyer: "Cancel sale" asks for confirmation, then cancels.
  - **Buyer:**
    - **Normal case:** "Confirm" and "Reject" (only outcomes from `allowed_outcomes`). Reject opens `ReasonPicker(kind=BUYER_REJECTION)` and then `CodeDialog`.
    - **When `stock_limit_problem` is set:** a warning `Alert` shows that sentence, and only "Reject" is offered. The reason is pre-set to STOCK_LIMIT and can be changed. There is no Confirm button anywhere.
- [ ] **Tests:**
  - home counts and cards render
  - the list filters send the right query
  - the seller can cancel
  - the buyer confirms through `CodeDialog`
  - the buyer's stock-limit state has no confirm button and the reason is preset
  - the seller's detail (contract `transaction_detail_seller`) never renders any buyer stock text
  - axe passes on each page
- [ ] **CODEMAP**, then **commit** `feat: licensee home, transactions and buyer decisions (stock-limit reject only)`.

### Task 6: The new-sale wizard

- [ ] **`/licensee/sale/new`:** a Mantine `Stepper` with a visible progress label ("Step 2 of 4").
  1. **Buyer:** a GSTIN field with format help (15 characters). "Find buyer" posts to `buyer-lookup` and shows the registered name with "Is this the right business?" (Yes/Change). A 404 shows the server text.
  2. **Goods:** substance (from `catalogue/substances`, limited to those the seller's licences cover, using `licences/mine`) and quantity with its unit. "Check" posts to `transactions/check`:
     - `ok`: shows "This sale can go ahead" and, when `approval_chain` is two-step, "Above the threshold: the superintendent gives final approval."
     - not ok: shows the reasons, and Next stays blocked.
  3. **Transport:** transporter name, ID or licence number, vehicle number (uppercased; format help) and route. Each field has help text.
  4. **Review and send:** everything on one page. "Send to buyer" posts to `transactions`. On 201, go to the detail with a success notification "Sent to the buyer for confirmation." On 422, show the reasons and a link back to step 2.
- [ ] **Drafts:**
  - saved to `sessionStorage["gj.draft.sale"]` on every change (debounced 300 ms)
  - restored on load, with "Draft restored", a "Start over" option and a "Discard draft" action
  - cleared on success
  - a test spies on `localStorage.setItem` and checks it is never called
- [ ] **Tests:**
  - each step validates before Next
  - the lookup states
  - the check, both ok and refused
  - the two-step notice
  - submit success and 422
  - draft save and restore, and draft cleared on submit
  - `localStorage` never used
  - axe passes at every step
- [ ] **CODEMAP**, then **commit** `feat: new-sale wizard with buyer lookup, live checks and tab-only drafts`.

### Task 7: Personnel: decisions and alerts

- [ ] **`/personnel` home:** sections depend on the positions held (`me.positions` levels).
  - **What's next:** "N transactions wait for your decision", "N unacknowledged alerts", and for a district position "Batch due on {date}" or "N batches overdue" (red).
  - **Decision queue:** `transactions?awaiting=me`. Each row shows its chain label, and "Final approval" for AWAITING_SUPERINTENDENT.
  - **Unacknowledged alerts:** the latest 3.
- [ ] **`/personnel/transactions` and the detail:** the same detail component as Task 5, with the authority fields: comments, `held_by` and the officer's recommendation.
  - **Decisions:** the buttons come only from `allowed_outcomes`:
    - `RECOMMEND` reads "Recommend for approval"
    - `APPROVE` reads "Approve" on the officer chain and for a dual holder, and "Give final approval" when the status is AWAITING_SUPERINTENDENT
    - `REJECT` opens `ReasonPicker(kind=OFFICER_REJECTION)`
  - **Every decision** goes through `CodeDialog`. A 422 refusal shows its reasons.
- [ ] **`AlertsDrawer`** (from the `Bell`): the list from `/api/alerts`, unacknowledged first.
  - **Each alert:** its kind label, the reference (linked), substance and quantity, party names, the reason, the comment and the pattern wording (buyer rejections), with saffron highlighting when the count is 2 or more.
  - **Acknowledging:** "Acknowledge" takes an optional note. A 409 shows the server's `detail`.
  - **The bell count** updates after acknowledging.
- [ ] **Tests:**
  - an officer on the two-step chain sees only Recommend and Reject
  - a dual holder sees Approve
  - a superintendent sees "Give final approval"
  - a 422 refusal shows its reasons
  - the drawer lists alerts and acknowledges them (count drops; 409 handled)
  - axe passes
- [ ] **CODEMAP**, then **commit** `feat: officer and superintendent decisions, approval queue and alerts drawer`.

### Task 8: Superintendent batches

- [ ] **`/personnel/batches`:** cards per batch: period, due date, `StatusBadge` (OPEN, OVERDUE in red, SIGNED in green), and item and flag counts.
- [ ] **`/personnel/batches/:id`:**
  - **Table:** the items with substance, quantity, parties, approval time, approving position, an "Approved by you" tag (`approved_by_superintendent`) and any flag.
  - **"Flag":** opens `ReasonPicker(kind=SUPERINTENDENT_FLAG)` with a comment. It is hidden for items marked approved by the superintendent, and for signed batches.
  - **"Sign off batch":** shown when `can_sign`. It goes through `CodeDialog` with `sign-off-code` and `sign-off`, then shows a success notification.
  - **A signed batch** shows who signed it and when.
- [ ] **Tests:**
  - list statuses
  - flag success and refusal (403 text shown)
  - no flag action on own approvals
  - sign-off flow
  - signed state
  - axe passes
- [ ] **CODEMAP**, then **commit** `feat: superintendent batch review — flags and signed sign-off`.

### Task 9: Licensing Authority screens

- [ ] **`/authority` home:** What's next shows licences expiring within 30 days, districts without a review period, your open rule changes and rule changes submitted. Quick links go to each screen.
- [ ] **`/authority/licences`:**
  - **Search:** an exact licence number or GSTIN, submitted by a button as `POST /api/licences/search` (the value in the request body; CSRF and the `lookup` throttle). `GET /api/licences` keeps only the status, area and page filters and refuses `?number=`/`?gstin=` with 400.
    - **Privacy:** the search value never sits in any URL: not the API's (it is in the POST body) and not the page's (keep the search in component state, not router search params).
    - A note says "Exact match only. Partial search isn't available, to protect licence holders."
  - **Filters:** status and area (a select fed from `review-settings` areas plus taluka names in the results; if no area list endpoint exists, filter by status only and leave the area filter out, then log it in the follow-ups).
  - **Results:** a paginated table with 25 rows per page.
- [ ] **`/authority/licences/:id`:** the `PermissionCard`, GSTIN, area and the validity periods table. No contact or stock.
- [ ] **`/authority/licence-types`:** an accordion per type listing each rule: scope, permissions, limits, validity, version. There is also a section with the approval thresholds.
- [ ] **`/authority/review-periods`:** a table of district positions with the period, start, current period end and last batch.
  - **"Change"** opens a modal with a 15/30/60 radio group and an optional start date, then sends a PUT.
  - **A 422** lists the reasons.
  - **Head and Software Owner** see the table read-only (no Change button). They reach it through the overview navigation.
- [ ] **Tests:**
  - exact search, with the URL checked to hold no number or GSTIN
  - pagination
  - detail with no contact
  - licence types render
  - a review-period change succeeds or fails with 422
  - read-only for Head
  - axe passes
- [ ] **CODEMAP**, then **commit** `feat: Licensing Authority — register, licence detail, licence types, review periods`.

### Task 10: Rule changes, and the Head Authority and Software Owner overview

- [ ] **`/rule-changes`** (Licensing Authority, district Personnel, Head): a list with status tabs (Open, Approved, Rejected, Withdrawn). Each row shows the kind label, a scope summary, the drafter role, the date and a status badge.
- [ ] **`/rule-changes/new`:** pick the kind, then a form per kind (Mantine `useForm`), with a justification field (10–1000 characters, with a counter).
  - **Each form's fields:**
    - **New licence type:** code (uppercase hint), name and description.
    - **Rule version:** licence type select, a scope switch (substance or class) with a select, buy/sell/transport switches, the two limits with unit, and validity in months. Inline check: per-transaction ≤ stock.
    - **Approval threshold:** a scope switch and select, and the quantity with unit.
  - **A 422** shows the reasons. **Success** goes to the detail.
- [ ] **`/rule-changes/:id`:**
  - **Before and after:** a two-column comparison of `current` and `proposed`, with changed values highlighted. `current` null reads "New, nothing to compare".
  - **Details:** the justification, the drafter role (and user ID for the Head and Software Owner), and the decision, if any.
  - **Buttons:**
    - "Withdraw" appears when `can_withdraw`.
    - "Approve" and "Reject" appear when `can_decide`. Reject needs a note of at least 10 characters, and the decision goes through `CodeDialog`.
    - When the Head drafted the change, no decide buttons appear, and a note explains "Another Head Authority officer must decide this change."
- [ ] **`/head` home:** What's next ("N rule changes wait for your approval") and links to:
  - the rule changes awaiting approval
  - all transactions, with a "Superintendent-approved" filter (`approved_by=superintendent`)
  - alerts
  - batches
  - review periods (read-only)
  - licences
- [ ] **`/overview` (Software Owner):** the same read-only lists without the decide actions.
- [ ] **Tests:**
  - each draft form validates and submits, and a 422 shows its reasons
  - the before/after highlighting
  - withdraw
  - the Head decides someone else's change: approve, and reject with a note
  - no decide on own drafts
  - the overview filter sends `approved_by=superintendent`
  - axe passes
- [ ] **CODEMAP**, then **commit** `feat: rule-change drafting and Head Authority approval; authority overview`.

### Task 11: Polish, accessibility sweep and docs

- [ ] **Text check:** a test or script that fails on hard-coded user-visible strings in `src/features` and `src/components`. Use `eslint-plugin-i18next` (`no-literal-string`, markup only), or a simple test that renders every page and checks every text node comes from `en.json` values. Pick the simpler one that works.
- [ ] **Accessibility and layout:** an axe sweep test that renders every route with contract data; it must be all green. Then a manual check at 360 px and 1280 px in mock mode through the preview browser (`frontend-mock` launch config): screenshot each persona's home, the wizard and a transaction detail, and fix any overflow or truncation.
- [ ] **Empty states:** every list has an inviting empty state, and every page has a loading skeleton.
- [ ] **CODEMAP sweep:**
  - every `frontend/src/**/*.ts(x)` file, apart from tests and contracts, has a row
  - every frontend test file has a catalogue section
  - "Last updated" gives both test counts
- [ ] **Follow-ups:** add a D3 section with anything deferred, the D4 notes (Caddy CSP from design §6, the persona picker, the SMS inbox, Playwright on the real backend), and the reminder that **adding `frontend` to the required checks of the ruleset needs the owner's confirmation**.
- [ ] **Commit:** `docs: D3 accessibility sweep, CODEMAP and follow-ups`.

## Spec coverage (D3)

| Design item | Task |
|---|---|
| W1 stack, W2 theme, W6 i18n, CI | 1 |
| W3 one origin, W7 polling, contracts | 1, 2 |
| Sign-in, session expiry, shell, bell | 3 |
| Shared components | 4 |
| Licensee screens, buyer stock-limit state | 5 |
| Wizard, W4 drafts | 6 |
| Officer, superintendent decisions, alerts | 7 |
| Batches | 8 |
| Licensing Authority (W5) | 9 |
| Rule changes, Head Authority and Software Owner overview | 10 |
| Accessibility, responsiveness, i18n completeness | 11 |
