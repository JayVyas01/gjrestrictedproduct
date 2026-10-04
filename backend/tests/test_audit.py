import pytest
from django.core.management import CommandError, call_command
from django.db import DatabaseError, connection, transaction

from audit.hashing import GENESIS_HASH
from audit.models import AuditEvent
from audit.service import record
from audit.verify import verify_chain
from core.db_context import SYSTEM_ROLE, set_actor
from identity.roles import AUDIT_READERS, Role

pytestmark = pytest.mark.django_db


def verify_as_system():
    with transaction.atomic():
        set_actor(user_id="test", role=SYSTEM_ROLE)
        return verify_chain()


def events_as_system():
    with transaction.atomic():
        set_actor(user_id="test", role=SYSTEM_ROLE)
        return list(AuditEvent.objects.order_by("id"))


def tamper(sql):
    """Act as the schema owner with the trigger disabled, simulating a DB-level attacker."""
    with connection.cursor() as cursor:
        cursor.execute("ALTER TABLE audit_auditevent DISABLE TRIGGER audit_event_no_update_delete")
        cursor.execute(sql)
        cursor.execute("ALTER TABLE audit_auditevent ENABLE TRIGGER audit_event_no_update_delete")


def test_each_event_links_to_the_previous_one(app_db):
    record(action="test.first", actor="GJTESTUSER01")
    record(action="test.second")
    first, second = events_as_system()
    assert first.prev_hash == GENESIS_HASH
    assert second.prev_hash == first.hash


def test_verify_passes_on_untouched_chain(app_db):
    record(action="test.first")
    record(action="test.second", payload={"count": 2, "ok": True, "note": None})
    report = verify_as_system()
    assert report.ok
    assert report.checked == 2


def test_record_rejects_nested_payload(app_db):
    with pytest.raises(TypeError):
        record(action="test.bad", payload={"nested": {"a": 1}})


def test_app_role_cannot_update_events(app_db):
    record(action="test.event")
    with pytest.raises(DatabaseError, match="permission denied"):
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("UPDATE audit_auditevent SET action = 'forged'")


def test_app_role_cannot_delete_events(app_db):
    record(action="test.event")
    with pytest.raises(DatabaseError, match="permission denied"):
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("DELETE FROM audit_auditevent")


def test_trigger_blocks_changes_even_for_table_owner(db):
    record(action="test.event")
    with pytest.raises(DatabaseError, match="append-only"):
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("UPDATE audit_auditevent SET action = 'forged'")


def test_verify_detects_edited_event(db):
    record(action="test.first")
    record(action="test.second")
    tamper("UPDATE audit_auditevent SET reason = 'forged' WHERE action = 'test.first'")
    report = verify_as_system()
    assert not report.ok
    assert report.problem == "event contents do not match its hash"


def test_verify_detects_deleted_middle_event(db):
    for action in ("test.first", "test.second", "test.third"):
        record(action=action)
    tamper("DELETE FROM audit_auditevent WHERE action = 'test.second'")
    report = verify_as_system()
    assert not report.ok
    assert report.problem == "prev_hash does not match the previous event"


def test_verify_detects_deleted_last_event(db):
    record(action="test.first")
    record(action="test.second")
    tamper("DELETE FROM audit_auditevent WHERE action = 'test.second'")
    report = verify_as_system()
    assert not report.ok
    assert report.problem == "chain head does not match the last event"


def test_verify_accepts_events_appended_after_head_read(db):
    record(action="test.first")
    record(action="test.second")
    first_hash = events_as_system()[0].hash
    with connection.cursor() as cursor:
        cursor.execute("UPDATE audit_auditchainhead SET last_hash = %s WHERE id = 1", [first_hash])
    report = verify_as_system()
    assert report.ok
    assert report.checked == 2


@pytest.mark.parametrize("role", list(Role))
def test_only_audit_readers_can_read_events(app_db, role):
    record(action="test.event")
    with transaction.atomic():
        set_actor(user_id="GJTESTUSER01", role=role)
        visible = AuditEvent.objects.count()
    assert visible == (1 if role in AUDIT_READERS else 0)


def test_anonymous_context_cannot_read_events(app_db):
    record(action="test.event")
    assert AuditEvent.objects.count() == 0


def test_verify_command_reports_ok(app_db, capsys):
    record(action="test.event")
    call_command("verify_audit_chain")
    assert "Audit chain OK (1 events)" in capsys.readouterr().out


def test_verify_command_fails_loudly_on_tampering(db):
    record(action="test.event")
    tamper("UPDATE audit_auditevent SET actor = 'forged'")
    with pytest.raises(CommandError, match="BROKEN"):
        call_command("verify_audit_chain")
