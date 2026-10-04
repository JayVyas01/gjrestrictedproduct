"""Who may see and change rule-change proposals.

Read: the drafter (own proposals), Head Authority, Software Owner, Licensing Authority and
SYSTEM. Write: SYSTEM only (services check who may act first). gj_app may update only the
decision columns; a decided proposal (no longer SUBMITTED) cannot change even for the table
owner, and no proposal can be deleted.
"""

from django.db import migrations

ROLE = "current_setting('app.role', true)"
USER_ID = "current_setting('app.user_id', true)"
READERS = "('HEAD_AUTHORITY', 'SOFTWARE_OWNER', 'LICENSING_AUTHORITY', 'SYSTEM')"
DECISION_COLUMNS = "status, decided_by, decided_at, decision_note, applied_ref"

FORWARD = f"""
ALTER TABLE governance_rulechangeproposal ENABLE ROW LEVEL SECURITY;
CREATE POLICY proposal_drafter_read ON governance_rulechangeproposal FOR SELECT TO gj_app
    USING (drafted_by = {USER_ID});
CREATE POLICY proposal_authority_read ON governance_rulechangeproposal FOR SELECT TO gj_app
    USING ({ROLE} IN {READERS});
CREATE POLICY proposal_insert ON governance_rulechangeproposal FOR INSERT TO gj_app
    WITH CHECK ({ROLE} = 'SYSTEM');
CREATE POLICY proposal_update ON governance_rulechangeproposal FOR UPDATE TO gj_app
    USING ({ROLE} = 'SYSTEM') WITH CHECK ({ROLE} = 'SYSTEM');
REVOKE UPDATE, DELETE, TRUNCATE ON governance_rulechangeproposal FROM gj_app;
GRANT UPDATE ({DECISION_COLUMNS}) ON governance_rulechangeproposal TO gj_app;

CREATE FUNCTION reject_decided_proposal_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status <> 'SUBMITTED' THEN
        RAISE EXCEPTION 'Rule-change proposal % has already been decided', OLD.id;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER proposal_decided_is_final BEFORE UPDATE ON governance_rulechangeproposal
    FOR EACH ROW EXECUTE FUNCTION reject_decided_proposal_change();
CREATE TRIGGER proposal_no_delete BEFORE DELETE ON governance_rulechangeproposal
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
CREATE TRIGGER proposal_no_truncate BEFORE TRUNCATE ON governance_rulechangeproposal
    FOR EACH STATEMENT EXECUTE FUNCTION reject_append_only_change();
"""  # noqa: S608 - SQL built only from the constants above; no user input.

BACKWARD = f"""
DROP TRIGGER proposal_no_truncate ON governance_rulechangeproposal;
DROP TRIGGER proposal_no_delete ON governance_rulechangeproposal;
DROP TRIGGER proposal_decided_is_final ON governance_rulechangeproposal;
DROP FUNCTION reject_decided_proposal_change();
REVOKE UPDATE ({DECISION_COLUMNS}) ON governance_rulechangeproposal FROM gj_app;
GRANT UPDATE, DELETE ON governance_rulechangeproposal TO gj_app;
DROP POLICY proposal_update ON governance_rulechangeproposal;
DROP POLICY proposal_insert ON governance_rulechangeproposal;
DROP POLICY proposal_authority_read ON governance_rulechangeproposal;
DROP POLICY proposal_drafter_read ON governance_rulechangeproposal;
ALTER TABLE governance_rulechangeproposal DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("governance", "0001_initial"),
        ("core", "0002_append_only_guard"),
    ]
    operations = [migrations.RunSQL(sql=FORWARD, reverse_sql=BACKWARD)]
