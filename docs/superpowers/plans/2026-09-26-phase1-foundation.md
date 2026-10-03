# Phase 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A secure, tested Django + Postgres backend skeleton with least-privilege DB roles, field encryption, a user/role model, RLS context plumbing, a hash-chained append-only audit log, and password + OTP login with lockout and rate limiting.

**Architecture:** Modular monolith in `backend/`: `config` (settings/urls), `core` (shared plumbing: env, DB privileges, RLS context, crypto), `identity` (users, roles, OTP, login), `audit` (hash-chained trail). The app talks to Postgres as the non-owner role `gj_app` (no `BYPASSRLS`); migrations run as `gj_owner`. Every request runs in one transaction tagged with the acting user and role (`app.user_id`, `app.role`) so Postgres row-level security can enforce access independently of Python code.

**Tech Stack:** Python 3.12, Django 5.2 LTS, Django REST Framework 3.17, PostgreSQL 16, psycopg 3, argon2-cffi, cryptography (Fernet), pytest + pytest-django, ruff, pip-audit, uv, GitHub Actions, Docker Compose (local Postgres only).

**Spec:** [`highlevel_plan.md`](../../../highlevel_plan.md) · **Roadmap:** [`2026-09-26-roadmap.md`](2026-09-26-roadmap.md)

## Global Constraints

- Versions: Python `>=3.12,<3.13`; Django `>=5.2,<5.3`; DRF `>=3.17.2,<3.18` (raised from 3.16 by Ruling R5: PYSEC-2026-3827/3828); psycopg `>=3.2,<3.3`; PostgreSQL 16.
- Tech stack is fixed by the spec: Django backend, React frontend (the frontend starts in Phase 2), Postgres.
- The app role `gj_app` must never own tables, have `BYPASSRLS`, or run DDL. Migrations run as `gj_owner`.
- Records are never edited or deleted. Append-only tables get `REVOKE UPDATE, DELETE, TRUNCATE ... FROM gj_app` plus a trigger. Any migration that revokes privileges must depend on `("core", "0001_app_role_privileges")`.
- Sensitive identifiers and contacts are stored only encrypted (`core.crypto.encrypt`). Exact-match lookups use `core.crypto.blind_index`.
- Deny by default: DRF default permission is `IsAuthenticated`. Only login, CSRF and health endpoints opt out.
- Authentication failures return one generic message (`"Invalid credentials"`), with no hint about whether a user exists.
- No secrets in the repo. The only exception is `backend/.env.test`, which holds clearly labelled test-only values for the local and CI test database.
- Never log PII or OTP codes. `ConsoleOtpSender` refuses to run unless `DEBUG` is on.
- Tests that exercise application behaviour use the `app_db` fixture, so they run as `gj_app` like production. Never use `transactional_db`, because its TRUNCATE teardown is blocked by the audit trigger by design.
- No service that stores data outside India (spec: data residency, DPDP Act 2023).
- Code style: one responsibility per file, a module docstring explaining why the file exists, type hints on public functions, and functions of roughly 40 lines or fewer.
- Before every commit, run from `backend/`: `uv run ruff format . && uv run ruff check . && uv run --env-file .env.test pytest`. All three must pass.

## Decisions made in this plan (flag to reviewer)

1. **Roles are a fixed enum (`identity.roles.Role`), not a `roles` table.** Per the [2026-09-28 design](../specs/2026-09-28-licence-types-and-demo-design.md), buyer and seller are a single `LICENSEE` role (buy and sell rights come from licences). The spec's role set is fixed and legally defined, and an enum plus a DB check constraint is simpler and easier to audit. It can be revisited if roles ever need to be configured at runtime.
2. **Identity tables (`identity_user`, `identity_otpchallenge`) are not under RLS.** They must be read before anyone is authenticated (at login). They are protected by app-layer checks, encrypted contacts, and `REVOKE DELETE`. RLS covers the audit log now and every business table from Phase 2 onward. A security reviewer should confirm this.
3. **Sessions are server-side Django sessions in HttpOnly, Secure, SameSite=Strict cookies, not JWTs.** They are simpler and can be revoked server-side.
4. **Deferred to later phases per the roadmap:** session listing and revocation (Phase 2), personnel provisioning and forced password change (Phase 4), and audit anchoring to a WORM store (Phase 5).

## File Structure

```
.env.example                          # local docker-compose DB passwords (copy to .env)
docker-compose.yml                    # local Postgres 16 bound to 127.0.0.1
docker/postgres-init.sh               # creates gj_owner / gj_app roles + gjrp database
.github/workflows/ci.yml              # lint, tests, audit, deploy checks
.github/dependabot.yml                # weekly dependency + action updates
backend/
  pyproject.toml, uv.lock, manage.py
  .env.test                           # TEST-ONLY settings (committed)
  .env.example                        # template for local dev settings (real .env is gitignored)
  config/env.py                       # read env vars, fail fast when missing
  config/settings.py, urls.py, wsgi.py
  core/apps.py
  core/views.py                       # /api/health
  core/migrations/0001_app_role_privileges.py
  core/crypto.py                      # field encryption + blind index
  core/db_context.py                  # set_actor(): tell Postgres who is acting (RLS)
  core/middleware.py                  # DbContextMiddleware: one transaction per request
  identity/roles.py                   # Role enum + role groups
  identity/models.py                  # User, OtpChallenge
  identity/otp.py                     # issue/verify one-time codes
  identity/otp_delivery.py            # OtpSender interface + dev/test senders
  identity/login.py                   # password step with lockout
  identity/permissions.py             # role_required() for DRF views
  identity/serializers.py, views.py, urls.py
  identity/management/commands/create_software_owner.py
  audit/hashing.py                    # pure hash-chain functions
  audit/models.py                     # AuditEvent, AuditChainHead
  audit/service.py                    # record()
  audit/verify.py                     # verify_chain()
  audit/management/commands/verify_audit_chain.py
  tests/conftest.py + tests/test_*.py
```

---

### Task 1: Backend scaffold with fail-fast settings and health endpoint

**Files:**
- Create: `backend/pyproject.toml`, `backend/manage.py`, `backend/.env.test`
- Create: `backend/config/__init__.py`, `backend/config/env.py`, `backend/config/settings.py`, `backend/config/urls.py`, `backend/config/wsgi.py`
- Create: `backend/core/__init__.py`, `backend/core/apps.py`, `backend/core/views.py`, `backend/core/migrations/__init__.py`
- Create: `docker-compose.yml`, `docker/postgres-init.sh`, `.env.example`
- Test: `backend/tests/test_env.py`, `backend/tests/test_health.py`

**Interfaces:**
- Produces: `config.env.required(name) -> str`, `config.env.optional(name, default) -> str`, `config.env.flag(name, default=False) -> bool`, `config.env.listed(name) -> list[str]`, `config.env.MissingSetting`; `GET /api/health -> {"status": "ok"}`; local Postgres with roles `gj_owner` (owner, CREATEDB) and `gj_app` (runtime, NOBYPASSRLS), database `gjrp`.

- [ ] **Step 1: Install prerequisites (macOS)**

