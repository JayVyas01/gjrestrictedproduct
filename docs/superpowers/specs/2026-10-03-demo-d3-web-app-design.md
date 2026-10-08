# Demo D3: Web App Design

**Status:** draft for review · **Date:** 2026-10-03 · **Parent specs:** [licence types and demo design](2026-09-28-licence-types-and-demo-design.md) (§6 demo journeys, §7 UX principles), [routing and rule governance (Revision 4)](2026-10-03-routing-and-rule-governance-design.md)

**Built after D2c and D2d** (backend), which supply the APIs in §4.

## 1. Goal

Build the screens the authorities will see in the demo, on top of the APIs from D1–D2b. The demo must cover:

- the transaction journey: seller → buyer → designated officer
- the buyer-rejection scene: the alert reaches the officer and the superintendent
- the oversight scene: the superintendent flags a transaction, then signs off the batch
- the Licensing Authority's licence register and review-period screen

D3 is production quality: tested, accessible and secure. Demo tooling (seed data, the persona picker, the SMS inbox, `make demo`, Playwright and the script) belongs to D4.

## 2. Decisions

| # | Decision |
|---|---|
| W1 | **Stack.** React 18, TypeScript (strict) and Vite. Mantine 7 for components, React Router for routing, TanStack Query for server data, react-i18next for text. Package manager: npm with a committed lockfile. |
| W2 | **Visual direction A, "Navy official".** Deep navy app bar (`#1B365D`) on a light grey-blue page (`#F5F7FA`) with white cards. Saffron (`#E8A33D`) marks things that need attention: the bell count, the "What's next" accent and "awaiting you" badges. Status colours: green for approved, red for rejected, grey for cancelled. Every text and colour pair meets WCAG 2.1 AA contrast. The theme lives in `frontend/src/theme.ts` and nowhere else. |
| W3 | **One origin.** During development, the Vite dev server proxies `/api` to Django. In the demo and in production, Caddy serves the built app and proxies `/api` (the Compose wiring is in D4). Session cookies stay `SameSite=Strict` and CSRF protection stays as it is. |
| W4 | **Wizard drafts** are kept in `sessionStorage` for the current browser tab only. Logging out, the session ending and a successful submit all delete the draft. Nothing personal is ever written to `localStorage`. |
| W5 | **Licensing Authority scope.** A read-only licence register (search plus a permissions card), licence types and rules, and the screen for setting the superintendent review period. Rule changes go through proposals (Revision 4 R6), not direct editing. |
| W6 | **Server text.** Business refusals (`reasons`, `detail`) come from the backend in plain English and are shown as they are. All other text goes through the i18n files. When Gujarati arrives, the backend will send codes as well as messages. That is out of scope for D3 and noted in the follow-ups. |
| W7 | **Polling, no push.** The bell and the "What's next" counts refresh every 30 seconds, and immediately after any action the user takes. Push notifications come in Phase 2. |

## 3. Screens by role

The persona and the role in `/api/auth/me` decide the landing screen. Every home screen opens with a **What's next** card.

| Role | Screens |
|---|---|
| **All** | Sign in: user ID and password, then a 6-digit code. *Superseded by the 2026-10-06 demo accounts plan (`plans/2026-10-06-demo-accounts-and-csv.md`): the role first, then a party's GSTIN or an official's email and the password, then the code; a password the system issued must be changed at the first sign-in.* Session-expired notice. Sign out. Bell (personnel and authorities only). |
| **Licensee (seller and buyer)** | **Home:** What's next ("1 purchase waits for your confirmation"), licence permission cards, stock, recent transactions and a **New sale** button. **New sale wizard** (4 steps with a progress bar): 1. *Buyer* (GSTIN, then the registered name to confirm). 2. *Goods* (substance and quantity, with a live check that shows plain reasons before you can continue). 3. *Transport* (name, ID or licence number, vehicle, route). 4. *Review and send*. **Transactions:** a list with a "Sales" / "Purchases" filter. **Transaction detail:** timeline, transport, next action, cancel (seller, awaiting buyer) or confirm/reject (buyer) with the code dialog. When the sale would breach the buyer's stock limit, the buyer sees why and only **Reject** is offered, with the stock-limit reason filled in. |
| **Personnel: designated officer** | **Home:** What's next ("3 transactions wait for your approval"), the approval queue and unacknowledged alerts. **Transaction detail:** approve or reject (reason, then code); comments and who held the position appear on the timeline. **Alerts drawer** (from the bell): reason, pattern signal ("3rd buyer rejection for this seller in the last 30 days") and an acknowledge button with an optional note. |
| **Personnel: superintendent** | **Home:** What's next ("2 transactions wait for your final approval" and "Batch 1–15 Sep due in 12 days", with overdue in red), the final-approval queue, the batch list and alerts. **Transaction detail:** final approve or reject (code) on above-threshold transactions, with the officer's recommendation shown. **Batch review:** period, due date, status, and items with a flag action (reason and comment); items they approved are marked and can't be flagged. **Sign off batch** (code dialog). **Rule changes:** draft a proposal and see its status. |
| **Licensing Authority** | **Home:** What's next (licences expiring in 30 days, districts without a review period, your proposals awaiting decision). **Rule changes:** draft a new licence type, rule version or approval threshold, with a justification; see the status of your proposals. **Licence register:** exact search by licence number or GSTIN, filters by status and area, paginated. **Licence detail:** permission card, validity periods and status. **Licence types:** each type's rules (latest version) per substance or class. **Review periods:** each district's superintendent position, its current period and its next batch date, with a change dialog (15, 30 or 60 days). |
| **Head Authority** | **Home:** What's next ("2 rule changes wait for your approval"), and read-only lists of all transactions, alerts and batches, including a "Superintendent-approved" filter. **Rule change review:** a before/after comparison, the justification, and approve or reject with a code. Proposals they drafted themselves are shown but can't be approved by them. A persona in the demo. |
| **Software Owner** | **Home:** read-only lists of all transactions, alerts and batches, so this role never lands on an empty screen. |

