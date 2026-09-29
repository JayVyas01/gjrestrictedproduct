"""Tell Postgres who is acting, so row-level security policies can check it.

Values are transaction-local (set_config(..., true)): they disappear at commit or
rollback and can never leak into the next request on a reused connection.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from django.db import connection, transaction

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


@contextmanager
def acting_as_system(job: str) -> Iterator[None]:
    """Briefly act as a named SYSTEM job, e.g. to match a licence during enrolment.

    Use only for reads or writes that genuinely cross owners, keep the block small, and
    return only the minimum data to the caller. The previous actor is restored afterwards.

    The block runs in its own savepoint: on any exception the rollback to that savepoint
    reverts the actor to the previous one without running more SQL (which could mask the
    real error), even if a caller catches the exception and carries on. The price is that
    writes made inside the block are rolled back too; a SYSTEM block is all-or-nothing.
    """
    previous_user, previous_role = current_actor()
    with transaction.atomic():
        set_actor(user_id=job, role=SYSTEM_ROLE)
        yield
        set_actor(user_id=previous_user or "", role=previous_role or "")
