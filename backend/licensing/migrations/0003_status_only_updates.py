"""Only a licence's status may change after it is recorded.

Without this, an authority or SYSTEM context could rewrite any column, for example move a
licence to another holder by changing its GSTIN index.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("licensing", "0002_rls_and_append_only")]
    operations = [
        migrations.RunSQL(
            sql="""
            REVOKE UPDATE ON licensing_licence FROM gj_app;
            GRANT UPDATE (status) ON licensing_licence TO gj_app;
            """,
            reverse_sql="""
            REVOKE UPDATE (status) ON licensing_licence FROM gj_app;
            GRANT UPDATE ON licensing_licence TO gj_app;
            """,
        )
    ]
