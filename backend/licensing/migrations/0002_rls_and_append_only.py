"""Who may see and change licence data.

- A licensee reads only licences whose GSTIN index matches their account.
- Licensing Authority, Head Authority, Software Owner and SYSTEM jobs read all licences.
- Only Licensing Authority and SYSTEM jobs write.
- Periods and snapshots are visible exactly when their licence is, and are append-only.
Personnel read access (for transactions routed to them) is added in plan D2.
"""

from django.db import migrations

READERS = "('LICENSING_AUTHORITY', 'HEAD_AUTHORITY', 'SOFTWARE_OWNER', 'SYSTEM')"
WRITERS = "('LICENSING_AUTHORITY', 'SYSTEM')"
ROLE = "current_setting('app.role', true)"
OWN_GSTIN = (
    "(SELECT licensee_gstin_index FROM identity_user "
    "WHERE user_id = current_setting('app.user_id', true) AND licensee_gstin_index <> '')"
)

# The SQL is built only from the constants above; no user input ever reaches it.
FORWARD = f"""
ALTER TABLE licensing_licence ENABLE ROW LEVEL SECURITY;
CREATE POLICY licence_holder_read ON licensing_licence FOR SELECT TO gj_app
    USING (gstin_index = {OWN_GSTIN});
CREATE POLICY licence_authority_read ON licensing_licence FOR SELECT TO gj_app
    USING ({ROLE} IN {READERS});
CREATE POLICY licence_insert ON licensing_licence FOR INSERT TO gj_app
    WITH CHECK ({ROLE} IN {WRITERS});
CREATE POLICY licence_update ON licensing_licence FOR UPDATE TO gj_app
    USING ({ROLE} IN {WRITERS}) WITH CHECK ({ROLE} IN {WRITERS});
REVOKE DELETE, TRUNCATE ON licensing_licence FROM gj_app;

ALTER TABLE licensing_licencevalidityperiod ENABLE ROW LEVEL SECURITY;
CREATE POLICY period_read ON licensing_licencevalidityperiod FOR SELECT TO gj_app
    USING (licence_id IN (SELECT id FROM licensing_licence));
CREATE POLICY period_insert ON licensing_licencevalidityperiod FOR INSERT TO gj_app
    WITH CHECK ({ROLE} IN {WRITERS});
REVOKE UPDATE, DELETE, TRUNCATE ON licensing_licencevalidityperiod FROM gj_app;
CREATE TRIGGER period_append_only BEFORE UPDATE OR DELETE ON licensing_licencevalidityperiod
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
CREATE TRIGGER period_no_truncate BEFORE TRUNCATE ON licensing_licencevalidityperiod
    FOR EACH STATEMENT EXECUTE FUNCTION reject_append_only_change();

ALTER TABLE licensing_licencepermissionssnapshot ENABLE ROW LEVEL SECURITY;
CREATE POLICY snapshot_read ON licensing_licencepermissionssnapshot FOR SELECT TO gj_app
    USING (licence_id IN (SELECT id FROM licensing_licence));
CREATE POLICY snapshot_insert ON licensing_licencepermissionssnapshot FOR INSERT TO gj_app
    WITH CHECK ({ROLE} IN {WRITERS});
REVOKE UPDATE, DELETE, TRUNCATE ON licensing_licencepermissionssnapshot FROM gj_app;
CREATE TRIGGER snapshot_append_only BEFORE UPDATE OR DELETE ON licensing_licencepermissionssnapshot
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
CREATE TRIGGER snapshot_no_truncate BEFORE TRUNCATE ON licensing_licencepermissionssnapshot
    FOR EACH STATEMENT EXECUTE FUNCTION reject_append_only_change();
"""  # noqa: S608

BACKWARD = """
DROP TRIGGER snapshot_no_truncate ON licensing_licencepermissionssnapshot;
DROP TRIGGER snapshot_append_only ON licensing_licencepermissionssnapshot;
DROP TRIGGER period_no_truncate ON licensing_licencevalidityperiod;
DROP TRIGGER period_append_only ON licensing_licencevalidityperiod;
DROP POLICY snapshot_insert ON licensing_licencepermissionssnapshot;
DROP POLICY snapshot_read ON licensing_licencepermissionssnapshot;
ALTER TABLE licensing_licencepermissionssnapshot DISABLE ROW LEVEL SECURITY;
DROP POLICY period_insert ON licensing_licencevalidityperiod;
DROP POLICY period_read ON licensing_licencevalidityperiod;
ALTER TABLE licensing_licencevalidityperiod DISABLE ROW LEVEL SECURITY;
DROP POLICY licence_update ON licensing_licence;
DROP POLICY licence_insert ON licensing_licence;
DROP POLICY licence_authority_read ON licensing_licence;
DROP POLICY licence_holder_read ON licensing_licence;
ALTER TABLE licensing_licence DISABLE ROW LEVEL SECURITY;
GRANT UPDATE, DELETE ON licensing_licencevalidityperiod TO gj_app;
GRANT UPDATE, DELETE ON licensing_licencepermissionssnapshot TO gj_app;
GRANT DELETE ON licensing_licence TO gj_app;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("licensing", "0001_initial"),
        ("identity", "0007_user_licensee_gstin_index"),
        ("core", "0001_app_role_privileges"),
        ("core", "0002_append_only_guard"),
    ]
    operations = [migrations.RunSQL(sql=FORWARD, reverse_sql=BACKWARD)]
