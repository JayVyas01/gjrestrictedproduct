# Code Map

**What this is:** the one place that says which code is responsible for what, which user roles it serves, and which tests prove it. Use it to review, debug or change the system.

**Keep it current:** every pull request that adds, removes or changes code or tests updates this file in the same pull request. A reviewer should reject a code PR that leaves this map stale.

**Last updated:** 2026-09-29, Phase 1 Foundation (100 tests).

---

## 1. User roles and where their rules live

| Role | What they can do today | Where it is enforced | Proving tests |
|---|---|---|---|
| **Licensee** (buyer and seller combined; what they may do comes from their licences) | Log in with password and a one-time code. Licences and transactions arrive in Demo D1 and D2. | `identity/roles.py` (`Role.LICENSEE`), `identity/login.py`, `identity/views.py` | `test_login_api.py`, `test_users.py::test_has_role` |
| **Authorised Personnel** | Log in. Position-based approvals arrive in D1 and D2. | `identity/roles.py` (`Role.PERSONNEL`) | `test_permissions.py` |
| **Licensing Authority** | Log in. Recording licences arrives in D1. | `identity/roles.py` (`Role.LICENSING_AUTHORITY`) | `test_permissions.py` |
| **Software Owner** | Log in; read the whole audit log; create or reset personnel accounts (the API comes in Phase 4) | `identity/roles.py` (`AUDIT_READERS`, `PERSONNEL_PROVISIONERS`); `audit/migrations/0002_protect_and_rls.py` (read policy); `create_software_owner` command (first account only) | `test_audit.py::test_only_audit_readers_can_read_events`, `test_create_software_owner.py` |
| **Head Authority** | Log in; read the whole audit log (oversight); create or reset personnel accounts (Phase 4) | Same as Software Owner | `test_audit.py::test_only_audit_readers_can_read_events` |
| **SYSTEM** (background jobs, never a person) | Read the audit log to verify the chain | `core/db_context.py` (`SYSTEM_ROLE`), `verify_audit_chain` command | `test_audit.py::test_verify_command_*` |
| **Anonymous** (not logged in) | Only the health check, the CSRF cookie and the two login steps | `settings.REST_FRAMEWORK` (deny by default), `AllowAny` on those views only | `test_login_api.py`, `test_permissions.py::test_anonymous_is_refused`, `test_audit.py::test_anonymous_context_cannot_read_events` |

To restrict a new API endpoint to certain roles, use `permission_classes = [role_required(Role.X, ...)]` from `identity/permissions.py`.

---

## 2. Code responsibility map

Paths are relative to `backend/`.

### config: settings and startup

| File | Responsible for | Key names | Tests |
|---|---|---|---|
| `config/env.py` | Reading environment variables; stops at startup if a required one is missing | `required`, `optional`, `flag`, `listed`, `MissingSetting` | `test_env.py` |
| `config/settings.py` | All settings: database, security headers, sessions (15-minute idle timeout), rate limits (`login`, `otp` 10/min, `NUM_PROXIES: 0`), encryption keys, OTP sender, exception handler | `REST_FRAMEWORK`, `CACHES`, `MIDDLEWARE` | Covered indirectly by all API tests; `check --deploy` in CI |
| `config/urls.py` | URL routing: `/api/health`, `/api/auth/*` | — | `test_health.py`, `test_login_api.py` |
| `.env.test` | Test-only settings (never real secrets) | — | — |

### core: shared building blocks

| File | Responsible for | Key names | Tests |
|---|---|---|---|
| `core/views.py` | Health check; also confirms the database is reachable | `health` | `test_health.py` |
| `core/crypto.py` | Encrypting sensitive fields; one-way lookup keys (blind indexes) for exact-match lookup only | `encrypt`, `decrypt`, `blind_index(context, value)`, `DecryptionError` | `test_crypto.py` |
| `core/db_context.py` | Telling Postgres who is acting, so row-level security can check it; the setting lasts only for the current transaction | `set_actor`, `current_actor`, `SYSTEM_ROLE` | `test_db_context.py` |
| `core/middleware.py` | One database transaction per request, tagged with the user; a 5xx response rolls back | `DbContextMiddleware` | `test_db_context.py` |
| `core/exceptions.py` | A raised API error undoes the request's writes (**raise to roll back, return to commit**) | `rollback_on_exception` | `test_rollback_on_exception.py` |
| `core/migrations/0001_app_role_privileges.py` | The app role `gj_app` gets data access only: no schema changes, no ownership | — | `test_db_privileges.py` |

### identity: accounts, roles, one-time codes, login