### Shared components

| Component | Behaviour |
|---|---|
| `WhatsNextCard` | One sentence with one primary action. The counts come from `/api/home`. |
| `StatusTimeline` | Shows each step like a parcel tracker: who acted (position title), when (in IST), the outcome, the reason and the comment when present, and the holder for authorities. A pending step appears greyed out. |
| `CodeDialog` | Requests a code, then shows six digit inputs that take a pasted code. A 5-minute countdown and "Send a new code" are included. A wrong code shows "That code didn't match. Check the SMS or send a new code." |
| `ReasonPicker` | Loads the reason codes for its kind. Choosing "Other" reveals a required text box. |
| `StatusBadge` | Shows the status label in the colours from W2. "Awaiting you" appears when `can_decide` is true. |
| `PermissionCard` | Shows the licence type and scope, then the allowances buy/sell/transport as ticks and crosses, then the stock and per-transaction limits and the validity period. Suspended and expired licences get a clear banner. |
| `ErrorNotice` | Maps HTTP statuses to fix-it text: 400 field errors under each field, 401 a wrong code, 403 "You can't do this", 404 "Not found or not yours", 422 the listed reasons, 429 "Too many tries, wait a minute", 5xx "Something went wrong, try again". Raw codes are never shown. |

## 4. Backend additions (delivered in D2c and D2d)

Each addition is small and gets pytest coverage and a CODEMAP entry. B1–B4 and B6 ship in D2c; B7–B8 and the rule-change APIs ship in D2d.

| # | Change | Why |
|---|---|---|
| B1 | `GET /api/auth/me` also returns `display_name` and `positions` (`[{id, title, level}]`): the registered business name for a licensee, the position titles for personnel. | The app bar shows who you are; the screens adapt to held positions. |
| B2 | `GET /api/home` returns role-specific counts: `awaiting_your_decision`; `unacknowledged_alerts`; `open_batches`, `overdue_batches` and `next_due`; for the Licensing Authority, `expiring_licences_30d` and `districts_without_review_period`. All counts run under the caller's RLS. | The What's next card needs exact counts, not counts taken from a list capped at 50. |
| B3 | `GET /api/transactions?awaiting=me` and `?side=sales\|purchases`. The list stays capped at 50, newest first. | The officer queue and the licensee filter. |
| B4 | `POST /api/transactions/check` is a dry run of the start checks. It saves nothing, uses the `lookup` throttle and is audited like a buyer lookup (blind index only). It returns `{ok, reasons}`. | Step 2 of the wizard shows a block (for example "Quantity 600 L exceeds…") before the seller fills in the transport details. |
| B5 | **Replaced by Revision 4 R1.** The seller is never refused for the buyer's stock limit; the buyer decides. | The leak goes away because the seller never sees the buyer's numbers. |
| B6 | **Restore the "already acknowledged" message** without echoing exception text: `AlreadyAcknowledged(NotAllowed)`, with each case mapped to a fixed message in the view. | The CodeQL autofix in PR #6 collapsed both cases into "not allowed", which undoes ruling B-R2. |
| B7 | Licensing Authority APIs, open only to `role_required(LICENSING_AUTHORITY, HEAD_AUTHORITY, SOFTWARE_OWNER)`: `POST /api/licences/search` (exact search by licence number or GSTIN through the blind index, in the request body so neither value ever sits in a URL or a server log; CSRF and the `lookup` throttle; `status`, `area` and `page` in the body too; 25 per page); `GET /api/licences` (the plain listing with `?status=`, `?area=` and `?page=` only: `?number=` or `?gstin=` is refused with 400); `GET /api/licences/<id>` (card plus periods); `GET /api/catalogue/licence-types` (latest rule versions). Searches are audited by blind index. | The licence register (W5). |
| B8 | `GET /api/oversight/review-settings` lists each district position with its current setting and next batch date. `PUT /api/oversight/review-settings/<position_id>` takes `{period_days}`, is **Licensing Authority only** (this closes the CODEMAP follow-up "the service trusts its caller") and calls `set_review_period`; refusals are 422 with reasons. | The review-periods screen. |

