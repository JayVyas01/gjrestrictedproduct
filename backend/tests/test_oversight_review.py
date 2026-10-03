from datetime import date

import pytest
from django.db import DatabaseError, transaction

from alerts.models import AuthorityAlert
from core.db_context import acting_as_system, set_actor
from identity.models import OtpChallenge
from oversight.models import BatchFlag, BatchSignOff
from oversight.presenters import batch_detail
from oversight.service import (
    NotAllowed,
    batch_status,
    create_due_batches,
    flag_item,
    request_sign_off_code,
    sign_off,
)
from reasons.service import InvalidReason
from tests.conftest import set_decided_on

pytestmark = pytest.mark.django_db


@pytest.fixture
def batch(settle, review_setting):
    tx = settle()
    set_decided_on(tx, date(2026, 6, 10))
    with acting_as_system("test"):
        [made] = create_due_batches(date(2026, 6, 16))
    return made, tx


def as_user(user):
    set_actor(user_id=user.user_id, role=user.role)


def sign(user, batch_id, otp_outbox, code=None):
    as_user(user)
    challenge = request_sign_off_code(batch_id=batch_id, user=user)
    return sign_off(
        batch_id=batch_id,
        user=user,
        challenge_id=str(challenge.public_id),
        code=code or otp_outbox[-1][1],
    )


def test_flag_alerts_the_approving_officer(app_db, org, trade, batch, audit_actions):
    made, tx = batch
    as_user(trade.superintendent)
    flag = flag_item(
        batch_id=made.id,
        reference=tx.reference,
        user=trade.superintendent,
        reason_code="QUANTITY_UNUSUAL",
        comment="Twice the usual volume",
    )
    assert flag.position == org.district_officer and flag.flagged_by == trade.superintendent.user_id
    with acting_as_system("test"):
        alert = AuthorityAlert.objects.get(kind="SUPERINTENDENT_FLAG")
    assert alert.position == org.area_officer and alert.transaction == tx
    assert alert.comment == "Twice the usual volume"
    assert audit_actions()[-1] == "oversight.transaction_flagged"


def test_flag_needs_a_flag_reason(app_db, trade, batch):
    made, tx = batch
    as_user(trade.superintendent)
    with pytest.raises(InvalidReason):
        flag_item(
            batch_id=made.id,
            reference=tx.reference,
            user=trade.superintendent,
            reason_code="NOT_ORDERED",
            comment="",
        )
    with pytest.raises(InvalidReason, match="describe the reason"):
        flag_item(
            batch_id=made.id,
            reference=tx.reference,
            user=trade.superintendent,
            reason_code="OTHER",
            comment=" ",
        )


def test_one_flag_per_transaction(app_db, trade, batch):
    made, tx = batch
    as_user(trade.superintendent)
    flag_item(
        batch_id=made.id,
        reference=tx.reference,
        user=trade.superintendent,
        reason_code="PATTERN_CONCERN",
        comment="",
    )
    with pytest.raises(NotAllowed, match="already flagged"):
        flag_item(
            batch_id=made.id,
            reference=tx.reference,
            user=trade.superintendent,
            reason_code="PATTERN_CONCERN",
            comment="",
        )


def test_only_the_superintendent_can_review(app_db, trade, batch):
    made, tx = batch
    as_user(trade.officer)
    with pytest.raises(NotAllowed, match="Only the superintendent"):
        flag_item(
            batch_id=made.id,
            reference=tx.reference,
            user=trade.officer,
            reason_code="PATTERN_CONCERN",
            comment="",
        )
    with pytest.raises(NotAllowed):
        request_sign_off_code(batch_id=made.id, user=trade.officer)


def test_transaction_must_be_in_the_batch(app_db, trade, batch, settle):
    made, _ = batch
    other = settle()
    as_user(trade.superintendent)
    with pytest.raises(NotAllowed, match="not in this batch"):
        flag_item(
            batch_id=made.id,
            reference=other.reference,
            user=trade.superintendent,
            reason_code="PATTERN_CONCERN",
            comment="",
        )


def test_sign_off_with_code(app_db, trade, batch, otp_outbox, audit_actions):
    made, _ = batch
    signed = sign(trade.superintendent, made.id, otp_outbox)
    assert signed.signed_by == trade.superintendent.user_id and signed.otp_verified_at is not None
    assert batch_status(made, date(2026, 6, 30)) == "SIGNED"
    assert audit_actions()[-1] == "oversight.batch_signed"


