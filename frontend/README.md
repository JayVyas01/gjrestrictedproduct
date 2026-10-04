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

Vite runs in `--mode mock`, which reads `.env.mock` (`VITE_MOCK_API=1`). The MSW browser worker then answers
`/api` calls from the recorded API contracts (wired up in Task 2). The worker is never part of `npm run build`.

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
