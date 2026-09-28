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
