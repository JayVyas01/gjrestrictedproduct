"""Stock access: holders read their own business; authorities and SYSTEM read all; only
SYSTEM writes. Balances change only via quantity; movements are append-only."""

from django.db import migrations

ROLE = "current_setting('app.role', true)"
OWN_GSTIN = (
    "(SELECT licensee_gstin_index FROM identity_user "
    "WHERE user_id = current_setting('app.user_id', true) AND licensee_gstin_index <> '')"
)
READERS = "('HEAD_AUTHORITY', 'SOFTWARE_OWNER', 'LICENSING_AUTHORITY', 'SYSTEM')"

FORWARD = f"""
ALTER TABLE stock_stockbalance ENABLE ROW LEVEL SECURITY;
CREATE POLICY balance_read ON stock_stockbalance FOR SELECT TO gj_app
    USING (gstin_index = {OWN_GSTIN} OR {ROLE} IN {READERS});
CREATE POLICY balance_insert ON stock_stockbalance FOR INSERT TO gj_app
    WITH CHECK ({ROLE} = 'SYSTEM');
CREATE POLICY balance_update ON stock_stockbalance FOR UPDATE TO gj_app
    USING ({ROLE} = 'SYSTEM') WITH CHECK ({ROLE} = 'SYSTEM');
REVOKE UPDATE, DELETE, TRUNCATE ON stock_stockbalance FROM gj_app;
GRANT UPDATE (quantity, updated_at) ON stock_stockbalance TO gj_app;

ALTER TABLE stock_stockmovement ENABLE ROW LEVEL SECURITY;
CREATE POLICY movement_read ON stock_stockmovement FOR SELECT TO gj_app
    USING (gstin_index = {OWN_GSTIN} OR {ROLE} IN {READERS});
CREATE POLICY movement_insert ON stock_stockmovement FOR INSERT TO gj_app
    WITH CHECK ({ROLE} = 'SYSTEM');
REVOKE UPDATE, DELETE, TRUNCATE ON stock_stockmovement FROM gj_app;
CREATE TRIGGER movement_no_update_delete BEFORE UPDATE OR DELETE ON stock_stockmovement
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
CREATE TRIGGER movement_no_truncate BEFORE TRUNCATE ON stock_stockmovement
    FOR EACH STATEMENT EXECUTE FUNCTION reject_append_only_change();
"""  # noqa: S608

BACKWARD = """
DROP TRIGGER movement_no_truncate ON stock_stockmovement;
DROP TRIGGER movement_no_update_delete ON stock_stockmovement;
DROP POLICY movement_insert ON stock_stockmovement;
DROP POLICY movement_read ON stock_stockmovement;
ALTER TABLE stock_stockmovement DISABLE ROW LEVEL SECURITY;
GRANT UPDATE, DELETE ON stock_stockmovement TO gj_app;
REVOKE UPDATE (quantity, updated_at) ON stock_stockbalance FROM gj_app;
DROP POLICY balance_update ON stock_stockbalance;
DROP POLICY balance_insert ON stock_stockbalance;
DROP POLICY balance_read ON stock_stockbalance;
ALTER TABLE stock_stockbalance DISABLE ROW LEVEL SECURITY;
GRANT UPDATE, DELETE ON stock_stockbalance TO gj_app;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("stock", "0001_initial"),
        ("identity", "0008_one_account_per_licensee_gstin"),
        ("core", "0002_append_only_guard"),
    ]
    operations = [migrations.RunSQL(sql=FORWARD, reverse_sql=BACKWARD)]
