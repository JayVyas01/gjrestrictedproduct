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
