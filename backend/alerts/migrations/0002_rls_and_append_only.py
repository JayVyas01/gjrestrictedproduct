"""Alerts are visible to whoever currently holds the addressed position, and to Head Authority,
Software Owner and SYSTEM. Only SYSTEM writes. Alerts and acknowledgements are append-only."""

from django.db import migrations

ROLE = "current_setting('app.role', true)"
HELD = (
    "(SELECT a.position_id FROM positions_personnelassignment a "
    "JOIN identity_user u ON u.id = a.user_id "
    "WHERE u.user_id = current_setting('app.user_id', true) AND a.ended_at IS NULL)"
)
READERS = "('HEAD_AUTHORITY', 'SOFTWARE_OWNER', 'SYSTEM')"

FORWARD = f"""
ALTER TABLE alerts_authorityalert ENABLE ROW LEVEL SECURITY;
CREATE POLICY alert_read ON alerts_authorityalert FOR SELECT TO gj_app
    USING (position_id IN {HELD} OR {ROLE} IN {READERS});
CREATE POLICY alert_insert ON alerts_authorityalert FOR INSERT TO gj_app
    WITH CHECK ({ROLE} = 'SYSTEM');
REVOKE UPDATE, DELETE, TRUNCATE ON alerts_authorityalert FROM gj_app;
CREATE TRIGGER alert_no_update_delete BEFORE UPDATE OR DELETE ON alerts_authorityalert
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
CREATE TRIGGER alert_no_truncate BEFORE TRUNCATE ON alerts_authorityalert
    FOR EACH STATEMENT EXECUTE FUNCTION reject_append_only_change();

ALTER TABLE alerts_alertacknowledgement ENABLE ROW LEVEL SECURITY;
CREATE POLICY ack_read ON alerts_alertacknowledgement FOR SELECT TO gj_app
    USING (alert_id IN (SELECT id FROM alerts_authorityalert));
CREATE POLICY ack_insert ON alerts_alertacknowledgement FOR INSERT TO gj_app
    WITH CHECK ({ROLE} = 'SYSTEM');
REVOKE UPDATE, DELETE, TRUNCATE ON alerts_alertacknowledgement FROM gj_app;
CREATE TRIGGER ack_no_update_delete BEFORE UPDATE OR DELETE ON alerts_alertacknowledgement
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
CREATE TRIGGER ack_no_truncate BEFORE TRUNCATE ON alerts_alertacknowledgement
    FOR EACH STATEMENT EXECUTE FUNCTION reject_append_only_change();
"""  # noqa: S608 - SQL built only from the constants above; no user input.

BACKWARD = """
DROP TRIGGER ack_no_truncate ON alerts_alertacknowledgement;
DROP TRIGGER ack_no_update_delete ON alerts_alertacknowledgement;
DROP POLICY ack_insert ON alerts_alertacknowledgement;
DROP POLICY ack_read ON alerts_alertacknowledgement;
ALTER TABLE alerts_alertacknowledgement DISABLE ROW LEVEL SECURITY;
GRANT UPDATE, DELETE ON alerts_alertacknowledgement TO gj_app;
DROP TRIGGER alert_no_truncate ON alerts_authorityalert;
DROP TRIGGER alert_no_update_delete ON alerts_authorityalert;
DROP POLICY alert_insert ON alerts_authorityalert;
DROP POLICY alert_read ON alerts_authorityalert;
ALTER TABLE alerts_authorityalert DISABLE ROW LEVEL SECURITY;
GRANT UPDATE, DELETE ON alerts_authorityalert TO gj_app;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("alerts", "0001_initial"),
        ("positions", "0002_one_position_per_area"),
        ("identity", "0009_otp_purpose_decision"),
        ("core", "0002_append_only_guard"),
    ]
    operations = [migrations.RunSQL(sql=FORWARD, reverse_sql=BACKWARD)]
