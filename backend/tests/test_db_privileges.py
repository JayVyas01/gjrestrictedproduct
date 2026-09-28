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
