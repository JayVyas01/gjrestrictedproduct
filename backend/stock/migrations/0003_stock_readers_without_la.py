"""DPDP data minimisation: the Licensing Authority no longer reads stock. Holders still read
their own business; Head Authority, Software Owner and SYSTEM read all."""

from django.db import migrations

ROLE = "current_setting('app.role', true)"
OWN_GSTIN = (
    "(SELECT licensee_gstin_index FROM identity_user "
    "WHERE user_id = current_setting('app.user_id', true) AND licensee_gstin_index <> '')"
)
READERS = "('HEAD_AUTHORITY', 'SOFTWARE_OWNER', 'SYSTEM')"
OLD_READERS = "('HEAD_AUTHORITY', 'SOFTWARE_OWNER', 'LICENSING_AUTHORITY', 'SYSTEM')"


def _read_policies(readers: str) -> str:
    return f"""
DROP POLICY balance_read ON stock_stockbalance;
CREATE POLICY balance_read ON stock_stockbalance FOR SELECT TO gj_app
    USING (gstin_index = {OWN_GSTIN} OR {ROLE} IN {readers});
DROP POLICY movement_read ON stock_stockmovement;
CREATE POLICY movement_read ON stock_stockmovement FOR SELECT TO gj_app
    USING (gstin_index = {OWN_GSTIN} OR {ROLE} IN {readers});
"""  # noqa: S608


class Migration(migrations.Migration):
    dependencies = [("stock", "0002_rls_and_append_only")]
    operations = [
        migrations.RunSQL(sql=_read_policies(READERS), reverse_sql=_read_policies(OLD_READERS))
    ]