Run:
```bash
brew install uv
```
Install Docker Desktop (https://www.docker.com/products/docker-desktop/) and start it. Check with `uv --version` and `docker compose version`.

- [ ] **Step 2: Create local database files**

`docker/postgres-init.sh` (make it executable with `chmod +x docker/postgres-init.sh`):
```bash
#!/usr/bin/env bash
# Creates the two database roles the application uses:
#   gj_owner - owns the schema, runs migrations and tests (never used by the running app)
#   gj_app   - the running application: no ownership, no DDL, cannot bypass row-level security
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" \
  -v owner_pw="$GJ_OWNER_PASSWORD" -v app_pw="$GJ_APP_PASSWORD" <<'SQL'
CREATE ROLE gj_owner LOGIN CREATEDB NOSUPERUSER NOCREATEROLE PASSWORD :'owner_pw';
CREATE ROLE gj_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD :'app_pw';
-- Lets tests run "SET ROLE gj_app" to exercise production privileges.
GRANT gj_app TO gj_owner;
CREATE DATABASE gjrp OWNER gj_owner;
REVOKE ALL ON DATABASE gjrp FROM PUBLIC;
GRANT CONNECT ON DATABASE gjrp TO gj_app;
SQL
```

`docker-compose.yml`:
```yaml
# Local development database only. Production uses a managed Postgres in an India region.
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_SUPERUSER_PASSWORD:?copy .env.example to .env}
      GJ_OWNER_PASSWORD: ${GJ_OWNER_PASSWORD:?copy .env.example to .env}
      GJ_APP_PASSWORD: ${GJ_APP_PASSWORD:?copy .env.example to .env}
    ports:
      - "127.0.0.1:5432:5432"
    volumes:
      - ./docker/postgres-init.sh:/docker-entrypoint-initdb.d/10-roles.sh:ro
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

`.env.example`:
```
# Local development database only (bound to 127.0.0.1). Copy to .env - never commit .env.
POSTGRES_SUPERUSER_PASSWORD=change-me-local-superuser
# Must match DB_PASSWORD in backend/.env.test so the test suite can connect.
GJ_OWNER_PASSWORD=gj_owner_local_only
GJ_APP_PASSWORD=change-me-local-app
```

Run:
```bash
cp .env.example .env
docker compose up -d db
```
Expected: `docker compose ps` shows `db` running.

- [ ] **Step 3: Create the Python project**

`backend/pyproject.toml`:
```toml
[project]
name = "gjrp-backend"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
dependencies = [
    "django>=5.2,<5.3",
    "djangorestframework>=3.17.2,<3.18",
    "psycopg[binary]>=3.2,<3.3",
    "argon2-cffi>=23.1",
    "cryptography>=43",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-django>=4.9",
    "ruff>=0.6",
    "pip-audit>=2.7",
]

[tool.uv]
package = false

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings"
pythonpath = ["."]
testpaths = ["tests"]
addopts = "--strict-markers"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
# E/F: errors, I: import order, B: likely bugs, S: security (bandit rules), UP: modern syntax
select = ["E", "F", "I", "B", "S", "UP"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "S105", "S106"]
```

`backend/.env.test`:
```
# TEST-ONLY values for the local/CI test database. Never use these anywhere else.
DJANGO_SECRET_KEY=test-only-secret-key-not-for-any-real-deployment-0123456789
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=testserver,localhost
DJANGO_SSL_REDIRECT=0
DB_NAME=gjrp
DB_USER=gj_owner
DB_PASSWORD=gj_owner_local_only
DB_HOST=localhost
DB_PORT=5432
DB_SSLMODE=disable
```

Run (from `backend/`):
```bash
uv sync
```
Expected: creates `.venv` and `uv.lock`.

- [ ] **Step 4: Write the failing tests**

`backend/tests/test_env.py`:
```python
import pytest

from config import env


def test_required_returns_trimmed_value(monkeypatch):
    monkeypatch.setenv("GJ_SAMPLE", " value ")
    assert env.required("GJ_SAMPLE") == "value"


def test_required_fails_fast_when_missing(monkeypatch):
    monkeypatch.delenv("GJ_SAMPLE", raising=False)
    with pytest.raises(env.MissingSetting, match="GJ_SAMPLE"):
        env.required("GJ_SAMPLE")


def test_required_fails_fast_when_blank(monkeypatch):
    monkeypatch.setenv("GJ_SAMPLE", "   ")
    with pytest.raises(env.MissingSetting):
        env.required("GJ_SAMPLE")


def test_optional_uses_default_when_unset(monkeypatch):
    monkeypatch.delenv("GJ_SAMPLE", raising=False)
    assert env.optional("GJ_SAMPLE", "fallback") == "fallback"


def test_flag_parses_truthy_and_falsy(monkeypatch):
    monkeypatch.setenv("GJ_FLAG", "True")
    assert env.flag("GJ_FLAG") is True
    monkeypatch.setenv("GJ_FLAG", "0")
    assert env.flag("GJ_FLAG") is False


def test_flag_default_when_unset(monkeypatch):
    monkeypatch.delenv("GJ_FLAG", raising=False)
    assert env.flag("GJ_FLAG", default=True) is True


def test_listed_splits_and_trims(monkeypatch):
    monkeypatch.setenv("GJ_LIST", "a.example, b.example ,")
    assert env.listed("GJ_LIST") == ["a.example", "b.example"]
```

`backend/tests/test_health.py`:
```python
def test_health_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_rejects_post(client):
    assert client.post("/api/health").status_code == 405


def test_security_headers_present(client):
    response = client.get("/api/health")
    assert response["X-Frame-Options"] == "DENY"
    assert response["X-Content-Type-Options"] == "nosniff"
```

- [ ] **Step 5: Run the tests to verify they fail**

Run: `uv run --env-file .env.test pytest -v`
Expected: FAIL / collection error, `ModuleNotFoundError: No module named 'config'`.

- [ ] **Step 6: Write the implementation**

`backend/config/__init__.py` and `backend/core/__init__.py` and `backend/core/migrations/__init__.py`: empty files.

`backend/config/env.py`:
```python
"""Read configuration from environment variables.

Missing required values stop the process at startup instead of silently
falling back to an insecure default.
"""

import os


class MissingSetting(RuntimeError):
    pass


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise MissingSetting(f"Environment variable {name} must be set")
    return value


def optional(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes"}


def listed(name: str) -> list[str]:
    return [item.strip() for item in required(name).split(",") if item.strip()]
```

`backend/config/settings.py`:
```python
"""Django settings.

Every environment-specific or secret value comes from environment variables
(see backend/.env.example). Nothing secret lives in this file.
"""

from pathlib import Path

from config import env

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = env.required("DJANGO_SECRET_KEY")
DEBUG = env.flag("DJANGO_DEBUG")
ALLOWED_HOSTS = env.listed("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env.required("DB_NAME"),
        "USER": env.required("DB_USER"),
        "PASSWORD": env.required("DB_PASSWORD"),
        "HOST": env.required("DB_HOST"),
        "PORT": env.optional("DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
        # Production must use "verify-full".
        "OPTIONS": {"sslmode": env.optional("DB_SSLMODE", "verify-full")},
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = False
USE_TZ = True

# --- Transport and browser security ---------------------------------------
SECURE_SSL_REDIRECT = env.flag("DJANGO_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = 0 if DEBUG else 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
# HSTS preload is a go-live decision for the production domain (roadmap Phase 6).
SILENCED_SYSTEM_CHECKS = ["security.W021"]
```

`backend/config/urls.py`:
```python
from django.urls import path

from core.views import health

urlpatterns = [
    path("api/health", health),
]
```

`backend/config/wsgi.py`:
```python
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_wsgi_application()
```

`backend/manage.py`:
```python
#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
```

`backend/core/apps.py`:
```python
from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"
```

`backend/core/views.py`:
```python
"""Liveness endpoint for the load balancer. Touches no data."""

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def health(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run --env-file .env.test pytest -v`
Expected: 10 passed.

- [ ] **Step 8: Commit**

```bash
uv run ruff format . && uv run ruff check .
cd .. && git add .env.example docker-compose.yml docker/ backend/
git commit -m "feat: backend scaffold with fail-fast settings, health endpoint, local Postgres roles"
```

---

### Task 2: CI pipeline and dependency updates

**Files:**
- Create: `.github/workflows/ci.yml`, `.github/dependabot.yml`

**Interfaces:**
- Consumes: `docker/postgres-init.sh` and `backend/.env.test` from Task 1.
- Produces: a CI gate that later tasks rely on (lint, format, migrations check, tests, dependency audit, deploy checks).

- [ ] **Step 1: Write the workflow**

`.github/workflows/ci.yml`:
```yaml
name: ci

on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

jobs:
  backend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres_ci_only
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U postgres"
          --health-interval 5s --health-timeout 5s --health-retries 10
    steps:
      # Pin actions to full commit SHAs before go-live (Dependabot keeps them current).
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          python-version: "3.12"

      - name: Create database roles
        working-directory: .
        env:
          PGHOST: localhost
          PGPASSWORD: postgres_ci_only
          POSTGRES_USER: postgres
          GJ_OWNER_PASSWORD: gj_owner_local_only
          GJ_APP_PASSWORD: gj_app_ci_only
        run: bash docker/postgres-init.sh

      - run: uv sync --locked
      - run: uv run ruff format --check .
      - run: uv run ruff check .
      - run: uv run --env-file .env.test python manage.py makemigrations --check --dry-run
      - run: uv run --env-file .env.test pytest

      - name: Dependency vulnerability audit
        run: |
          uv export --format requirements-txt --no-emit-project --output-file "$RUNNER_TEMP/req.txt"
          uv run pip-audit --disable-pip --requirement "$RUNNER_TEMP/req.txt"

      - name: Production settings check
        run: |
          set -a; source .env.test; set +a
          export DJANGO_SSL_REDIRECT=1
          export DJANGO_SECRET_KEY="ci-deploy-check-$(openssl rand -hex 32)"
          uv run python manage.py check --deploy --fail-level WARNING
```

`.github/dependabot.yml`:
```yaml
version: 2
updates:
  - package-ecosystem: "uv"
    directory: "/backend"
    schedule:
      interval: "weekly"
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```

- [ ] **Step 2: Run the same checks locally**

Run (from `backend/`):
```bash
uv run ruff format --check . && uv run ruff check . && \
uv run --env-file .env.test python manage.py makemigrations --check --dry-run && \
uv run --env-file .env.test pytest
```
Expected: all pass, `No changes detected`.

Run the deploy check:
```bash
(set -a; source .env.test; set +a; export DJANGO_SSL_REDIRECT=1 DJANGO_SECRET_KEY="local-deploy-check-$(openssl rand -hex 32)"; uv run python manage.py check --deploy --fail-level WARNING)
```
Expected: `System check identified no issues`.

- [ ] **Step 3: Commit, push, and confirm CI is green**

```bash
git add .github/
git commit -m "ci: lint, tests, migrations check, dependency audit, deploy check"
git push -u origin foundation/scaffold
```
Expected: the `ci` workflow passes on GitHub.

---

### Task 3: Least-privilege application database role

**Files:**
- Create: `backend/core/migrations/0001_app_role_privileges.py`
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/test_db_privileges.py`

**Interfaces:**
- Consumes: roles `gj_owner`/`gj_app` from Task 1.
- Produces: migration `("core", "0001_app_role_privileges")`, which grants DML on all current and future tables to `gj_app`; pytest fixture `app_db`, which runs the test as `gj_app`.

- [ ] **Step 1: Write the fixture and failing tests**

`backend/tests/conftest.py`:
```python
"""Shared test fixtures.

Use `app_db` (not `db`) for anything that exercises application behaviour, so the test runs
with the same restricted privileges as production. Use plain `db` only when a test must act as
the schema owner, for example to simulate an attacker tampering with the audit table.
Never use `transactional_db`: its TRUNCATE-based teardown is blocked by the audit trigger.
"""

import pytest
from django.db import connection


@pytest.fixture
def app_db(db):
    # SET ROLE is undone automatically when the test transaction rolls back.
    with connection.cursor() as cursor:
        cursor.execute("SET ROLE gj_app")
```

`backend/tests/test_db_privileges.py`:
```python
import pytest
from django.db import DatabaseError, connection, transaction

pytestmark = pytest.mark.django_db


def test_app_role_is_not_superuser_and_cannot_bypass_rls():
    with connection.cursor() as cursor:
        cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'gj_app'")
        assert cursor.fetchone() == (False, False)


def test_app_role_owns_no_tables():
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM pg_tables WHERE tableowner = 'gj_app'")
        assert cursor.fetchone()[0] == 0


def test_app_role_can_use_migrated_tables(app_db):
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM django_migrations")
        assert cursor.fetchone()[0] > 0


def test_tables_created_later_are_granted_to_app_role(db):
    with connection.cursor() as cursor:
        cursor.execute("CREATE TABLE later_table (id int)")
        cursor.execute("SET ROLE gj_app")
        cursor.execute("INSERT INTO later_table VALUES (1)")
        cursor.execute("SELECT count(*) FROM later_table")
        assert cursor.fetchone()[0] == 1


def test_app_role_cannot_create_tables(app_db):
    with pytest.raises(DatabaseError, match="permission denied"):
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("CREATE TABLE should_fail (id int)")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --env-file .env.test pytest tests/test_db_privileges.py -v`
Expected: `test_app_role_can_use_migrated_tables` and `test_tables_created_later_are_granted_to_app_role` FAIL with `permission denied`.

- [ ] **Step 3: Write the migration**

`backend/core/migrations/0001_app_role_privileges.py`:
```python
"""Give the runtime role (gj_app) data access, and nothing else.

Grants cover tables that already exist AND tables created later by the migration
role, so migration order never matters. Tables that must be append-only revoke
UPDATE/DELETE in their own migration, which must depend on this one.
"""

from django.db import migrations

GRANT = """
GRANT USAGE ON SCHEMA public TO gj_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO gj_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO gj_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO gj_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO gj_app;
"""

REVOKE = """
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM gj_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    REVOKE USAGE, SELECT ON SEQUENCES FROM gj_app;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM gj_app;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM gj_app;
"""


class Migration(migrations.Migration):
    dependencies = []
    operations = [migrations.RunSQL(sql=GRANT, reverse_sql=REVOKE)]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --env-file .env.test pytest -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
uv run ruff format . && uv run ruff check .
git add core/migrations/0001_app_role_privileges.py tests/conftest.py tests/test_db_privileges.py
git commit -m "feat: least-privilege gj_app role with default grants and app_db test fixture"
```

---

### Task 4: Field-level encryption and blind index

**Files:**
- Create: `backend/core/crypto.py`
- Modify: `backend/config/settings.py` (append keys), `backend/.env.test` (append test keys)
- Test: `backend/tests/test_crypto.py`

**Interfaces:**
- Produces: `core.crypto.encrypt(plaintext: str) -> str`, `core.crypto.decrypt(token: str) -> str` (raises `core.crypto.DecryptionError`), `core.crypto.blind_index(value: str) -> str` (64 hex chars; normalises trim + uppercase).

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_crypto.py`:
```python
import pytest
from cryptography.fernet import Fernet

from core.crypto import DecryptionError, blind_index, decrypt, encrypt

CONTACT = "+91 98765 43210"


def test_encrypt_round_trip():
    assert decrypt(encrypt(CONTACT)) == CONTACT


def test_ciphertext_does_not_reveal_plaintext():
    assert "98765" not in encrypt(CONTACT)


def test_encryption_is_randomised():
    assert encrypt(CONTACT) != encrypt(CONTACT)


def test_decrypt_rejects_garbage():
    with pytest.raises(DecryptionError):
        decrypt("not-a-token")


def test_decrypt_rejects_value_encrypted_with_another_key(settings):
    token = encrypt(CONTACT)
    settings.FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()
    with pytest.raises(DecryptionError):
        decrypt(token)


def test_blind_index_is_deterministic_and_normalised():
    assert blind_index(" gj/lic/001 ") == blind_index("GJ/LIC/001")
    assert len(blind_index("GJ/LIC/001")) == 64


def test_blind_index_differs_between_values():
    assert blind_index("GJ/LIC/001") != blind_index("GJ/LIC/002")


def test_blind_index_depends_on_secret_key(settings):
    before = blind_index("GJ/LIC/001")
    settings.BLIND_INDEX_KEY = "another-test-key"
    assert blind_index("GJ/LIC/001") != before
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --env-file .env.test pytest tests/test_crypto.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'core.crypto'`.

- [ ] **Step 3: Write the implementation**

Append to `backend/.env.test`:
```
FIELD_ENCRYPTION_KEY=MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=
BLIND_INDEX_KEY=test-only-blind-index-key
```

Append to `backend/config/settings.py`:
```python
# --- Field-level encryption (keys come from the secrets vault in production) ----
FIELD_ENCRYPTION_KEY = env.required("FIELD_ENCRYPTION_KEY")  # Fernet key
BLIND_INDEX_KEY = env.required("BLIND_INDEX_KEY")
```

`backend/core/crypto.py`:
```python
"""Field-level encryption and blind indexes for sensitive identifiers.

- encrypt/decrypt: reversible, for values we must show or use again (e.g. an OTP contact).
- blind_index: one-way keyed hash, for exact-match lookup (e.g. licence number) without
  storing the plaintext. Partial or fuzzy search is deliberately impossible.
"""

import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


class DecryptionError(Exception):
    pass


def _fernet() -> Fernet:
    return Fernet(settings.FIELD_ENCRYPTION_KEY.encode())


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise DecryptionError("Value could not be decrypted") from exc


def blind_index(value: str) -> str:
    normalised = value.strip().upper()
    key = settings.BLIND_INDEX_KEY.encode()
    return hmac.new(key, normalised.encode(), hashlib.sha256).hexdigest()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --env-file .env.test pytest -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
uv run ruff format . && uv run ruff check .
git add core/crypto.py config/settings.py .env.test tests/test_crypto.py
git commit -m "feat: field-level encryption and blind index helpers"
```

---

### Task 5: User model and roles

**Files:**
- Create: `backend/identity/__init__.py`, `backend/identity/apps.py`, `backend/identity/roles.py`, `backend/identity/models.py`, `backend/identity/migrations/__init__.py`
- Create (generated): `backend/identity/migrations/0001_initial.py`
- Create: `backend/identity/migrations/0002_protect_users.py`
- Modify: `backend/config/settings.py`, `backend/tests/conftest.py`
- Test: `backend/tests/test_users.py`

**Interfaces:**
- Consumes: `core.crypto.encrypt/decrypt`.
- Produces: `identity.roles.Role` (`LICENSEE`, `PERSONNEL`, `LICENSING_AUTHORITY`, `SOFTWARE_OWNER`, `HEAD_AUTHORITY`); `identity.roles.AUDIT_READERS`, `identity.roles.PERSONNEL_PROVISIONERS` (frozensets of `Role`); `identity.models.User` with fields `user_id` (e.g. `GJ7K2M...`, 12 chars), `role`, `contact_encrypted`, `is_active`, `failed_login_count`, `locked_until`, `created_at`, and methods `get_contact() -> str`, `set_contact(contact: str)`, `has_role(*roles) -> bool`; `User.objects.create_user(*, role, password, contact) -> User`; conftest fixture `make_user(role=Role.LICENSEE, password=TEST_PASSWORD, contact=...) -> User` and constant `TEST_PASSWORD`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_users.py`:
```python
import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction

from identity.models import USER_ID_ALPHABET, User
from identity.roles import Role

pytestmark = pytest.mark.django_db


def test_user_id_is_system_generated(app_db, make_user):
    user = make_user()
    assert len(user.user_id) == 12
    assert user.user_id.startswith("GJ")
    assert all(ch in USER_ID_ALPHABET for ch in user.user_id[2:])


def test_user_ids_are_unique(app_db, make_user):
    assert make_user().user_id != make_user().user_id


def test_password_is_hashed_with_argon2(app_db, make_user):
    user = make_user(password="a-long-test-password")
    assert user.password.startswith("argon2")
    assert user.check_password("a-long-test-password")


def test_contact_is_encrypted_at_rest(app_db, make_user):
    user = make_user(contact="+919876543210")
    with connection.cursor() as cursor:
        cursor.execute("SELECT contact_encrypted FROM identity_user WHERE id = %s", [user.id])
        raw = cursor.fetchone()[0]
    assert "9876543210" not in raw
    assert User.objects.get(pk=user.pk).get_contact() == "+919876543210"


def test_database_rejects_unknown_role(app_db):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            User.objects.create(role="SUPERHERO", contact_encrypted="x")


def test_has_role(app_db, make_user):
    user = make_user(role=Role.LICENSEE)
    assert user.has_role(Role.LICENSEE, Role.PERSONNEL)
    assert not user.has_role(Role.PERSONNEL)


def test_inactive_user_has_no_role(app_db, make_user):
    user = make_user(role=Role.LICENSEE)
    user.is_active = False
    assert not user.has_role(Role.LICENSEE)


def test_app_role_cannot_delete_users(app_db, make_user):
    user = make_user()
    with pytest.raises(DatabaseError, match="permission denied"):
        with transaction.atomic():
            User.objects.filter(pk=user.pk).delete()
```

Add to `backend/tests/conftest.py` (imports go at the top of the file):
```python
from identity.models import User
from identity.roles import Role

TEST_PASSWORD = "correct-horse-battery-9"


@pytest.fixture
def make_user(db):
    def _make(role=Role.LICENSEE, password=TEST_PASSWORD, contact="+919800000001") -> User:
        return User.objects.create_user(role=role, password=password, contact=contact)

    return _make
```
- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --env-file .env.test pytest tests/test_users.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'identity'`.

- [ ] **Step 3: Write the implementation**

`backend/identity/__init__.py`, `backend/identity/migrations/__init__.py`: empty.

`backend/identity/apps.py`:
```python
from django.apps import AppConfig


class IdentityConfig(AppConfig):
    name = "identity"
```

`backend/identity/roles.py`:
```python
"""The fixed set of roles defined by the spec, and which roles share which powers.

Roles are an enum (not a table) because they are legally defined and must not be
changed at runtime. Every permission check refers to these names.
"""

from django.db import models


class Role(models.TextChoices):
    # What a licensee may buy, sell or transport comes from their licences, not their role.
    LICENSEE = "LICENSEE", "Licensee"
    PERSONNEL = "PERSONNEL", "Authorised Personnel"
    LICENSING_AUTHORITY = "LICENSING_AUTHORITY", "Licensing Authority"
    SOFTWARE_OWNER = "SOFTWARE_OWNER", "Software Owner"
    HEAD_AUTHORITY = "HEAD_AUTHORITY", "Head Authority"


# Spec rule 5: only these roles may create or reset Authorised Personnel accounts.
PERSONNEL_PROVISIONERS = frozenset({Role.SOFTWARE_OWNER, Role.HEAD_AUTHORITY})

# Roles allowed to read the full audit trail. Must match the RLS policy in audit migration 0002.
AUDIT_READERS = frozenset({Role.SOFTWARE_OWNER, Role.HEAD_AUTHORITY})
```

`backend/identity/models.py`:
```python
"""User accounts.

Users never choose their own ID: it is generated here. The OTP contact is stored
encrypted and can only be set by trusted server code, never by the user.
"""

import secrets

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models

from core import crypto
from identity.roles import Role

# No 0/O or 1/I, so IDs can be read aloud or copied without mistakes.
USER_ID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_user_id() -> str:
    return "GJ" + "".join(secrets.choice(USER_ID_ALPHABET) for _ in range(10))


class UserManager(BaseUserManager):
    def create_user(self, *, role: str, password: str, contact: str) -> "User":
        user = self.model(role=role)
        user.set_contact(contact)
        user.set_password(password)
        user.save()
        return user


class User(AbstractBaseUser):
    user_id = models.CharField(max_length=12, unique=True, default=generate_user_id, editable=False)
    role = models.CharField(max_length=32, choices=Role.choices)
    contact_encrypted = models.TextField()
    is_active = models.BooleanField(default=True)
    failed_login_count = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "user_id"
    REQUIRED_FIELDS = ["role"]

    objects = UserManager()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(role__in=Role.values), name="user_role_valid"),
        ]

    def set_contact(self, contact: str) -> None:
        self.contact_encrypted = crypto.encrypt(contact)

    def get_contact(self) -> str:
        return crypto.decrypt(self.contact_encrypted)

    def has_role(self, *roles: str) -> bool:
        return self.is_active and self.role in roles
```

Modify `backend/config/settings.py`. Replace the `INSTALLED_APPS` list and add the auth settings below it:
```python
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "core",
    "identity",
]

AUTH_USER_MODEL = "identity.User"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.Argon2PasswordHasher"]
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
```

Generate the model migration:
```bash
uv run --env-file .env.test python manage.py makemigrations identity
```
Expected: creates `identity/migrations/0001_initial.py`.

`backend/identity/migrations/0002_protect_users.py`:
```python
"""Accounts are never deleted (spec rule 2): deactivate instead."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("identity", "0001_initial"),
        ("core", "0001_app_role_privileges"),
    ]
    operations = [
        migrations.RunSQL(
            sql="REVOKE DELETE, TRUNCATE ON identity_user FROM gj_app;",
            reverse_sql="GRANT DELETE ON identity_user TO gj_app;",
        ),
    ]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --env-file .env.test pytest -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
uv run ruff format . && uv run ruff check .
git add identity/ config/settings.py tests/conftest.py tests/test_users.py
git commit -m "feat: user model with generated IDs, fixed roles, argon2, encrypted contact"
```

---

### Task 6: Row-level-security request context

**Files:**
- Create: `backend/core/db_context.py`, `backend/core/middleware.py`
- Modify: `backend/config/settings.py` (append middleware)
- Test: `backend/tests/test_db_context.py`

**Interfaces:**
- Consumes: `identity.models.User` (`user_id`, `role`, `is_authenticated`).
- Produces: `core.db_context.set_actor(*, user_id: str, role: str) -> None` (only valid inside `transaction.atomic()`), `core.db_context.current_actor() -> tuple[str | None, str | None]`, `core.db_context.SYSTEM_ROLE = "SYSTEM"`; `core.middleware.DbContextMiddleware`. RLS policies read `current_setting('app.user_id', true)` and `current_setting('app.role', true)`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_db_context.py`:
```python
import pytest
from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.http import HttpResponse

from core.db_context import current_actor, set_actor
from core.middleware import DbContextMiddleware
from identity.models import User
from identity.roles import Role

pytestmark = pytest.mark.django_db


def test_set_actor_is_visible_to_postgres(app_db):
    set_actor(user_id="GJTESTUSER01", role=Role.LICENSEE)
    assert current_actor() == ("GJTESTUSER01", "LICENSEE")


def test_set_actor_refuses_to_run_outside_a_transaction(app_db, monkeypatch):
    monkeypatch.setattr(connection, "in_atomic_block", False)
    with pytest.raises(RuntimeError, match="transaction"):
        set_actor(user_id="GJTESTUSER01", role=Role.LICENSEE)


def test_middleware_tags_request_with_authenticated_user(app_db, rf, make_user):
    user = make_user(role=Role.LICENSEE)
    request = rf.get("/")
    request.user = user
    seen = {}

    def view(req):
        seen["actor"] = current_actor()
        return HttpResponse()

    DbContextMiddleware(view)(request)
    assert seen["actor"] == (user.user_id, "LICENSEE")


def test_middleware_sets_no_actor_for_anonymous_request(app_db, rf):
    request = rf.get("/")
    request.user = AnonymousUser()
    seen = {}

    def view(req):
        seen["actor"] = current_actor()
        return HttpResponse()

    DbContextMiddleware(view)(request)
    assert not any(seen["actor"])


def test_middleware_rolls_back_writes_on_server_error(app_db, rf, make_user):
    user = make_user()
    request = rf.get("/")
    request.user = user

    def failing_view(req):
        User.objects.filter(pk=user.pk).update(failed_login_count=3)
        return HttpResponse(status=500)

    DbContextMiddleware(failing_view)(request)
    user.refresh_from_db()
    assert user.failed_login_count == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --env-file .env.test pytest tests/test_db_context.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'core.db_context'`.

- [ ] **Step 3: Write the implementation**

`backend/core/db_context.py`:
```python
"""Tell Postgres who is acting, so row-level security policies can check it.

Values are transaction-local (set_config(..., true)): they disappear at commit or
rollback and can never leak into the next request on a reused connection.
"""

from django.db import connection

# Background jobs (e.g. audit verification). Never assigned to a user account.
SYSTEM_ROLE = "SYSTEM"


def set_actor(*, user_id: str, role: str) -> None:
    if not connection.in_atomic_block:
        raise RuntimeError("set_actor must be called inside transaction.atomic()")
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT set_config('app.user_id', %s, true), set_config('app.role', %s, true)",
            [str(user_id), str(role)],
        )


def current_actor() -> tuple[str | None, str | None]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT current_setting('app.user_id', true), current_setting('app.role', true)"
        )
        return cursor.fetchone()
```

`backend/core/middleware.py`:
```python
"""Run every request in a single transaction tagged with the acting user.

This replaces ATOMIC_REQUESTS so that the RLS context and the view's queries share
one transaction. Any 5xx response rolls back, so a crash never leaves half a change.
"""

from django.db import transaction

from core.db_context import set_actor


class DbContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        with transaction.atomic():
            user = getattr(request, "user", None)
            if user is not None and user.is_authenticated:
                set_actor(user_id=user.user_id, role=user.role)
            response = self.get_response(request)
            if response.status_code >= 500:
                transaction.set_rollback(True)
            return response
```

Modify `backend/config/settings.py`. Add `"core.middleware.DbContextMiddleware",` as the **last** entry of `MIDDLEWARE`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --env-file .env.test pytest -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
uv run ruff format . && uv run ruff check .
git add core/db_context.py core/middleware.py config/settings.py tests/test_db_context.py
git commit -m "feat: per-request transaction tagged with actor for row-level security"
```

---

### Task 7: Hash-chained, append-only audit log

**Files:**
- Create: `backend/audit/__init__.py`, `backend/audit/apps.py`, `backend/audit/hashing.py`, `backend/audit/models.py`, `backend/audit/service.py`, `backend/audit/verify.py`, `backend/audit/migrations/__init__.py`
- Create (generated): `backend/audit/migrations/0001_initial.py`
- Create: `backend/audit/migrations/0002_protect_and_rls.py`
- Create: `backend/audit/management/__init__.py`, `backend/audit/management/commands/__init__.py`, `backend/audit/management/commands/verify_audit_chain.py`
- Modify: `backend/config/settings.py` (`INSTALLED_APPS`), `backend/tests/conftest.py`
- Test: `backend/tests/test_audit_hashing.py`, `backend/tests/test_audit.py`

**Interfaces:**
- Consumes: `core.db_context.set_actor`, `SYSTEM_ROLE`; `identity.roles.Role`, `AUDIT_READERS`.
- Produces: `audit.service.record(*, action: str, actor: str = "", subject_type: str = "", subject_id: str = "", reason: str = "", payload: dict | None = None) -> str` (returns the new event's hash; payload values must be `str | int | bool | None`); `audit.verify.verify_chain() -> ChainReport` (`ok: bool`, `checked: int`, `first_bad_event_id: int | None`, `problem: str`); `audit.hashing.GENESIS_HASH`; management command `verify_audit_chain`; conftest fixture `audit_actions() -> list[str]`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_audit_hashing.py`:
```python
from datetime import UTC, datetime

from audit.hashing import GENESIS_HASH, compute_hash, event_fields


def sample_fields(**overrides):
    fields = dict(
        occurred_at=datetime(2026, 9, 26, 10, 0, 0, 123456, tzinfo=UTC),
        actor="GJTESTUSER01",
        action="test.action",
        subject_type="user",
        subject_id="GJTESTUSER02",
        reason="",
        payload={"b": 1, "a": "x"},
    )
    fields.update(overrides)
    return event_fields(**fields)


def test_hash_is_64_hex_chars_and_deterministic():
    first = compute_hash(GENESIS_HASH, sample_fields())
    assert first == compute_hash(GENESIS_HASH, sample_fields())
    assert len(first) == 64


def test_hash_ignores_payload_key_order():
    reordered = sample_fields(payload={"a": "x", "b": 1})
    assert compute_hash(GENESIS_HASH, reordered) == compute_hash(GENESIS_HASH, sample_fields())


def test_hash_changes_when_any_field_changes():
    base = compute_hash(GENESIS_HASH, sample_fields())
    assert compute_hash(GENESIS_HASH, sample_fields(reason="edited")) != base
    assert compute_hash("f" * 64, sample_fields()) != base
```

`backend/tests/test_audit.py`:
```python
import pytest
from django.core.management import CommandError, call_command
from django.db import DatabaseError, connection, transaction

from audit.hashing import GENESIS_HASH
from audit.models import AuditEvent
from audit.service import record
from audit.verify import verify_chain
from core.db_context import SYSTEM_ROLE, set_actor
from identity.roles import AUDIT_READERS, Role

pytestmark = pytest.mark.django_db


def verify_as_system():
    with transaction.atomic():
        set_actor(user_id="test", role=SYSTEM_ROLE)
        return verify_chain()


def events_as_system():
    with transaction.atomic():
        set_actor(user_id="test", role=SYSTEM_ROLE)
        return list(AuditEvent.objects.order_by("id"))


def tamper(sql):
    """Act as the schema owner with the trigger disabled, simulating a DB-level attacker."""
    with connection.cursor() as cursor:
        cursor.execute("ALTER TABLE audit_auditevent DISABLE TRIGGER audit_event_no_update_delete")
        cursor.execute(sql)
        cursor.execute("ALTER TABLE audit_auditevent ENABLE TRIGGER audit_event_no_update_delete")


def test_each_event_links_to_the_previous_one(app_db):
    record(action="test.first", actor="GJTESTUSER01")
    record(action="test.second")
    first, second = events_as_system()
    assert first.prev_hash == GENESIS_HASH
    assert second.prev_hash == first.hash


def test_verify_passes_on_untouched_chain(app_db):
    record(action="test.first")
    record(action="test.second", payload={"count": 2, "ok": True, "note": None})
    report = verify_as_system()
    assert report.ok
    assert report.checked == 2


def test_record_rejects_nested_payload(app_db):
    with pytest.raises(TypeError):
        record(action="test.bad", payload={"nested": {"a": 1}})


def test_app_role_cannot_update_events(app_db):
    record(action="test.event")
    with pytest.raises(DatabaseError, match="permission denied"):
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("UPDATE audit_auditevent SET action = 'forged'")


def test_app_role_cannot_delete_events(app_db):
    record(action="test.event")
    with pytest.raises(DatabaseError, match="permission denied"):
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("DELETE FROM audit_auditevent")


def test_trigger_blocks_changes_even_for_table_owner(db):
    record(action="test.event")
    with pytest.raises(DatabaseError, match="append-only"):
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("UPDATE audit_auditevent SET action = 'forged'")


def test_verify_detects_edited_event(db):
    record(action="test.first")
    record(action="test.second")
    tamper("UPDATE audit_auditevent SET reason = 'forged' WHERE action = 'test.first'")
    report = verify_as_system()
    assert not report.ok
    assert report.problem == "event contents do not match its hash"


def test_verify_detects_deleted_middle_event(db):
    for action in ("test.first", "test.second", "test.third"):
        record(action=action)
    tamper("DELETE FROM audit_auditevent WHERE action = 'test.second'")
    report = verify_as_system()
    assert not report.ok
    assert report.problem == "prev_hash does not match the previous event"


def test_verify_detects_deleted_last_event(db):
    record(action="test.first")
    record(action="test.second")
    tamper("DELETE FROM audit_auditevent WHERE action = 'test.second'")
    report = verify_as_system()
    assert not report.ok
    assert report.problem == "chain head does not match the last event"


@pytest.mark.parametrize("role", list(Role))
def test_only_audit_readers_can_read_events(app_db, role):
    record(action="test.event")
    with transaction.atomic():
        set_actor(user_id="GJTESTUSER01", role=role)
        visible = AuditEvent.objects.count()
    assert visible == (1 if role in AUDIT_READERS else 0)


def test_anonymous_context_cannot_read_events(app_db):
    record(action="test.event")
    assert AuditEvent.objects.count() == 0


def test_verify_command_reports_ok(app_db, capsys):
    record(action="test.event")
    call_command("verify_audit_chain")
    assert "Audit chain OK (1 events)" in capsys.readouterr().out


def test_verify_command_fails_loudly_on_tampering(db):
    record(action="test.event")
    tamper("UPDATE audit_auditevent SET actor = 'forged'")
    with pytest.raises(CommandError, match="BROKEN"):
        call_command("verify_audit_chain")
```

Append to `backend/tests/conftest.py` (put the imports at the top of the file):
```python
from django.db import transaction

from audit.models import AuditEvent
from core.db_context import SYSTEM_ROLE, set_actor


@pytest.fixture
def audit_actions():
    """Return a function listing audit actions recorded so far in this test."""

    def _read() -> list[str]:
        with transaction.atomic():
            set_actor(user_id="test", role=SYSTEM_ROLE)
            return list(AuditEvent.objects.order_by("id").values_list("action", flat=True))

    return _read
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --env-file .env.test pytest tests/test_audit_hashing.py tests/test_audit.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'audit'`.

- [ ] **Step 3: Write the pure hashing module**

`backend/audit/__init__.py`, `backend/audit/migrations/__init__.py`, `backend/audit/management/__init__.py`, `backend/audit/management/commands/__init__.py`: empty.

`backend/audit/apps.py`:
```python
from django.apps import AppConfig


class AuditConfig(AppConfig):
    name = "audit"
```

`backend/audit/hashing.py`:
```python
"""Pure functions defining the audit hash chain.

Each event's hash covers its own fields plus the previous event's hash, so changing,
removing or reordering any event breaks every hash after it.
"""

import hashlib
import json
from datetime import UTC, datetime

GENESIS_HASH = "0" * 64


def event_fields(
    *,
    occurred_at: datetime,
    actor: str,
    action: str,
    subject_type: str,
    subject_id: str,
    reason: str,
    payload: dict,
) -> dict:
    return {
        "occurred_at": occurred_at.astimezone(UTC).isoformat(timespec="microseconds"),
        "actor": actor,
        "action": action,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "reason": reason,
        "payload": payload,
    }


def compute_hash(prev_hash: str, fields: dict) -> str:
    canonical = json.dumps(
        {"prev_hash": prev_hash, **fields},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
```

Run: `uv run --env-file .env.test pytest tests/test_audit_hashing.py -v`
Expected: 3 passed.

- [ ] **Step 4: Write the models and generate the migration**

`backend/audit/models.py`:
```python
"""Storage for the audit trail. Rows are never updated or deleted (enforced in migration 0002)."""

from django.db import models


class AuditEvent(models.Model):
    occurred_at = models.DateTimeField()
    actor = models.CharField(max_length=64, blank=True)  # user_id, job name, or "" if anonymous
    action = models.CharField(max_length=64)  # e.g. "login.succeeded"
    subject_type = models.CharField(max_length=64, blank=True)
    subject_id = models.CharField(max_length=64, blank=True)
    reason = models.CharField(max_length=255, blank=True)  # why sensitive data was accessed
    payload = models.JSONField(default=dict)
    prev_hash = models.CharField(max_length=64)
    hash = models.CharField(max_length=64, unique=True)

    class Meta:
        db_table = "audit_auditevent"


class AuditChainHead(models.Model):
    """Single row holding the newest hash. Locking it makes appends happen one at a time."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    last_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "audit_auditchainhead"
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="audit_head_single_row")]
```

Add `"audit",` to `INSTALLED_APPS` in `backend/config/settings.py` (after `"core",`), then run:
```bash
uv run --env-file .env.test python manage.py makemigrations audit
```
Expected: creates `audit/migrations/0001_initial.py`.

- [ ] **Step 5: Write the protection migration**

`backend/audit/migrations/0002_protect_and_rls.py`:
```python
"""Make the audit trail append-only and readable only by oversight roles.

Three independent layers:
1. REVOKE: the app role has no UPDATE/DELETE/TRUNCATE privilege at all.
2. Trigger: even the table owner cannot update or delete without first disabling it.
3. RLS: only SOFTWARE_OWNER, HEAD_AUTHORITY and SYSTEM jobs can read events.
   Keep this role list in sync with identity.roles.AUDIT_READERS (a test enforces it).
"""

from django.db import migrations

FORWARD = """
CREATE FUNCTION audit_reject_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit events are append-only';
END $$;

CREATE TRIGGER audit_event_no_update_delete
    BEFORE UPDATE OR DELETE ON audit_auditevent
    FOR EACH ROW EXECUTE FUNCTION audit_reject_change();
CREATE TRIGGER audit_event_no_truncate
    BEFORE TRUNCATE ON audit_auditevent
    FOR EACH STATEMENT EXECUTE FUNCTION audit_reject_change();

REVOKE UPDATE, DELETE, TRUNCATE ON audit_auditevent FROM gj_app;
REVOKE DELETE, TRUNCATE ON audit_auditchainhead FROM gj_app;

ALTER TABLE audit_auditevent ENABLE ROW LEVEL SECURITY;
CREATE POLICY audit_insert ON audit_auditevent FOR INSERT TO gj_app WITH CHECK (true);
CREATE POLICY audit_read ON audit_auditevent FOR SELECT TO gj_app
    USING (current_setting('app.role', true) IN ('SOFTWARE_OWNER', 'HEAD_AUTHORITY', 'SYSTEM'));

INSERT INTO audit_auditchainhead (id, last_hash) VALUES (1, repeat('0', 64));
"""

BACKWARD = """
DELETE FROM audit_auditchainhead;
DROP POLICY audit_read ON audit_auditevent;
DROP POLICY audit_insert ON audit_auditevent;
ALTER TABLE audit_auditevent DISABLE ROW LEVEL SECURITY;
GRANT UPDATE, DELETE ON audit_auditevent TO gj_app;
GRANT DELETE ON audit_auditchainhead TO gj_app;
DROP TRIGGER audit_event_no_truncate ON audit_auditevent;
DROP TRIGGER audit_event_no_update_delete ON audit_auditevent;
DROP FUNCTION audit_reject_change();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0001_initial"),
        ("core", "0001_app_role_privileges"),
    ]
    operations = [migrations.RunSQL(sql=FORWARD, reverse_sql=BACKWARD)]
```

- [ ] **Step 6: Write the service, verifier and command**

`backend/audit/service.py`:
```python
"""Append events to the audit trail.

Uses a plain INSERT (no RETURNING) on purpose: RLS hides events from most roles, and
RETURNING would require read access. Callers get the new hash back instead.
"""

import json

from django.db import connection, transaction
from django.utils import timezone

from audit.hashing import compute_hash, event_fields
from audit.models import AuditChainHead

_ALLOWED_VALUE_TYPES = (str, int, bool, type(None))

_INSERT = """
INSERT INTO audit_auditevent
    (occurred_at, actor, action, subject_type, subject_id, reason, payload, prev_hash, hash)
VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
"""


def _check_payload(payload: dict) -> None:
    # Flat, simple values only: they survive the JSONB round trip unchanged,
    # so the hash can always be recomputed exactly.
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, _ALLOWED_VALUE_TYPES):
            raise TypeError(f"Audit payload field {key!r} must be str, int, bool or None")


def record(
    *,
    action: str,
    actor: str = "",
    subject_type: str = "",
    subject_id: str = "",
    reason: str = "",
    payload: dict | None = None,
) -> str:
    payload = payload or {}
    _check_payload(payload)
    with transaction.atomic():
        head = AuditChainHead.objects.select_for_update().get(pk=1)
        occurred_at = timezone.now()
        fields = event_fields(
            occurred_at=occurred_at,
            actor=actor,
            action=action,
            subject_type=subject_type,
            subject_id=subject_id,
            reason=reason,
            payload=payload,
        )
        new_hash = compute_hash(head.last_hash, fields)
        with connection.cursor() as cursor:
            cursor.execute(
                _INSERT,
                [occurred_at, actor, action, subject_type, subject_id, reason,
                 json.dumps(payload), head.last_hash, new_hash],
            )
        head.last_hash = new_hash
        head.save(update_fields=["last_hash"])
    return new_hash
```

`backend/audit/verify.py`:
```python
"""Recompute the whole audit hash chain and report the first break, if any.

Needs read access to all events, so call it as a SYSTEM actor (see the management command).
"""

from dataclasses import dataclass

from audit.hashing import GENESIS_HASH, compute_hash, event_fields
from audit.models import AuditChainHead, AuditEvent


@dataclass(frozen=True)
class ChainReport:
    ok: bool
    checked: int
    first_bad_event_id: int | None = None
    problem: str = ""


def verify_chain() -> ChainReport:
    expected_prev = GENESIS_HASH
    checked = 0
    for event in AuditEvent.objects.order_by("id").iterator(chunk_size=1000):
        if event.prev_hash != expected_prev:
            return ChainReport(False, checked, event.id, "prev_hash does not match the previous event")
        fields = event_fields(
            occurred_at=event.occurred_at,
            actor=event.actor,
            action=event.action,
            subject_type=event.subject_type,
            subject_id=event.subject_id,
            reason=event.reason,
            payload=event.payload,
        )
        if compute_hash(event.prev_hash, fields) != event.hash:
            return ChainReport(False, checked, event.id, "event contents do not match its hash")
        expected_prev = event.hash
        checked += 1
    if AuditChainHead.objects.get(pk=1).last_hash != expected_prev:
        return ChainReport(False, checked, None, "chain head does not match the last event")
    return ChainReport(True, checked)
```

`backend/audit/management/commands/verify_audit_chain.py`:
```python
"""Scheduled integrity check: exits non-zero if the audit trail was altered."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from audit.verify import verify_chain
from core.db_context import SYSTEM_ROLE, set_actor


class Command(BaseCommand):
    help = "Recompute the audit hash chain and fail loudly if anything was altered."

    def handle(self, *args, **options):
        with transaction.atomic():
            set_actor(user_id="verify_audit_chain", role=SYSTEM_ROLE)
            report = verify_chain()
        if not report.ok:
            raise CommandError(
                f"Audit chain BROKEN at event {report.first_bad_event_id}: {report.problem}"
            )
        self.stdout.write(f"Audit chain OK ({report.checked} events)")
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run --env-file .env.test pytest -v`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
uv run ruff format . && uv run ruff check .
git add audit/ config/settings.py tests/conftest.py tests/test_audit_hashing.py tests/test_audit.py
git commit -m "feat: hash-chained append-only audit log with RLS, trigger and verifier"
```

---

### Task 8: One-time passcodes (OTP)

**Files:**
- Create: `backend/identity/otp.py`, `backend/identity/otp_delivery.py`
- Modify: `backend/identity/models.py` (add `OtpPurpose`, `OtpChallenge`), `backend/config/settings.py`, `backend/.env.test`, `backend/tests/conftest.py`
- Create (generated): `backend/identity/migrations/0003_otpchallenge.py`
- Test: `backend/tests/test_otp.py`

**Interfaces:**
- Consumes: `identity.models.User.get_contact()`.
- Produces: `identity.models.OtpPurpose` (`LOGIN`; later phases add `ENROL`, `PASSWORD_RESET`, `DECISION`); `identity.models.OtpChallenge` (`public_id: UUID`, `user`, `purpose`, `code_hash`, `expires_at`, `attempts`, `closed_at`); `identity.otp.issue(user: User, purpose: str) -> OtpChallenge`; `identity.otp.verify(*, challenge_id: str, purpose: str, code: str) -> User | None`; constants `OTP_TTL`, `OTP_MAX_ATTEMPTS`; `identity.otp_delivery.OtpSender` protocol, `ConsoleOtpSender`, `OutboxOtpSender`, `get_sender()`; conftest fixture `otp_outbox -> list[tuple[contact, code]]`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_otp.py`:
```python
from datetime import timedelta

import pytest
from django.utils import timezone

from identity import otp
from identity.models import OtpChallenge, OtpPurpose

pytestmark = pytest.mark.django_db


def test_issue_sends_six_digit_code_to_registered_contact(app_db, make_user, otp_outbox):
    user = make_user(contact="+919811111111")
    otp.issue(user, OtpPurpose.LOGIN)
    contact, code = otp_outbox[-1]
    assert contact == "+919811111111"
    assert len(code) == 6 and code.isdigit()


def test_code_is_not_stored_in_plaintext(app_db, make_user, otp_outbox):
    challenge = otp.issue(make_user(), OtpPurpose.LOGIN)
    code = otp_outbox[-1][1]
    stored = OtpChallenge.objects.get(pk=challenge.pk).code_hash
    assert stored != code and len(stored) == 64


def test_correct_code_returns_user_once(app_db, make_user, otp_outbox):
    user = make_user()
    challenge = otp.issue(user, OtpPurpose.LOGIN)
    code = otp_outbox[-1][1]
    args = dict(challenge_id=str(challenge.public_id), purpose=OtpPurpose.LOGIN, code=code)
    assert otp.verify(**args) == user
    assert otp.verify(**args) is None  # single use


def test_wrong_code_is_rejected_and_counted(app_db, make_user, otp_outbox):
    challenge = otp.issue(make_user(), OtpPurpose.LOGIN)
    code = otp_outbox[-1][1]
    wrong = "000000" if code != "000000" else "111111"
    assert otp.verify(challenge_id=str(challenge.public_id), purpose=OtpPurpose.LOGIN, code=wrong) is None
    challenge.refresh_from_db()
    assert challenge.attempts == 1


def test_challenge_closes_after_max_attempts(app_db, make_user, otp_outbox):
    challenge = otp.issue(make_user(), OtpPurpose.LOGIN)
    code = otp_outbox[-1][1]
    wrong = "000000" if code != "000000" else "111111"
    challenge_id = str(challenge.public_id)
    for _ in range(otp.OTP_MAX_ATTEMPTS):
        otp.verify(challenge_id=challenge_id, purpose=OtpPurpose.LOGIN, code=wrong)
    assert otp.verify(challenge_id=challenge_id, purpose=OtpPurpose.LOGIN, code=code) is None


def test_expired_code_is_rejected(app_db, make_user, otp_outbox):
    challenge = otp.issue(make_user(), OtpPurpose.LOGIN)
    code = otp_outbox[-1][1]
    OtpChallenge.objects.filter(pk=challenge.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    assert otp.verify(challenge_id=str(challenge.public_id), purpose=OtpPurpose.LOGIN, code=code) is None


def test_new_challenge_supersedes_the_old_one(app_db, make_user, otp_outbox):
    user = make_user()
    first = otp.issue(user, OtpPurpose.LOGIN)
    first_code = otp_outbox[-1][1]
    otp.issue(user, OtpPurpose.LOGIN)
    assert otp.verify(challenge_id=str(first.public_id), purpose=OtpPurpose.LOGIN, code=first_code) is None


def test_inactive_user_cannot_complete_otp(app_db, make_user, otp_outbox):
    user = make_user()
    challenge = otp.issue(user, OtpPurpose.LOGIN)
    code = otp_outbox[-1][1]
    user.is_active = False
    user.save(update_fields=["is_active"])
    assert otp.verify(challenge_id=str(challenge.public_id), purpose=OtpPurpose.LOGIN, code=code) is None


def test_malformed_challenge_id_is_rejected(app_db):
    assert otp.verify(challenge_id="not-a-uuid", purpose=OtpPurpose.LOGIN, code="123456") is None
```

Append to `backend/tests/conftest.py` (import at the top):
```python
from identity.otp_delivery import OutboxOtpSender


@pytest.fixture
def otp_outbox():
    OutboxOtpSender.outbox.clear()
    yield OutboxOtpSender.outbox
    OutboxOtpSender.outbox.clear()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --env-file .env.test pytest tests/test_otp.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'identity.otp_delivery'`.

- [ ] **Step 3: Write the delivery interface**

Append to `backend/.env.test`:
```
OTP_HMAC_KEY=test-only-otp-hmac-key
OTP_SENDER=identity.otp_delivery.OutboxOtpSender
```

Append to `backend/config/settings.py`:
```python
# --- One-time passcodes ----------------------------------------------------------
OTP_HMAC_KEY = env.required("OTP_HMAC_KEY")
# Production sender (India-resident SMS/email provider) is chosen in Phase 2.
OTP_SENDER = env.required("OTP_SENDER")
```

`backend/identity/otp_delivery.py`:
```python
"""How one-time codes reach the user. The production provider is plugged in via settings.

Codes are only ever sent to the contact stored on the account, never to an address
supplied in the request.
"""

from typing import ClassVar, Protocol

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string


class OtpSender(Protocol):
    def send(self, contact: str, code: str) -> None: ...


class ConsoleOtpSender:
    """Development only: prints the code. Refuses to run when DEBUG is off."""

    def send(self, contact: str, code: str) -> None:
        if not settings.DEBUG:
            raise ImproperlyConfigured("ConsoleOtpSender must not be used outside development")
        print(f"[DEV OTP] code {code} for contact ending {contact[-4:]}")


class OutboxOtpSender:
    """Tests only: keeps sent codes in memory so tests can read them."""

    outbox: ClassVar[list[tuple[str, str]]] = []

    def send(self, contact: str, code: str) -> None:
        self.outbox.append((contact, code))


def get_sender() -> OtpSender:
    return import_string(settings.OTP_SENDER)()
```

- [ ] **Step 4: Write the model and generate the migration**

Append to `backend/identity/models.py` (add `import uuid` at the top):
```python
class OtpPurpose(models.TextChoices):
    LOGIN = "LOGIN", "Login second factor"


class OtpChallenge(models.Model):
    """One issued code. Closed when verified, superseded, expired-and-tried, or out of attempts."""

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="otp_challenges")
    purpose = models.CharField(max_length=16, choices=OtpPurpose.choices)
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    closed_at = models.DateTimeField(null=True, blank=True)
```

Run:
```bash
uv run --env-file .env.test python manage.py makemigrations identity --name otpchallenge
```
Expected: creates `identity/migrations/0003_otpchallenge.py`.

- [ ] **Step 5: Write the OTP service**

`backend/identity/otp.py`:
```python
"""Issue and check one-time passcodes.

Codes are stored only as an HMAC keyed with a server secret, so a database leak does not
reveal them (a plain hash of a 6-digit code could be brute-forced instantly).
The caller must be inside a transaction (the request middleware guarantees this).
"""

import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from identity.models import OtpChallenge, User
from identity.otp_delivery import get_sender

OTP_LENGTH = 6
OTP_TTL = timedelta(minutes=5)
OTP_MAX_ATTEMPTS = 5


def _hash_code(challenge: OtpChallenge, code: str) -> str:
    message = f"{challenge.public_id}:{code}".encode()
    return hmac.new(settings.OTP_HMAC_KEY.encode(), message, hashlib.sha256).hexdigest()


def issue(user: User, purpose: str) -> OtpChallenge:
    now = timezone.now()
    OtpChallenge.objects.filter(user=user, purpose=purpose, closed_at__isnull=True).update(
        closed_at=now
    )
    code = f"{secrets.randbelow(10**OTP_LENGTH):0{OTP_LENGTH}d}"
    challenge = OtpChallenge(user=user, purpose=purpose, expires_at=now + OTP_TTL)
    challenge.code_hash = _hash_code(challenge, code)
    challenge.save()
    get_sender().send(user.get_contact(), code)
    return challenge


def verify(*, challenge_id: str, purpose: str, code: str) -> User | None:
    try:
        challenge = (
            OtpChallenge.objects.select_for_update()
            .select_related("user")
            .get(public_id=challenge_id, purpose=purpose, closed_at__isnull=True)
        )
    except (OtpChallenge.DoesNotExist, ValidationError):
        return None

    now = timezone.now()
    challenge.attempts += 1
    matches = hmac.compare_digest(challenge.code_hash, _hash_code(challenge, code))
    success = matches and now < challenge.expires_at and challenge.user.is_active
    if success or now >= challenge.expires_at or challenge.attempts >= OTP_MAX_ATTEMPTS:
        challenge.closed_at = now
    challenge.save(update_fields=["attempts", "closed_at"])
    return challenge.user if success else None
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run --env-file .env.test pytest -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
uv run ruff format . && uv run ruff check .
git add identity/ config/settings.py .env.test tests/conftest.py tests/test_otp.py
git commit -m "feat: HMAC-stored one-time passcodes with expiry, attempt limit and pluggable delivery"
```

---

### Task 9: Password + OTP login API with lockout, rate limits and role checks

**Files:**
- Create: `backend/identity/login.py`, `backend/identity/permissions.py`, `backend/identity/serializers.py`, `backend/identity/views.py`, `backend/identity/urls.py`
- Modify: `backend/config/settings.py`, `backend/config/urls.py`
- Test: `backend/tests/test_login_api.py`, `backend/tests/test_permissions.py`

**Interfaces:**
- Consumes: `identity.otp.issue/verify`, `OtpPurpose.LOGIN`, `audit.service.record`, `core.db_context.set_actor`, `identity.roles.Role`.
- Produces: `identity.login.start_login(user_id: str, password: str) -> OtpChallenge | None`; `LOCKOUT_THRESHOLD = 5`; `LOCKOUT_DURATION = timedelta(minutes=15)`; `identity.permissions.role_required(*roles) -> type[BasePermission]`; HTTP API:
  - `GET  /api/auth/csrf` → 204, sets the CSRF cookie
  - `POST /api/auth/login` `{user_id, password}` → 200 `{challenge_id}` | 401 `{"detail": "Invalid credentials"}` | 429
  - `POST /api/auth/login/verify` `{challenge_id, code}` → 200 `{user_id, role}` + session cookie | 401 | 429
  - `POST /api/auth/logout` → 204
  - `GET  /api/auth/me` → 200 `{user_id, role}` | 403
  - Audit actions: `login.failed`, `login.locked`, `login.blocked_locked`, `login.otp_failed`, `login.succeeded`, `logout`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_login_api.py`:
```python
import pytest

from identity.roles import Role
from tests.conftest import TEST_PASSWORD

pytestmark = pytest.mark.django_db


def start(client, user_id, password=TEST_PASSWORD):
    return client.post(
        "/api/auth/login", {"user_id": user_id, "password": password}, content_type="application/json"
    )


def verify(client, challenge_id, code):
    return client.post(
        "/api/auth/login/verify",
        {"challenge_id": challenge_id, "code": code},
        content_type="application/json",
    )


def login(client, user, otp_outbox):
    challenge_id = start(client, user.user_id).json()["challenge_id"]
    return verify(client, challenge_id, otp_outbox[-1][1])


def test_full_login_requires_password_and_otp(app_db, client, make_user, otp_outbox):
    user = make_user(role=Role.LICENSEE)
    first = start(client, user.user_id)
    assert first.status_code == 200
    assert client.get("/api/auth/me").status_code == 403  # password alone is not a login

    second = verify(client, first.json()["challenge_id"], otp_outbox[-1][1])
    assert second.status_code == 200
    assert client.get("/api/auth/me").json() == {"user_id": user.user_id, "role": "LICENSEE"}


def test_user_id_is_case_insensitive(app_db, client, make_user, otp_outbox):
    user = make_user()
    assert start(client, user.user_id.lower()).status_code == 200


def test_wrong_password_and_unknown_user_look_identical(app_db, client, make_user, otp_outbox):
    user = make_user()
    wrong_password = start(client, user.user_id, "wrong-password-123")
    unknown_user = start(client, "GJNOSUCHUSER")
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json() == {"detail": "Invalid credentials"}
    assert otp_outbox == []


def test_wrong_otp_is_rejected(app_db, client, make_user, otp_outbox):
    user = make_user()
    challenge_id = start(client, user.user_id).json()["challenge_id"]
    code = otp_outbox[-1][1]
    wrong = "000000" if code != "000000" else "111111"
    assert verify(client, challenge_id, wrong).status_code == 401
    assert client.get("/api/auth/me").status_code == 403


def test_account_locks_after_repeated_failures(app_db, client, make_user, otp_outbox):
    user = make_user()
    for _ in range(5):
        start(client, user.user_id, "wrong-password-123")
    assert start(client, user.user_id).status_code == 401  # even the right password
    user.refresh_from_db()
    assert user.locked_until is not None


def test_login_is_rate_limited(app_db, client):
    statuses = [start(client, "GJNOSUCHUSER").status_code for _ in range(11)]
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429


def test_session_cookie_is_hardened(app_db, client, make_user, otp_outbox):
    response = login(client, make_user(), otp_outbox)
    cookie = response.cookies["sessionid"]
    assert cookie["httponly"] is True
    assert cookie["secure"] is True
    assert cookie["samesite"] == "Strict"


def test_logout_ends_session(app_db, client, make_user, otp_outbox):
    login(client, make_user(), otp_outbox)
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 403


def test_login_events_are_audited(app_db, client, make_user, otp_outbox, audit_actions):
    user = make_user()
    start(client, user.user_id, "wrong-password-123")
    login(client, user, otp_outbox)
    client.post("/api/auth/logout")
    assert audit_actions() == ["login.failed", "login.succeeded", "logout"]


def test_csrf_endpoint_sets_cookie(app_db, client):
    response = client.get("/api/auth/csrf")
    assert response.status_code == 204
    assert "csrftoken" in response.cookies
```

`backend/tests/test_permissions.py`:
```python
import pytest
from django.contrib.auth.models import AnonymousUser
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from identity.permissions import role_required
from identity.roles import Role

pytestmark = pytest.mark.django_db


def probe_view(*roles):
    class Probe(APIView):
        permission_classes = [role_required(*roles)]

        def get(self, request):
            return Response({"ok": True})

    return Probe.as_view()


def call(view, user):
    request = APIRequestFactory().get("/")
    force_authenticate(request, user=user)
    return view(request)


def test_listed_role_is_allowed(app_db, make_user):
    view = probe_view(Role.HEAD_AUTHORITY)
    assert call(view, make_user(role=Role.HEAD_AUTHORITY)).status_code == 200


@pytest.mark.parametrize("role", [r for r in Role if r != Role.HEAD_AUTHORITY])
def test_every_other_role_is_refused(app_db, make_user, role):
    view = probe_view(Role.HEAD_AUTHORITY)
    assert call(view, make_user(role=role)).status_code == 403


def test_anonymous_is_refused(app_db):
    view = probe_view(Role.HEAD_AUTHORITY)
    assert call(view, AnonymousUser()).status_code == 403


def test_deactivated_user_is_refused(app_db, make_user):
    user = make_user(role=Role.HEAD_AUTHORITY)
    user.is_active = False
    assert call(probe_view(Role.HEAD_AUTHORITY), user).status_code == 403
```

Create an empty `backend/tests/__init__.py` so tests can import `TEST_PASSWORD` from `tests.conftest`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --env-file .env.test pytest tests/test_login_api.py tests/test_permissions.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'rest_framework'...` or 404s for `/api/auth/*`.

- [ ] **Step 3: Update settings**

In `backend/config/settings.py`, replace `INSTALLED_APPS` and `MIDDLEWARE`:
```python
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "rest_framework",
    "core",
    "audit",
    "identity",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.DbContextMiddleware",
]
```

Append:
```python
# --- Sessions: server-side, short-lived, never readable by JavaScript --------------
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 15 * 60  # 15 minutes of inactivity
SESSION_SAVE_EVERY_REQUEST = True  # each request extends the idle timeout
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SAMESITE = "Strict"

# Shared across app servers so rate limits hold behind a load balancer.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "gj_cache",
    }
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_THROTTLE_RATES": {"login": "10/min", "otp": "10/min"},
}
```

- [ ] **Step 4: Write the login service and permission**

`backend/identity/login.py`:
```python
"""First login step: check the password, enforce lockout, then send an OTP.

Every outcome looks the same to the caller except success, so the API cannot be used
to discover which user IDs exist.
"""

from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.utils import timezone

from audit.service import record
from identity import otp
from identity.models import OtpChallenge, OtpPurpose, User

LOCKOUT_THRESHOLD = 5
LOCKOUT_DURATION = timedelta(minutes=15)


def start_login(user_id: str, password: str) -> OtpChallenge | None:
    user = User.objects.select_for_update().filter(user_id=user_id.strip().upper()).first()
    if user is None:
        make_password(password)  # spend the same time as a real check
        record(action="login.failed", reason="unknown user id", payload={"attempted": user_id[:32]})
        return None

    now = timezone.now()
    if user.locked_until and user.locked_until > now:
        record(action="login.blocked_locked", subject_type="user", subject_id=user.user_id)
        return None

    if not user.is_active or not user.check_password(password):
        _register_failure(user, now)
        return None

    user.failed_login_count = 0
    user.save(update_fields=["failed_login_count"])
    return otp.issue(user, OtpPurpose.LOGIN)


def _register_failure(user: User, now) -> None:
    user.failed_login_count += 1
    if user.failed_login_count >= LOCKOUT_THRESHOLD:
        user.failed_login_count = 0
        user.locked_until = now + LOCKOUT_DURATION
        record(action="login.locked", subject_type="user", subject_id=user.user_id)
    user.save(update_fields=["failed_login_count", "locked_until"])
    record(action="login.failed", subject_type="user", subject_id=user.user_id)
```


`backend/identity/permissions.py`:
```python
"""Role checks for API views. Usage: permission_classes = [role_required(Role.LICENSEE)]."""

from rest_framework.permissions import BasePermission


def role_required(*roles: str) -> type[BasePermission]:
    class HasRole(BasePermission):
        def has_permission(self, request, view) -> bool:
            user = request.user
            return bool(user and user.is_authenticated and user.has_role(*roles))

    HasRole.__name__ = f"HasRole({', '.join(roles)})"
    return HasRole
```

- [ ] **Step 5: Write serializers, views and URLs**

`backend/identity/serializers.py`:
```python
"""Input validation for the login endpoints. Strict formats reject junk early."""

from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    user_id = serializers.CharField(max_length=12)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


class OtpVerifySerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    code = serializers.RegexField(r"^\d{6}$")
```

`backend/identity/views.py`:
```python
"""HTTP endpoints for login and logout. Thin: validate, call a service, respond."""

from django.contrib.auth import login, logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from audit.service import record
from core.db_context import set_actor
from identity import otp
from identity.login import start_login
from identity.models import OtpPurpose
from identity.serializers import LoginSerializer, OtpVerifySerializer


def _invalid() -> Response:
    return Response({"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_protect, name="dispatch")
class LoginStartView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        data = LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        challenge = start_login(data.validated_data["user_id"], data.validated_data["password"])
        if challenge is None:
            return _invalid()
        return Response({"challenge_id": str(challenge.public_id)})


@method_decorator(csrf_protect, name="dispatch")
class LoginVerifyView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request):
        data = OtpVerifySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = otp.verify(
            challenge_id=str(data.validated_data["challenge_id"]),
            purpose=OtpPurpose.LOGIN,
            code=data.validated_data["code"],
        )
        if user is None:
            record(action="login.otp_failed")
            return _invalid()
        login(request, user)  # also rotates the session key (prevents session fixation)
        set_actor(user_id=user.user_id, role=user.role)
        record(action="login.succeeded", actor=user.user_id)
        return Response({"user_id": user.user_id, "role": user.role})


class LogoutView(APIView):
    def post(self, request):
        record(action="logout", actor=request.user.user_id)
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    def get(self, request):
        return Response({"user_id": request.user.user_id, "role": request.user.role})
```
`backend/identity/urls.py`:
```python
from django.urls import path

from identity import views

urlpatterns = [
    path("csrf", views.CsrfView.as_view()),
    path("login", views.LoginStartView.as_view()),
    path("login/verify", views.LoginVerifyView.as_view()),
    path("logout", views.LogoutView.as_view()),
    path("me", views.MeView.as_view()),
]
```

`backend/config/urls.py`:
```python
from django.urls import include, path

from core.views import health

urlpatterns = [
    path("api/health", health),
    path("api/auth/", include("identity.urls")),
]
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run --env-file .env.test pytest -v`
Expected: all pass. The test database's cache table is created automatically by Django's test runner.

- [ ] **Step 7: Commit**

```bash
uv run ruff format . && uv run ruff check .
git add identity/ config/ tests/
git commit -m "feat: password+OTP login with lockout, rate limits, hardened sessions and role checks"
```

---

### Task 10: Bootstrap Software Owner, developer runbook, Phase 1 acceptance

**Files:**
- Create: `backend/identity/management/__init__.py`, `backend/identity/management/commands/__init__.py`, `backend/identity/management/commands/create_software_owner.py`
- Create: `backend/.env.example`
- Modify: `README.md`
- Test: `backend/tests/test_create_software_owner.py`

**Interfaces:**
- Consumes: `User.objects.create_user`, `Role.SOFTWARE_OWNER`, `audit.service.record`.
- Produces: management command `create_software_owner` (interactive, run once by the deployer); audit action `account.bootstrap_owner_created`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_create_software_owner.py`:
```python
import pytest
from django.core.management import CommandError, call_command

from identity.models import User
from identity.roles import Role

pytestmark = pytest.mark.django_db

COMMAND_MODULE = "identity.management.commands.create_software_owner"


@pytest.fixture
def answers(monkeypatch):
    def _set(contact="+919822222222", password="a-strong-owner-pass-42", repeat=None):
        monkeypatch.setattr("builtins.input", lambda prompt: contact)
        replies = iter([password, repeat if repeat is not None else password])
        monkeypatch.setattr(f"{COMMAND_MODULE}.getpass.getpass", lambda prompt: next(replies))

    return _set


def test_creates_first_owner_and_audits_it(app_db, answers, capsys, audit_actions):
    answers()
    call_command("create_software_owner")
    owner = User.objects.get(role=Role.SOFTWARE_OWNER)
    assert owner.get_contact() == "+919822222222"
    assert owner.user_id in capsys.readouterr().out
    assert audit_actions() == ["account.bootstrap_owner_created"]


def test_refuses_when_an_owner_already_exists(app_db, answers, make_user):
    make_user(role=Role.SOFTWARE_OWNER)
    answers()
    with pytest.raises(CommandError, match="already exists"):
        call_command("create_software_owner")


def test_rejects_weak_password(app_db, answers):
    answers(password="short", repeat="short")
    with pytest.raises(CommandError):
        call_command("create_software_owner")
    assert not User.objects.exists()


def test_rejects_mismatched_passwords(app_db, answers):
    answers(repeat="something-else-entirely-9")
    with pytest.raises(CommandError, match="do not match"):
        call_command("create_software_owner")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --env-file .env.test pytest tests/test_create_software_owner.py -v`
Expected: FAIL, `CommandError: Unknown command: 'create_software_owner'`.

- [ ] **Step 3: Write the command**

`backend/identity/management/__init__.py`, `backend/identity/management/commands/__init__.py`: empty.

`backend/identity/management/commands/create_software_owner.py`:
```python
"""Create the very first Software Owner account.

Run once, on the server, by the deployer. Every later account is created through the
application's own audited provisioning flows (Phase 2 and Phase 4).
"""

import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from audit.service import record
from identity.models import User
from identity.roles import Role


class Command(BaseCommand):
    help = "Create the first Software Owner account (refuses if one already exists)."

    def handle(self, *args, **options):
        if User.objects.filter(role=Role.SOFTWARE_OWNER).exists():
            raise CommandError("A Software Owner already exists; use in-app provisioning instead.")
        contact = input("Registered OTP contact (phone or email): ").strip()
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Repeat password: "):
            raise CommandError("Passwords do not match")
        try:
            validate_password(password)
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc

        with transaction.atomic():
            user = User.objects.create_user(
                role=Role.SOFTWARE_OWNER, password=password, contact=contact
            )
            record(
                action="account.bootstrap_owner_created",
                actor="create_software_owner",
                subject_type="user",
                subject_id=user.user_id,
            )
        self.stdout.write(f"Created Software Owner with user ID {user.user_id}")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --env-file .env.test pytest -v`
Expected: all pass.

- [ ] **Step 5: Write the developer runbook**

`backend/.env.example`:
```
# Local development settings. Copy to backend/.env (gitignored). Production values come from the vault.
# Generate secrets with:
#   DJANGO_SECRET_KEY, BLIND_INDEX_KEY, OTP_HMAC_KEY: python3 -c "import secrets; print(secrets.token_urlsafe(64))"
#   FIELD_ENCRYPTION_KEY: uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
DJANGO_SECRET_KEY=replace-me
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_SSL_REDIRECT=0
DB_NAME=gjrp
# The running app always connects as gj_app. Migrations override this with gj_owner (see README).
DB_USER=gj_app
DB_PASSWORD=replace-with-GJ_APP_PASSWORD-from-root-env
DB_HOST=localhost
DB_PORT=5432
DB_SSLMODE=disable
FIELD_ENCRYPTION_KEY=replace-me
BLIND_INDEX_KEY=replace-me
OTP_HMAC_KEY=replace-me
OTP_SENDER=identity.otp_delivery.ConsoleOtpSender
```

Replace `README.md` with:
````markdown
# gjrestrictedproduct

Authorisation and audit platform for seller-initiated transactions of restricted items
in Gujarat. See `highlevel_plan.md` (design) and `docs/superpowers/plans/` (roadmap and plans).

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
````


- [ ] **Step 6: Phase 1 acceptance run**

Run (from `backend/`):
```bash
uv run ruff format --check . && uv run ruff check .
uv run --env-file .env.test python manage.py makemigrations --check --dry-run
uv run --env-file .env.test pytest -v
```
Expected: no lint issues, `No changes detected`, all tests pass.

Then follow the "Running the backend locally" steps and check by hand:
1. `curl -s localhost:8000/api/health` returns `{"status": "ok"}`.
2. Log in with the bootstrap owner: `GET /api/auth/csrf`, then `POST /api/auth/login`. The OTP is printed in the runserver console. Then `POST /api/auth/login/verify` and `GET /api/auth/me`.
3. `uv run python manage.py verify_audit_chain` (in the same shell) prints `Audit chain OK (...)`.

Run the `security-review` skill on the branch and fix any findings before opening the PR.

- [ ] **Step 7: Commit**

```bash
uv run ruff format . && uv run ruff check .
cd .. && git add README.md backend/
git commit -m "feat: bootstrap Software Owner command and developer runbook"
```

---

## Spec coverage (Phase 1)

| Spec item (Phase 1 / cross-cutting) | Task |
|---|---|
| Repo scaffold | 1 |
| CI | 2 |
| Postgres schema baseline, least privilege | 3, 5 |
| Identity + MFA (password + OTP), lockout, rate limiting, short sessions | 5, 8, 9 |
| Role model | 5, 9 |
| Audit log with hash chain, append-only, verification job | 7 |
| RLS baseline (context plumbing + first policy) | 6, 7 |
| Field-level encryption for identifiers | 4, 5 |
| Rule 2: never edit or delete records | 5 (users), 7 (audit) |
| Rule 4: access to sensitive data is logged | 7 (`record(..., reason=...)`); used from Phase 2 |
| Secrets not in code | 1, 4, 8 (env-only), 10 (`.env.example`) |
