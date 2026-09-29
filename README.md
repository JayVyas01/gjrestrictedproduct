# gjrestrictedproduct

Authorisation and audit platform for seller-initiated transactions of restricted items
in Gujarat. See `highlevel_plan.md` (design) and `docs/superpowers/plans/` (roadmap and plans).

## Branching and environments

| Branch | Environment | Rule |
|---|---|---|
| `dev` | Development (integration and testing) | Every change lands here first, through a pull request with CI green |
| `main` | Production | Only receives merges from `dev` once everything is tested and approved |

1. Branch from `dev` (for example `feature/licensing-domain`).
2. Open a pull request into `dev`. CI must pass before merging.
3. Test on `dev`. When a set of changes is cleared, open a pull request from `dev` into `main`.

Never commit or push directly to `main`. Hosted dev and prod deployments (India region) are added in the Hardening & go-live phase; until then, "environment" means the branch plus its CI run.

## Local setup (macOS)

1. Install `uv` (`brew install uv`) and Docker Desktop.
2. Start Postgres: `cp .env.example .env && docker compose up -d db`
3. Install the backend: `cd backend && uv sync`
4. Run the tests: `uv run --env-file .env.test pytest`

## Running the backend locally

```bash
cd backend
cp .env.example .env            # then fill in the generated keys and gj_app password
set -a; source .env; set +a     # load settings into this shell
DB_USER=gj_owner DB_PASSWORD=gj_owner_local_only uv run python manage.py migrate
DB_USER=gj_owner DB_PASSWORD=gj_owner_local_only uv run python manage.py createcachetable
uv run python manage.py create_software_owner
uv run python manage.py runserver
```

Migrations run as `gj_owner`; the app always runs as `gj_app`, which cannot change the schema,
bypass row-level security, or edit or delete audit records.

## Operations

- `python manage.py verify_audit_chain`: recompute the audit hash chain. Exits non-zero on tampering. Schedule it.
- Before every commit: `uv run ruff format . && uv run ruff check . && uv run --env-file .env.test pytest`
