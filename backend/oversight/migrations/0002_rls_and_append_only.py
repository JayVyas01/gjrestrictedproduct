"""Batches are visible to whoever currently holds the batch's (superintendent) position and to
Head Authority, Software Owner and SYSTEM. Only SYSTEM writes. Batches and items are
append-only. The review setting is configuration without RLS (like positions; written only
through set_review_period, which is audited)."""

from django.db import migrations

ROLE = "current_setting('app.role', true)"
HELD = (
    "(SELECT a.position_id FROM positions_personnelassignment a "
    "JOIN identity_user u ON u.id = a.user_id "
    "WHERE u.user_id = current_setting('app.user_id', true) AND a.ended_at IS NULL)"
)
READERS = "('HEAD_AUTHORITY', 'SOFTWARE_OWNER', 'SYSTEM')"


def _append_only(table: str, prefix: str) -> str:
    return f"""
REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM gj_app;
CREATE TRIGGER {prefix}_no_update_delete BEFORE UPDATE OR DELETE ON {table}
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
CREATE TRIGGER {prefix}_no_truncate BEFORE TRUNCATE ON {table}
    FOR EACH STATEMENT EXECUTE FUNCTION reject_append_only_change();
"""


FORWARD = f"""
ALTER TABLE oversight_oversightbatch ENABLE ROW LEVEL SECURITY;
CREATE POLICY batch_read ON oversight_oversightbatch FOR SELECT TO gj_app
    USING (position_id IN {HELD} OR {ROLE} IN {READERS});
CREATE POLICY batch_insert ON oversight_oversightbatch FOR INSERT TO gj_app
    WITH CHECK ({ROLE} = 'SYSTEM');
{_append_only("oversight_oversightbatch", "batch")}
ALTER TABLE oversight_batchitem ENABLE ROW LEVEL SECURITY;
CREATE POLICY item_read ON oversight_batchitem FOR SELECT TO gj_app
    USING (batch_id IN (SELECT id FROM oversight_oversightbatch));
CREATE POLICY item_insert ON oversight_batchitem FOR INSERT TO gj_app
    WITH CHECK ({ROLE} = 'SYSTEM');
{_append_only("oversight_batchitem", "item")}
"""  # noqa: S608 - SQL built only from constants; no user input.

BACKWARD = """
DROP TRIGGER item_no_truncate ON oversight_batchitem;
DROP TRIGGER item_no_update_delete ON oversight_batchitem;
DROP POLICY item_insert ON oversight_batchitem;
DROP POLICY item_read ON oversight_batchitem;
ALTER TABLE oversight_batchitem DISABLE ROW LEVEL SECURITY;
GRANT UPDATE, DELETE ON oversight_batchitem TO gj_app;
DROP TRIGGER batch_no_truncate ON oversight_oversightbatch;
DROP TRIGGER batch_no_update_delete ON oversight_oversightbatch;
DROP POLICY batch_insert ON oversight_oversightbatch;
DROP POLICY batch_read ON oversight_oversightbatch;
ALTER TABLE oversight_oversightbatch DISABLE ROW LEVEL SECURITY;
GRANT UPDATE, DELETE ON oversight_oversightbatch TO gj_app;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("oversight", "0001_initial"),
        ("positions", "0002_one_position_per_area"),
        ("identity", "0009_otp_purpose_decision"),
        ("core", "0002_append_only_guard"),
    ]
    operations = [migrations.RunSQL(sql=FORWARD, reverse_sql=BACKWARD)]
