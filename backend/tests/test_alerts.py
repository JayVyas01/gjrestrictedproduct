from datetime import timedelta

import pytest
from django.db import DatabaseError, transaction
from django.utils import timezone

from alerts.models import AlertAcknowledgement, AuthorityAlert
from alerts.service import NotAllowed, acknowledge, ordinal, pattern_text
from core.db_context import acting_as_system, set_actor
from identity.roles import Role
from positions.service import assign
from transactions.models import Transaction

pytestmark = pytest.mark.django_db


def visible_alerts(user):
    with transaction.atomic():
        set_actor(user_id=user.user_id, role=user.role)
        return list(AuthorityAlert.objects.order_by("id"))


@pytest.mark.parametrize(
    ("n", "text"),
    [
        (1, "1st"),
        (2, "2nd"),
        (3, "3rd"),
        (4, "4th"),
        (11, "11th"),
        (12, "12th"),
        (13, "13th"),
        (21, "21st"),
        (22, "22nd"),
        (103, "103rd"),
    ],
)
def test_ordinal(n, text):
    assert ordinal(n) == text


def test_pattern_text():
    assert pattern_text(3) == "3rd buyer rejection for this seller in the last 30 days"


def test_buyer_rejection_alerts_officer_and_superintendent(
    app_db, org, trade, settle, audit_actions
):
    tx = settle(buyer="REJECT", reason_code="NOT_ORDERED")
    with acting_as_system("test"):
        alerts = list(AuthorityAlert.objects.filter(transaction=tx).order_by("id"))
    assert [a.position for a in alerts] == [org.area_officer, org.district_officer]
    assert {a.kind for a in alerts} == {"BUYER_REJECTION"}
    assert alerts[0].reason.code == "NOT_ORDERED" and alerts[0].pattern_count == 1
    assert audit_actions()[-1] == "transaction.buyer_rejected"


def test_buyer_comment_is_kept_on_the_alert(app_db, trade, settle):
    tx = settle(buyer="REJECT", reason_code="OTHER", comment="Never ordered from them")
    with acting_as_system("test"):
        assert (
            AuthorityAlert.objects.filter(transaction=tx).first().comment
            == "Never ordered from them"
        )


def test_confirm_and_officer_reject_raise_no_alerts(app_db, trade, settle):
    settle()
    settle(officer="REJECT", reason_code="QUANTITY_MISMATCH")
    with acting_as_system("test"):
        assert AuthorityAlert.objects.count() == 0


def test_pattern_counts_recent_rejections(app_db, trade, settle):
    for _ in range(3):
        last = settle(buyer="REJECT", reason_code="NOT_ORDERED")
    with acting_as_system("test"):
        assert AuthorityAlert.objects.filter(transaction=last).first().pattern_count == 3


def test_pattern_ignores_rejections_older_than_30_days(app_db, trade, settle):
    old = settle(buyer="REJECT", reason_code="NOT_ORDERED")
    with acting_as_system("test"):
        Transaction.objects.filter(pk=old.pk).update(decided_at=timezone.now() - timedelta(days=31))
    recent = settle(buyer="REJECT", reason_code="NOT_ORDERED")
    with acting_as_system("test"):
        assert AuthorityAlert.objects.filter(transaction=recent).first().pattern_count == 1


def test_only_position_holders_and_authorities_see_alerts(app_db, trade, settle, make_user):
    settle(buyer="REJECT", reason_code="NOT_ORDERED")
    head = make_user(role=Role.HEAD_AUTHORITY)
    stranger = make_user(role=Role.PERSONNEL)
    assert len(visible_alerts(trade.officer)) == 1
    assert len(visible_alerts(trade.superintendent)) == 1
    assert len(visible_alerts(head)) == 2
    assert (
        visible_alerts(trade.seller)
        == visible_alerts(trade.buyer)
        == visible_alerts(stranger)
        == []
    )


def test_alert_follows_the_position_after_transfer(
    app_db, org, trade, settle, make_user, audit_actions
):
    settle(buyer="REJECT", reason_code="NOT_ORDERED")
    replacement = make_user(role=Role.PERSONNEL)
    assign(org.area_officer, replacement, by="test")
    assert visible_alerts(trade.officer) == []
    [alert] = visible_alerts(replacement)
    set_actor(user_id=replacement.user_id, role=replacement.role)
    ack = acknowledge(alert_id=alert.id, user=replacement, note="Called the buyer")
    assert ack.user_id == replacement.user_id
    assert audit_actions()[-1] == "alert.acknowledged"


def test_acknowledge_rules(app_db, trade, settle):
    settle(buyer="REJECT", reason_code="NOT_ORDERED")
    [officer_alert] = visible_alerts(trade.officer)
    set_actor(user_id=trade.superintendent.user_id, role=trade.superintendent.role)
    with pytest.raises(NotAllowed, match="Only the officer holding this position"):
        acknowledge(alert_id=officer_alert.id, user=trade.superintendent)
    set_actor(user_id=trade.officer.user_id, role=trade.officer.role)
    acknowledge(alert_id=officer_alert.id, user=trade.officer)
    with pytest.raises(NotAllowed, match="already acknowledged"):
        acknowledge(alert_id=officer_alert.id, user=trade.officer)


def test_alerts_and_acknowledgements_are_append_only_even_for_owner(db, trade, settle):
    settle(buyer="REJECT", reason_code="NOT_ORDERED")
    with acting_as_system("test"):
        alert = AuthorityAlert.objects.first()
        AlertAcknowledgement.objects.create(alert=alert, user_id="x")
    with pytest.raises(DatabaseError, match="append-only"):
        with transaction.atomic():
            AuthorityAlert.objects.update(comment="edited")
    with pytest.raises(DatabaseError, match="append-only"):
        with transaction.atomic():
            AlertAcknowledgement.objects.update(note="edited")


def test_duplicate_acknowledgement_race_is_reported_plainly(app_db, trade, settle, monkeypatch):
    settle(buyer="REJECT", reason_code="NOT_ORDERED")
    [alert] = visible_alerts(trade.officer)
    with acting_as_system("test"):
        AlertAcknowledgement.objects.create(alert=alert, user_id="someone-else")
    monkeypatch.setattr("alerts.service._already_acknowledged", lambda alert: False)
    set_actor(user_id=trade.officer.user_id, role=trade.officer.role)
    with pytest.raises(NotAllowed, match="already acknowledged"):
        acknowledge(alert_id=alert.id, user=trade.officer)
