"""Rule versions are never edited: a change is a new version (spec D3)."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("catalogue", "0001_initial"),
        ("core", "0001_app_role_privileges"),
    ]
    operations = [
        migrations.RunSQL(
            sql="REVOKE UPDATE, DELETE, TRUNCATE ON catalogue_licencetyperuleversion FROM gj_app;",
            reverse_sql="GRANT UPDATE, DELETE ON catalogue_licencetyperuleversion TO gj_app;",
        ),
    ]
