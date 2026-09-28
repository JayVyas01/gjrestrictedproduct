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