| File | Responsible for | Key names | Tests |
|---|---|---|---|
| `identity/roles.py` | The six fixed roles and role groups | `Role`, `AUDIT_READERS`, `PERSONNEL_PROVISIONERS` | `test_users.py`, `test_permissions.py`, `test_audit.py` |
| `identity/models.py` | User accounts (system-generated ID, Argon2 password, encrypted contact, lockout fields) and one-time-code records (at most one open code per user and purpose) | `User`, `UserManager.create_user`, `generate_user_id`, `OtpChallenge`, `OtpPurpose` | `test_users.py`, `test_otp.py` |
| `identity/migrations/0002_protect_users.py` | Accounts can't be deleted, only deactivated | — | `test_users.py::test_app_role_cannot_delete_users` |
| `identity/otp.py` | Issuing and checking 6-digit codes: stored as HMAC, 5-minute expiry, 5 attempts, single use, a new code cancels the old one, issuing locks the user row | `issue`, `verify`, `OTP_TTL`, `OTP_MAX_ATTEMPTS` | `test_otp.py` |
| `identity/otp_delivery.py` | How codes are sent: console in development (refuses unless DEBUG), in-memory outbox in tests, real provider later | `get_sender`, `ConsoleOtpSender`, `OutboxOtpSender` | `test_otp.py` |
| `identity/login.py` | Login step 1: password check on every path (timing is the same whether or not the account exists), lockout after 5 wrong passwords or 5 code requests in 15 minutes, locking cancels open codes | `start_login`, `LOCKOUT_THRESHOLD`, `LOCKOUT_DURATION` | `test_login_api.py` |
| `identity/serializers.py` | Validating login input | `LoginSerializer`, `OtpVerifySerializer` | `test_login_api.py` |
| `identity/views.py`, `identity/urls.py` | Login API: csrf, login, login/verify, logout, me | `CsrfView`, `LoginStartView`, `LoginVerifyView`, `LogoutView`, `MeView` | `test_login_api.py` |
| `identity/permissions.py` | Restricting an endpoint to certain roles | `role_required` | `test_permissions.py` |
| `identity/management/commands/create_software_owner.py` | Creating the very first Software Owner (run once, interactive) | — | `test_create_software_owner.py` |

### audit: tamper-evident audit log

| File | Responsible for | Key names | Tests |
|---|---|---|---|
| `audit/hashing.py` | Hash-chain maths: each entry's hash covers the previous one | `compute_hash`, `event_fields`, `GENESIS_HASH` | `test_audit_hashing.py` |
| `audit/models.py` | The audit entry table, plus a single row holding the latest hash | `AuditEvent`, `AuditChainHead` | `test_audit.py` |
| `audit/service.py` | Writing an entry. Rules: call it **last** in a request; payloads hold **IDs and lookup keys only, never personal data** | `record` | `test_audit.py` |
| `audit/verify.py` | Recomputing the chain and reporting the first broken entry | `verify_chain`, `ChainReport` | `test_audit.py` |
| `audit/migrations/0002_protect_and_rls.py` | Append-only (REVOKE plus a trigger), readable only by Software Owner, Head Authority and SYSTEM | — | `test_audit.py` |
| `audit/management/commands/verify_audit_chain.py` | Scheduled integrity check; exits with an error if the log was altered | — | `test_audit.py::test_verify_command_*` |

### Repository, CI and local setup

| File | Responsible for | Check name |
|---|---|---|
| `.github/workflows/ci.yml` | Lint, format, migrations check, tests, dependency vulnerability audit, production settings check | `backend` |
| `.github/workflows/branch-policy.yml` | Pull requests into `main` must come from `dev` | `source-branch` |
| `.github/workflows/codeql.yml` | Security scanning of Python and GitHub Actions | `analyze (python)`, `analyze (actions)` |
| `.github/dependabot.yml` | Weekly dependency and action updates | — |
| GitHub ruleset "Protect dev and main" | Pull request required, the checks above must pass, merge commits only, no force-push, deletion or bypass | — |
| `docker-compose.yml`, `docker/postgres-init.sh` | Local Postgres 16 with roles `gj_owner` (migrations and tests) and `gj_app` (the running app) | — |

---

## 3. Test catalogue: what each test proves

Run all: `cd backend && uv run --env-file .env.test pytest`. Run one: `... pytest tests/<file>.py::<test> -v`.

