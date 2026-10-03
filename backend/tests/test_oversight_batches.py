from datetime import date

import pytest
from django.core.management import call_command
from django.db import DatabaseError, transaction

from core.db_context import acting_as_system, set_actor
from identity.roles import Role
from oversight.models import BatchItem, OversightBatch
from oversight.service import InvalidSetting, create_due_batches, set_review_period
from tests.conftest import set_decided_on

pytestmark = pytest.mark.django_db


def run(today):
    with acting_as_system("test"):
        return create_due_batches(today)


def test_review_period_must_be_15_30_or_60_days(app_db, org):
    with acting_as_system("test"):
        with pytest.raises(InvalidSetting, match="15, 30 or 60"):
            set_review_period(position=org.district_officer, days=20, by="test")


def test_review_period_only_for_district_positions(app_db, org):
    with acting_as_system("test"):
        with pytest.raises(InvalidSetting, match="district"):
            set_review_period(position=org.area_officer, days=15, by="test")


def test_batch_holds_approved_transactions_of_the_period(app_db, org, settle, review_setting):
    inside = settle()
    set_decided_on(inside, date(2026, 6, 10))
    outside = settle()
    set_decided_on(outside, date(2026, 6, 20))
    rejected = settle(officer="REJECT", reason_code="QUANTITY_MISMATCH")
    set_decided_on(rejected, date(2026, 6, 10))
    [batch] = run(date(2026, 6, 16))
    assert (batch.period_start, batch.period_end) == (date(2026, 6, 1), date(2026, 6, 15))
    assert batch.position == org.district_officer
    assert batch.due_on() == date(2026, 7, 15)
    with acting_as_system("test"):
        assert [i.transaction_id for i in BatchItem.objects.filter(batch=batch)] == [inside.id]


def test_no_batch_for_the_period_still_running(app_db, settle, review_setting):
    assert run(date(2026, 6, 15)) == []


def test_batches_are_created_once_per_completed_period(
    app_db, settle, review_setting, audit_actions
):
    created = run(date(2026, 7, 20))
    assert [(b.period_start, b.period_end) for b in created] == [
        (date(2026, 6, 1), date(2026, 6, 15)),
        (date(2026, 6, 16), date(2026, 6, 30)),
        (date(2026, 7, 1), date(2026, 7, 15)),
    ]
    assert run(date(2026, 7, 20)) == []
    assert audit_actions().count("oversight.batch_created") == 3


def test_empty_period_still_gets_a_batch(app_db, review_setting):
    [batch] = run(date(2026, 6, 16))
    with acting_as_system("test"):
        assert BatchItem.objects.filter(batch=batch).count() == 0


def test_changing_the_period_continues_after_the_last_batch(app_db, org, review_setting):
    run(date(2026, 6, 16))
    with acting_as_system("test"):
        setting = set_review_period(position=org.district_officer, days=30, by="test")
    assert setting.starts_on == date(2026, 6, 16)
    [batch] = run(date(2026, 7, 16))
    assert (batch.period_start, batch.period_end) == (date(2026, 6, 16), date(2026, 7, 15))


def test_only_the_superintendent_and_authorities_see_batches(
    app_db, trade, settle, review_setting, make_user
):
    run(date(2026, 6, 16))
    head = make_user(role=Role.HEAD_AUTHORITY)

    def count(user):
        with transaction.atomic():
            set_actor(user_id=user.user_id, role=user.role)
            return OversightBatch.objects.count()

    assert count(trade.superintendent) == 1
    assert count(head) == 1
    assert count(trade.officer) == count(trade.seller) == 0


def test_batches_are_append_only_even_for_owner(db, review_setting):
    run(date(2026, 6, 16))
    with pytest.raises(DatabaseError, match="append-only"):
        with transaction.atomic():
            OversightBatch.objects.update(period_end=date(2030, 1, 1))


def test_command_creates_due_batches(app_db, review_setting, capsys):
    call_command("create_due_batches", "--today", "2026-06-16")
    assert "Created 1 batch" in capsys.readouterr().out


def test_changing_the_period_before_any_batch_keeps_the_start(
    app_db, org, review_setting, monkeypatch
):
    monkeypatch.setattr("oversight.service.timezone.localdate", lambda: date(2026, 6, 10))
    with acting_as_system("test"):
        setting = set_review_period(position=org.district_officer, days=30, by="test")
    assert setting.starts_on == date(2026, 6, 1)
    [batch] = run(date(2026, 7, 2))
    assert (batch.period_start, batch.period_end) == (date(2026, 6, 1), date(2026, 6, 30))


def test_review_period_set_by_licensing_authority_sees_existing_batches(
    app_db, org, review_setting, make_user
):
    run(date(2026, 6, 16))
    la = make_user(role=Role.LICENSING_AUTHORITY)
    with transaction.atomic():
        set_actor(user_id=la.user_id, role=la.role)
        setting = set_review_period(position=org.district_officer, days=30, by="la")
    assert setting.starts_on == date(2026, 6, 16)


def test_review_period_cannot_skip_days(app_db, org, review_setting):
    with acting_as_system("test"):
        with pytest.raises(InvalidSetting, match="cannot start after 2026-06-01"):
            set_review_period(
                position=org.district_officer, days=30, by="test", starts_on=date(2026, 6, 5)
            )
    run(date(2026, 6, 16))
    with acting_as_system("test"):
        with pytest.raises(InvalidSetting, match="must start on 2026-06-16"):
            set_review_period(
                position=org.district_officer, days=30, by="test", starts_on=date(2026, 6, 20)
            )
        with pytest.raises(InvalidSetting, match="must start on 2026-06-16"):
            set_review_period(
                position=org.district_officer, days=30, by="test", starts_on=date(2026, 6, 10)
            )
