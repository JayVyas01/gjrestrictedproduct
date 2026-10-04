# Gujarat Restricted Goods: web app

React 18, TypeScript (strict), Vite, Mantine 7, React Router 6, TanStack Query 5 and react-i18next.
The design is in [`docs/superpowers/specs/2026-10-03-demo-d3-web-app-design.md`](../docs/superpowers/specs/2026-10-03-demo-d3-web-app-design.md);
the code map is [`docs/CODEMAP.md`](../docs/CODEMAP.md).

Needs Node 22 (`/opt/homebrew/opt/node@22/bin` if it isn't on your PATH). Run every command from `frontend/`.

## Run

```sh
npm ci            # install exactly what package-lock.json says
npm run dev       # http://localhost:5173, forwards /api to the backend on 127.0.0.1:8000
```

Start the backend first (`cd backend && uv run --env-file .env python manage.py runserver 8000`, with Docker up).
The dev server forwards `/api`, so the browser sees one origin and the session cookie and CSRF token just work.

## Mock mode

```sh
npm run dev:mock  # http://localhost:5174, no backend needed
```

Vite runs in `--mode mock`, which reads `.env.mock` (`VITE_MOCK_API=1`). The MSW browser worker
(`public/mockServiceWorker.js`, from `npx msw init public --save`) then answers `/api` calls from the API contracts
in `src/test/contracts/`, the same handlers the tests use (`src/test/handlers.ts`). Pick who you are with `?as=`:
`seller`, `buyer`, `officer`, `superintendent`, `la` or `head` (remembered for the tab; seller by default).
You are signed in as that persona straight away; `/sign-in` also works with any user ID, password and
6-digit code, and then lands on the persona's home.
The worker is never part of `npm run build`: `main.tsx` imports it only in dev mock mode, and the build drops
`mockServiceWorker.js` from `dist/`.

## API contracts

The contracts are captured from the real backend by `backend/tests/test_api_contracts.py`. After changing an
endpoint, regenerate and commit them:

```sh
cd backend && UPDATE_CONTRACTS=1 uv run --env-file .env.test pytest tests/test_api_contracts.py
```

Without `UPDATE_CONTRACTS` the backend test fails when a response's shape no longer matches its file, and
`src/api/contracts.test.ts` fails when a file no longer matches its type in `src/api/types.ts`. In a test, serve
another contract for one endpoint with `server.use(serveContract("transaction_detail_buyer_stock_limit"))`.

## Check

| Purpose | Command |
|---|---|
| Tests (Vitest, Testing Library, MSW, axe) | `npm test` (`npm run test:watch` while working) |
| Lint (ESLint: typescript-eslint, react-hooks, jsx-a11y) | `npm run lint` |
| Type check | `npm run typecheck` |
| Production build | `npm run build` (output in `dist/`, no source maps) |
| Dependency audit | `npm audit --audit-level=high` |

CI runs all of these in the `frontend` job.

## Rules

- All user-visible text comes from `src/i18n/en.json` through `t()`.
- Only `src/api/` talks to the server; components use the query hooks in `src/api/hooks/`.
- Colours live only in `src/theme.ts`.
- No `localStorage` and no `dangerouslySetInnerHTML` (ESLint enforces both).
- Every page test includes an axe check (`expect(await axe(container)).toHaveNoViolations()`).
- Tests render through `renderWithProviders` in `src/test/render.tsx`. Unhandled requests fail the test.