### `test_env.py`: configuration loading
| Test | Proves |
|---|---|
| `test_required_returns_trimmed_value` | Values are read without surrounding spaces |
| `test_required_fails_fast_when_missing` / `_when_blank` | A missing or blank required setting stops startup |
| `test_optional_uses_default_when_unset` | Optional settings fall back to their default |
| `test_flag_parses_truthy_and_falsy`, `test_flag_default_when_unset` | On/off flags are read correctly |
| `test_listed_splits_and_trims` | Comma-separated lists are parsed |

### `test_health.py`: health check
| Test | Proves |
|---|---|
| `test_health_returns_ok` | `GET /api/health` → `{"status": "ok"}` |
| `test_health_rejects_post` | Only GET is allowed |
| `test_security_headers_present` | `X-Frame-Options: DENY` and `nosniff` are sent |

### `test_db_privileges.py`: least-privilege database role
| Test | Proves |
|---|---|
| `test_app_role_is_not_superuser_and_cannot_bypass_rls` | `gj_app` has no superuser and no row-level-security bypass |
| `test_app_role_owns_no_tables` | The app owns nothing, so it can't disable protections |
| `test_app_role_can_use_migrated_tables` | The app can read and write data |
| `test_tables_created_later_are_granted_to_app_role` | Future tables are accessible automatically |
| `test_app_role_cannot_create_tables` | The app can't change the schema |

### `test_crypto.py`: encryption and lookup keys
| Test | Proves |
|---|---|
| `test_encrypt_round_trip` | Decrypt returns the original value |
| `test_ciphertext_does_not_reveal_plaintext`, `test_encryption_is_randomised` | Stored values reveal nothing, and the same input encrypts differently each time |
| `test_decrypt_rejects_garbage`, `..._with_another_key` | Tampered data or a wrong key fails safely |
| `test_blind_index_is_deterministic_and_normalised` | Same value → same key, ignoring case and spaces |
| `test_blind_index_differs_between_values`, `_depends_on_secret_key`, `_differs_by_context` | Keys can't be guessed or linked across fields |
| `test_blind_index_rejects_empty_context` | Every lookup key must name its field |

### `test_users.py`: accounts and roles
| Test | Proves |
|---|---|
| `test_user_id_is_system_generated`, `test_user_ids_are_unique` | IDs look like `GJ` plus 10 unambiguous characters and are unique |
| `test_password_is_hashed_with_argon2` | Passwords are stored as Argon2 hashes |
| `test_contact_is_encrypted_at_rest` | The contact is encrypted in the database |
| `test_database_rejects_unknown_role` | The database only accepts the 6 roles |
| `test_has_role`, `test_inactive_user_has_no_role` | Role checks work, and deactivated users have no role |
| `test_app_role_cannot_delete_users` | Accounts can never be deleted |

### `test_db_context.py`: row-level-security context
| Test | Proves |
|---|---|
| `test_set_actor_is_visible_to_postgres` | Postgres sees the acting user and role |
| `test_set_actor_refuses_to_run_outside_a_transaction` | The actor can't be set where it would leak |
| `test_middleware_tags_request_with_authenticated_user` | Logged-in requests carry the user's identity |
| `test_middleware_sets_no_actor_for_anonymous_request`, `test_anonymous_request_after_authenticated_request_has_no_actor` | Anonymous requests never inherit a previous identity |
| `test_middleware_rolls_back_writes_on_server_error` | A 5xx undoes the request's writes |

### `test_rollback_on_exception.py`
| Test | Proves |
|---|---|
| `test_raised_exception_rolls_back_audit_write` | A raised 4xx error undoes the request's writes |

### `test_audit_hashing.py` and `test_audit.py`: audit log
| Test | Proves |
|---|---|
| `test_hash_is_64_hex_chars_and_deterministic`, `test_hash_ignores_payload_key_order`, `test_hash_changes_when_any_field_changes` | The hash is stable and sensitive to any change |
| `test_each_event_links_to_the_previous_one` | Entries form a chain |
| `test_verify_passes_on_untouched_chain` | A healthy log verifies |
| `test_record_rejects_nested_payload` | Only simple values can be stored, so hashes are reproducible |
| `test_app_role_cannot_update_events` / `_delete_events` | The app can't edit or delete entries |
| `test_trigger_blocks_changes_even_for_table_owner` | Even the database owner is blocked |
| `test_verify_detects_edited_event` / `_deleted_middle_event` / `_deleted_last_event` | Every kind of tampering is detected |
| `test_verify_accepts_events_appended_after_head_read` | No false alarm when entries are written during a check |
| `test_only_audit_readers_can_read_events` (every role) | Only Software Owner and Head Authority can read the log |
| `test_anonymous_context_cannot_read_events` | Anonymous requests see nothing |
| `test_verify_command_reports_ok` / `_fails_loudly_on_tampering` | The scheduled check reports correctly |