## 5. Frontend structure

```
frontend/
  package.json, vite.config.ts (proxy /api → :8000), tsconfig.json, index.html
  src/
    main.tsx, App.tsx          providers: Mantine, Query, i18n, Router
    theme.ts                   W2 palette and Mantine theme (the only place for colours)
    i18n/en.json, i18n/index.ts
    api/client.ts              fetch wrapper: same-origin credentials, CSRF header, error mapping, session expiry
    api/*.ts                   one file per backend app (auth, transactions, alerts, oversight, licensing, home)
    auth/                      SignIn, session context, RequireRole
    components/                shared components (§3)
    features/licensee/         home, wizard, transactions
    features/officer/          home, queue
    features/superintendent/   home, batch review
    features/authority/        Licensing Authority screens
    features/governance/       rule-change drafting and review
    features/overview/         Head Authority / Software Owner read-only views
  tests/                       Vitest + Testing Library + MSW, plus axe checks
```

Rules:
- Components never call `fetch` directly. They use `api/*` through TanStack Query hooks.
- Each user-visible string is a key in `en.json`.

## 6. Security and privacy (frontend)

- **No tokens in JS.** Auth uses the existing HttpOnly session cookie. The CSRF token is read from the cookie and sent in `X-CSRFToken`.
- **No personal data in URLs.** GSTINs, transporter details and codes travel only in POST bodies. URLs carry only transaction references and numeric IDs.
- **Drafts** live in `sessionStorage` only (W4). Query caches are cleared when the user logs out or the session ends.
- **No `dangerouslySetInnerHTML`.** All server text renders as plain text.
- **Session expiry.** A 403 that `me` confirms as unauthenticated sends the user to sign-in with the message "Your session ended after 15 minutes of inactivity."
- **Content Security Policy** for Caddy (applied in D4): `default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'` (Mantine injects styles); `frame-ancestors 'none'`.
- **CI checks:** `npm audit --audit-level=high` runs in CI, and CodeQL also scans JavaScript/TypeScript.

## 7. Accessibility and responsiveness

- Meets WCAG 2.1 AA.
- Keyboard: every action works from the keyboard, with a visible focus ring and a skip-to-content link.
- Forms: labels sit next to inputs, and errors are linked to their fields with `aria-describedby`.
- Changes are announced: the timeline and toasts use `aria-live`.
- Every page passes an automated axe check in its component test.
- The layout works down to 360 px wide: the queue and lists become stacked cards.
- Dates show in IST with `en-IN` formatting, and quantities are always shown with their unit.

## 8. Testing

- **Backend:** pytest for B1–B8, including RLS cases, role refusals, audit entries and the B5 message.
- **Frontend:**
  - Vitest and Testing Library, with the API mocked through MSW
  - each screen gets a render test, its main interaction and an axe check
  - each shared component gets state tests
  - `api/client.ts` gets tests for CSRF, error mapping and session expiry
  - wizard tests cover draft save, restore and clear
- **End-to-end:** Playwright against the seeded demo is in D4.

## 9. CI and repository

- A new `frontend` job in `ci.yml` runs: `npm ci`, lint (ESLint), `tsc --noEmit`, Vitest, `vite build` and `npm audit`.
- CodeQL adds `javascript-typescript`.
- Dependabot adds the npm ecosystem.
- Adding `frontend` to the required checks of the "Protect dev and main" ruleset is a repository setting change, so it is done **only after the owner confirms**.

## 10. Out of scope (later)

- Push or SMS notifications (Phase 2)
- Personnel provisioning screens (Phase 4)
- Gujarati translations (W6)
- Everything in D4 (persona picker, SMS inbox, seed, Compose/Caddy, Playwright, script). The persona picker adds the Head Authority.
