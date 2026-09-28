"""Shared test fixtures.

Use `app_db` (not `db`) for anything that exercises application behaviour, so the test runs
with the same restricted privileges as production. Use plain `db` only when a test must act as
the schema owner, for example to simulate an attacker tampering with the audit table.
Never use `transactional_db`: its TRUNCATE-based teardown is blocked by the audit trigger.
"""

import pytest
from django.db import connection, transaction

from audit.models import AuditEvent
from core.db_context import SYSTEM_ROLE, set_actor
from identity.models import User
from identity.roles import Role

TEST_PASSWORD = "correct-horse-battery-9"


@pytest.fixture
def app_db(db):
    # SET ROLE is undone automatically when the test transaction rolls back.
    with connection.cursor() as cursor:
        cursor.execute("SET ROLE gj_app")


@pytest.fixture
def make_user(db):
    def _make(role=Role.LICENSEE, password=TEST_PASSWORD, contact="+919800000001") -> User:
        return User.objects.create_user(role=role, password=password, contact=contact)

    return _make


@pytest.fixture
def audit_actions():
    """Return a function listing audit actions recorded so far in this test."""

    def _read() -> list[str]:
        with transaction.atomic():
            set_actor(user_id="test", role=SYSTEM_ROLE)
            return list(AuditEvent.objects.order_by("id").values_list("action", flat=True))

    return _read
