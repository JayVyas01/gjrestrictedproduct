"""Shared guard for append-only tables.

Attach it in the table's own migration with two triggers: a row trigger
BEFORE UPDATE OR DELETE ... FOR EACH ROW, and a statement trigger BEFORE TRUNCATE
... FOR EACH STATEMENT, both EXECUTE FUNCTION reject_append_only_change(). Together with
a REVOKE from gj_app this stops even the table owner editing history by accident.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("core", "0001_app_role_privileges")]
    operations = [
        migrations.RunSQL(
            sql="""
            CREATE FUNCTION reject_append_only_change() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION '% is append-only', TG_TABLE_NAME; END $$;
            """,
            reverse_sql="DROP FUNCTION reject_append_only_change();",
        ),
    ]
