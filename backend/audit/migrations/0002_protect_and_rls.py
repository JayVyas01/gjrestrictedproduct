"""Make the audit trail append-only and readable only by oversight roles.

Three independent layers:
1. REVOKE: the app role has no UPDATE/DELETE/TRUNCATE privilege at all.
2. Trigger: even the table owner cannot update or delete without first disabling it.
3. RLS: only SOFTWARE_OWNER, HEAD_AUTHORITY and SYSTEM jobs can read events.
   Keep this role list in sync with identity.roles.AUDIT_READERS (a test enforces it).
"""

from django.db import migrations

FORWARD = """
CREATE FUNCTION audit_reject_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit events are append-only';
END $$;

CREATE TRIGGER audit_event_no_update_delete
    BEFORE UPDATE OR DELETE ON audit_auditevent
    FOR EACH ROW EXECUTE FUNCTION audit_reject_change();
CREATE TRIGGER audit_event_no_truncate
    BEFORE TRUNCATE ON audit_auditevent
    FOR EACH STATEMENT EXECUTE FUNCTION audit_reject_change();

REVOKE UPDATE, DELETE, TRUNCATE ON audit_auditevent FROM gj_app;
REVOKE DELETE, TRUNCATE ON audit_auditchainhead FROM gj_app;

ALTER TABLE audit_auditevent ENABLE ROW LEVEL SECURITY;
CREATE POLICY audit_insert ON audit_auditevent FOR INSERT TO gj_app WITH CHECK (true);
CREATE POLICY audit_read ON audit_auditevent FOR SELECT TO gj_app
    USING (current_setting('app.role', true) IN ('SOFTWARE_OWNER', 'HEAD_AUTHORITY', 'SYSTEM'));

INSERT INTO audit_auditchainhead (id, last_hash) VALUES (1, repeat('0', 64));
"""

BACKWARD = """
DELETE FROM audit_auditchainhead;
DROP POLICY audit_read ON audit_auditevent;
DROP POLICY audit_insert ON audit_auditevent;
ALTER TABLE audit_auditevent DISABLE ROW LEVEL SECURITY;
GRANT UPDATE, DELETE ON audit_auditevent TO gj_app;
GRANT DELETE ON audit_auditchainhead TO gj_app;
DROP TRIGGER audit_event_no_truncate ON audit_auditevent;
DROP TRIGGER audit_event_no_update_delete ON audit_auditevent;
DROP FUNCTION audit_reject_change();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0001_initial"),
        ("core", "0001_app_role_privileges"),
    ]
    operations = [migrations.RunSQL(sql=FORWARD, reverse_sql=BACKWARD)]
