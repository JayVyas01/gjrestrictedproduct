"""Rule versions are append-only for everyone, including the table owner."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("catalogue", "0002_append_only_versions"),
        ("core", "0002_append_only_guard"),
    ]
    operations = [
        migrations.RunSQL(
            sql="""
            CREATE TRIGGER rule_version_no_update_delete BEFORE UPDATE OR DELETE
              ON catalogue_licencetyperuleversion FOR EACH ROW
              EXECUTE FUNCTION reject_append_only_change();
            CREATE TRIGGER rule_version_no_truncate BEFORE TRUNCATE
              ON catalogue_licencetyperuleversion FOR EACH STATEMENT
              EXECUTE FUNCTION reject_append_only_change();
            """,
            reverse_sql="""
            DROP TRIGGER rule_version_no_truncate ON catalogue_licencetyperuleversion;
            DROP TRIGGER rule_version_no_update_delete ON catalogue_licencetyperuleversion;
            """,
        ),
    ]