### `test_otp.py`: one-time codes
| Test | Proves |
|---|---|
| `test_issue_sends_six_digit_code_to_registered_contact` | Codes go only to the contact on file |
| `test_code_is_not_stored_in_plaintext` | Only an HMAC of the code is stored |
| `test_correct_code_returns_user_once` | A code works exactly once |
| `test_wrong_code_is_rejected_and_counted`, `test_challenge_closes_after_max_attempts` | Wrong guesses count; after 5 the code is dead |
| `test_expired_code_is_rejected` | Codes expire after 5 minutes |
| `test_new_challenge_supersedes_the_old_one`, `test_database_allows_one_open_challenge_per_user_and_purpose` | Only one open code per user and purpose, even under concurrency |
| `test_inactive_user_cannot_complete_otp` | Deactivated users can't log in |
| `test_malformed_challenge_id_is_rejected` | Junk input fails safely |

### `test_login_api.py`: login API
| Test | Proves |
|---|---|
| `test_full_login_requires_password_and_otp` | The password alone doesn't log you in; password plus code does |
| `test_user_id_is_case_insensitive` | `gj…` and `GJ…` both work |
| `test_wrong_password_and_unknown_user_look_identical` | User IDs can't be discovered from responses |
| `test_locked_and_inactive_accounts_still_check_the_password` | …or from response timing |
| `test_wrong_otp_is_rejected` | A wrong code doesn't log in |
| `test_account_locks_after_repeated_failures` | 5 wrong passwords lock the account |
| `test_account_locks_after_too_many_code_requests` | 5 code requests in 15 minutes lock the account |
| `test_locking_cancels_outstanding_login_code` | A code sent before the lock stops working |
| `test_login_is_rate_limited`, `test_rate_limit_ignores_spoofed_forwarded_for` | 10 per minute per IP, and a faked IP header doesn't bypass it |
| `test_session_cookie_is_hardened` | Session cookie is HttpOnly, Secure and SameSite=Strict |
| `test_logout_ends_session` | Logout really logs out |
| `test_csrf_endpoint_sets_cookie`, `test_login_requires_csrf_token` | Anti-forgery (CSRF) protection is enforced on login |
| `test_login_events_are_audited` | Failures, successes and logouts are written to the audit log |
| `test_unknown_user_attempt_is_not_stored_in_plaintext` | Mistyped IDs or passwords never enter the audit log in plain text |

### `test_permissions.py`: role checks
| Test | Proves |
|---|---|
| `test_listed_role_is_allowed` | The permitted role gets in |
| `test_every_other_role_is_refused` (every role) | Every other role gets 403 |
| `test_anonymous_is_refused`, `test_deactivated_user_is_refused` | Not-logged-in and deactivated users get 403 |

### `test_create_software_owner.py`: first admin account
| Test | Proves |
|---|---|
| `test_creates_first_owner_and_audits_it` | Creates the owner and writes it to the audit log |
| `test_refuses_when_an_owner_already_exists` | It can only ever create the first owner |
| `test_rejects_weak_password`, `test_rejects_mismatched_passwords` | Password rules are enforced |

---

## 4. Conventions every change must follow

| Rule | Why | Enforced by |
|---|---|---|
| Views **raise** to roll back and **return** to commit | No half-saved data | `core/exceptions.py`, `test_rollback_on_exception.py` |
| Call `audit.record()` as the **last** lock in a request | Avoids deadlocks on the audit chain lock | Docstring in `audit/service.py` (code review) |
| Audit payloads hold IDs, codes and lookup keys only, **never personal data** | The log is permanent; DPDP erasure must stay possible | Docstring and code review |
| `blind_index` always names its field (`"licence_number"`, `"gstin"`, …) | Values can't be linked across tables | `test_blind_index_rejects_empty_context` |
| Tests use `app_db` (runs as `gj_app`), never `transactional_db` | Tests see production privileges | `tests/conftest.py` docstring |
| Every new business table gets row-level-security policies in the migration that creates it | Database backstop for access rules | Code review |
| Every change goes feature branch → PR into `dev` → PR from `dev` into `main` | Test in dev before production | GitHub ruleset, `source-branch` check |
| **Update this file in the same PR** | Keeps the map trustworthy | Code review |

Open follow-ups from the reviews: [`superpowers/plans/2026-09-29-phase1-followups.md`](superpowers/plans/2026-09-29-phase1-followups.md).
