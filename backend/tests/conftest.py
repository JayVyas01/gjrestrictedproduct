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