def test_wrong_code_does_not_sign(app_db, trade, batch, otp_outbox):
    made, _ = batch
    as_user(trade.superintendent)
    challenge = request_sign_off_code(batch_id=made.id, user=trade.superintendent)
    real = otp_outbox[-1][1]
    wrong = "000000" if real != "000000" else "111111"
    assert (
        sign_off(
            batch_id=made.id,
            user=trade.superintendent,
            challenge_id=str(challenge.public_id),
            code=wrong,
        )
        is None
    )
    assert OtpChallenge.objects.get(pk=challenge.pk).attempts == 1
    with acting_as_system("test"):
        assert BatchSignOff.objects.count() == 0


def test_signed_batch_cannot_be_flagged_or_signed_again(app_db, trade, batch, otp_outbox):
    made, tx = batch
    sign(trade.superintendent, made.id, otp_outbox)
    as_user(trade.superintendent)
    with pytest.raises(NotAllowed, match="already signed off"):
        flag_item(
            batch_id=made.id,
            reference=tx.reference,
            user=trade.superintendent,
            reason_code="PATTERN_CONCERN",
            comment="",
        )
    with pytest.raises(NotAllowed, match="already signed off"):
        request_sign_off_code(batch_id=made.id, user=trade.superintendent)


def test_batch_status_open_then_overdue(app_db, batch):
    made, _ = batch
    assert batch_status(made, date(2026, 7, 15)) == "OPEN"
    assert batch_status(made, date(2026, 7, 16)) == "OVERDUE"


def test_flags_and_sign_offs_are_append_only_even_for_owner(db, trade, batch, otp_outbox):
    made, tx = batch
    as_user(trade.superintendent)
    flag_item(
        batch_id=made.id,
        reference=tx.reference,
        user=trade.superintendent,
        reason_code="PATTERN_CONCERN",
        comment="",
    )
    sign(trade.superintendent, made.id, otp_outbox)
    for model in (BatchFlag, BatchSignOff):
        with pytest.raises(DatabaseError, match="append-only"):
            with transaction.atomic():
                model.objects.update(created_at=None)


@pytest.fixture
def mixed_batch(settle, review_setting, threshold):
    """One officer-only transaction and one the superintendent gave final approval to."""
    officer_only = settle("10")
    two_step = settle("300", officer="RECOMMEND", superintendent="APPROVE")
    for tx in (officer_only, two_step):
        set_decided_on(tx, date(2026, 6, 10))
    with acting_as_system("test"):
        [made] = create_due_batches(date(2026, 6, 16))
    return made, officer_only, two_step


def test_superintendent_approved_items_are_marked(app_db, org, trade, mixed_batch):
    made, officer_only, two_step = mixed_batch
    as_user(trade.superintendent)
    items = {
        i["reference"]: i
        for i in batch_detail(made, date(2026, 6, 20), trade.superintendent)["items"]
    }
    assert items[officer_only.reference]["approved_by_superintendent"] is False
    assert items[officer_only.reference]["approved_by_position"] == org.area_officer.title
    assert items[two_step.reference]["approved_by_superintendent"] is True
    assert items[two_step.reference]["approved_by_position"] == org.district_officer.title


def test_superintendent_cannot_flag_own_approval(app_db, trade, mixed_batch, audit_actions):
    made, _, two_step = mixed_batch
    before = audit_actions()
    as_user(trade.superintendent)
    with pytest.raises(NotAllowed) as refused:
        flag_item(
            batch_id=made.id,
            reference=two_step.reference,
            user=trade.superintendent,
            reason_code="PATTERN_CONCERN",
            comment="",
        )
    assert str(refused.value) == "You approved this transaction; the Head Authority reviews it."
    with acting_as_system("test"):
        assert BatchFlag.objects.count() == 0
        assert AuthorityAlert.objects.filter(kind="SUPERINTENDENT_FLAG").count() == 0
    assert audit_actions() == before


def test_officer_only_flag_still_alerts_officer(app_db, org, trade, mixed_batch):
    made, officer_only, _ = mixed_batch
    as_user(trade.superintendent)
    flag_item(
        batch_id=made.id,
        reference=officer_only.reference,
        user=trade.superintendent,
        reason_code="PATTERN_CONCERN",
        comment="",
    )
    with acting_as_system("test"):
        alert = AuthorityAlert.objects.get(kind="SUPERINTENDENT_FLAG")
    assert alert.position == org.area_officer and alert.transaction == officer_only
