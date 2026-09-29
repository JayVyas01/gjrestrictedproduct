"""Tell Postgres who is acting, so row-level security policies can check it.

Values are transaction-local (set_config(..., true)): they disappear at commit or
rollback and can never leak into the next request on a reused connection.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from django.db import DatabaseError, connection

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
    return only the minimum data to the caller. The previous actor is restored afterwards,
    except after a database error, where the aborted transaction's rollback reverts it.
    """
    previous_user, previous_role = current_actor()
    set_actor(user_id=job, role=SYSTEM_ROLE)
    try:
        yield
    except DatabaseError:
        # The transaction is aborted and its rollback reverts the actor; running more SQL
        # here would only replace the real error with "current transaction is aborted".
        raise
    except BaseException:
        if not connection.needs_rollback:
            set_actor(user_id=previous_user or "", role=previous_role or "")
        raise
    else:
        set_actor(user_id=previous_user or "", role=previous_role or "")
