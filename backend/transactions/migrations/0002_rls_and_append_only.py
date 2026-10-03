"""Who may see and change transactions.

Read: the seller's and buyer's businesses (GSTIN index), whoever currently holds the designated
or superintendent position, and Head Authority / Software Owner / SYSTEM. Write: SYSTEM only
(services check who may act first). Only status and decided_at can change. Decisions follow
their transaction's visibility and are append-only.
"""

from django.db import migrations

ROLE = "current_setting('app.role', true)"
OWN_GSTIN = (
    "(SELECT licensee_gstin_index FROM identity_user "
    "WHERE user_id = current_setting('app.user_id', true) AND licensee_gstin_index <> '')"
)
HELD = (
    "(SELECT a.position_id FROM positions_personnelassignment a "
    "JOIN identity_user u ON u.id = a.user_id "
    "WHERE u.user_id = current_setting('app.user_id', true) AND a.ended_at IS NULL)"
)
READERS = "('HEAD_AUTHORITY', 'SOFTWARE_OWNER', 'SYSTEM')"

FORWARD = f"""
ALTER TABLE transactions_transaction ENABLE ROW LEVEL SECURITY;
CREATE POLICY tx_party_read ON transactions_transaction FOR SELECT TO gj_app
    USING (seller_gstin_index = {OWN_GSTIN} OR buyer_gstin_index = {OWN_GSTIN});
CREATE POLICY tx_officer_read ON transactions_transaction FOR SELECT TO gj_app
    USING (designated_position_id IN {HELD} OR superintendent_position_id IN {HELD});
CREATE POLICY tx_authority_read ON transactions_transaction FOR SELECT TO gj_app
    USING ({ROLE} IN {READERS});
CREATE POLICY tx_insert ON transactions_transaction FOR INSERT TO gj_app
    WITH CHECK ({ROLE} = 'SYSTEM');
CREATE POLICY tx_update ON transactions_transaction FOR UPDATE TO gj_app
    USING ({ROLE} = 'SYSTEM') WITH CHECK ({ROLE} = 'SYSTEM');
REVOKE UPDATE, DELETE, TRUNCATE ON transactions_transaction FROM gj_app;
GRANT UPDATE (status, decided_at) ON transactions_transaction TO gj_app;

ALTER TABLE transactions_transactiondecision ENABLE ROW LEVEL SECURITY;
CREATE POLICY decision_read ON transactions_transactiondecision FOR SELECT TO gj_app
    USING (transaction_id IN (SELECT id FROM transactions_transaction));
CREATE POLICY decision_insert ON transactions_transactiondecision FOR INSERT TO gj_app
    WITH CHECK ({ROLE} = 'SYSTEM');
REVOKE UPDATE, DELETE, TRUNCATE ON transactions_transactiondecision FROM gj_app;
CREATE TRIGGER decision_no_update_delete BEFORE UPDATE OR DELETE
    ON transactions_transactiondecision
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
CREATE TRIGGER decision_no_truncate BEFORE TRUNCATE ON transactions_transactiondecision
    FOR EACH STATEMENT EXECUTE FUNCTION reject_append_only_change();
"""  # noqa: S608

BACKWARD = """
DROP TRIGGER decision_no_truncate ON transactions_transactiondecision;
DROP TRIGGER decision_no_update_delete ON transactions_transactiondecision;
DROP POLICY decision_insert ON transactions_transactiondecision;
DROP POLICY decision_read ON transactions_transactiondecision;
ALTER TABLE transactions_transactiondecision DISABLE ROW LEVEL SECURITY;
GRANT UPDATE, DELETE ON transactions_transactiondecision TO gj_app;
REVOKE UPDATE (status, decided_at) ON transactions_transaction FROM gj_app;
DROP POLICY tx_update ON transactions_transaction;
DROP POLICY tx_insert ON transactions_transaction;
DROP POLICY tx_authority_read ON transactions_transaction;
DROP POLICY tx_officer_read ON transactions_transaction;
DROP POLICY tx_party_read ON transactions_transaction;
ALTER TABLE transactions_transaction DISABLE ROW LEVEL SECURITY;
GRANT UPDATE, DELETE ON transactions_transaction TO gj_app;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("transactions", "0001_initial"),
        ("identity", "0008_one_account_per_licensee_gstin"),
        ("positions", "0002_one_position_per_area"),
        ("core", "0002_append_only_guard"),
    ]
    operations = [migrations.RunSQL(sql=FORWARD, reverse_sql=BACKWARD)]
