from decimal import Decimal

import pytest

from core.db_context import acting_as_system, set_actor
from identity import otp
from identity.models import OtpPurpose
from identity.roles import Role
from positions.service import assign
from reasons.service import InvalidReason
from stock.service import balance_of
from tests.conftest import BUYER_GSTIN
from transactions.models import TransactionDecision, TransactionStatus
from transactions.service import (
    NotAllowed,
    TransactionRefused,
    Transport,
    decide,
    request_decision_code,
    start_transaction,
)

pytestmark = pytest.mark.django_db
TRANSPORT = Transport(
    name="Ravi Transport Co",
    id_number="GJ-TR-4411",
    vehicle_number="GJ01AB1234",
    route="Sanand to Bopal",
)


def as_user(user, role):
    set_actor(user_id=user.user_id, role=role)


def new_tx(trade, catalogue, qty="150"):
    as_user(trade.seller, Role.LICENSEE)
    return start_transaction(
        seller=trade.seller,
        buyer_gstin=BUYER_GSTIN,
        substance=catalogue.whisky,
        quantity=Decimal(qty),
        transport=TRANSPORT,
    )


def act(user, role, tx, otp_outbox, outcome, reason_code="", comment="", code=None):
    as_user(user, role)
    challenge = request_decision_code(reference=tx.reference, user=user)
    return decide(
        reference=tx.reference,
        user=user,
        challenge_id=str(challenge.public_id),
        code=code or otp_outbox[-1][1],
        outcome=outcome,
        reason_code=reason_code,
        comment=comment,
    )


def test_happy_path_moves_stock_on_approval(app_db, catalogue, trade, otp_outbox, audit_actions):
    tx = new_tx(trade, catalogue)
    assert (
        act(trade.buyer, Role.LICENSEE, tx, otp_outbox, "CONFIRM").status
        == TransactionStatus.AWAITING_OFFICER
    )
    approved = act(trade.officer, Role.PERSONNEL, tx, otp_outbox, "APPROVE")
    assert approved.status == TransactionStatus.APPROVED and approved.decided_at is not None
    with acting_as_system("test"):
        assert balance_of(trade.seller_licence.gstin_index, catalogue.whisky) == Decimal("250")
        assert balance_of(trade.buyer_licence.gstin_index, catalogue.whisky) == Decimal("150")
        steps = list(
            TransactionDecision.objects.filter(transaction=tx).values_list("step", "outcome")
        )
    assert steps == [("BUYER", "CONFIRM"), ("OFFICER", "APPROVE")]
    assert audit_actions()[-2:] == ["transaction.buyer_confirmed", "transaction.approved"]


def test_decision_records_position_and_holder(app_db, catalogue, org, trade, otp_outbox):
    tx = new_tx(trade, catalogue)
    act(trade.buyer, Role.LICENSEE, tx, otp_outbox, "CONFIRM")
    act(trade.officer, Role.PERSONNEL, tx, otp_outbox, "APPROVE")
    with acting_as_system("test"):
        officer_decision = TransactionDecision.objects.get(transaction=tx, step="OFFICER")
    assert officer_decision.position == org.area_officer
    assert officer_decision.actor_user_id == trade.officer.user_id
    assert officer_decision.otp_verified_at is not None


def test_buyer_reject_needs_a_buyer_reason(app_db, catalogue, trade, otp_outbox):
    tx = new_tx(trade, catalogue)
    as_user(trade.buyer, Role.LICENSEE)
    with pytest.raises(InvalidReason):
        decide(
            reference=tx.reference,
            user=trade.buyer,
            challenge_id="00000000-0000-0000-0000-000000000000",
            code="123456",
            outcome="REJECT",
            reason_code="TRANSPORTER_INVALID",
        )
    rejected = act(trade.buyer, Role.LICENSEE, tx, otp_outbox, "REJECT", reason_code="NOT_ORDERED")
    assert rejected.status == TransactionStatus.REJECTED_BY_BUYER


def test_officer_reject_other_needs_text(app_db, catalogue, trade, otp_outbox):
    tx = new_tx(trade, catalogue)
    act(trade.buyer, Role.LICENSEE, tx, otp_outbox, "CONFIRM")
    with pytest.raises(InvalidReason, match="describe the reason"):
        act(trade.officer, Role.PERSONNEL, tx, otp_outbox, "REJECT", reason_code="OTHER")
    rejected = act(
        trade.officer,
        Role.PERSONNEL,
        tx,
        otp_outbox,
        "REJECT",
        reason_code="OTHER",
        comment="Seal broken",
    )
    assert rejected.status == TransactionStatus.REJECTED_BY_OFFICER
    with acting_as_system("test"):
        assert balance_of(trade.seller_licence.gstin_index, catalogue.whisky) == Decimal("400")


def test_wrong_code_records_no_decision_but_counts_attempt(app_db, catalogue, trade, otp_outbox):
    tx = new_tx(trade, catalogue)
    as_user(trade.buyer, Role.LICENSEE)
    challenge = request_decision_code(reference=tx.reference, user=trade.buyer)
    real = otp_outbox[-1][1]
    wrong = "000000" if real != "000000" else "111111"
    assert (
        decide(
            reference=tx.reference,
            user=trade.buyer,
            challenge_id=str(challenge.public_id),
            code=wrong,
            outcome="CONFIRM",
        )
        is None
    )
    challenge.refresh_from_db()
    assert challenge.attempts == 1
    with acting_as_system("test"):
        assert TransactionDecision.objects.filter(transaction=tx).count() == 0


def test_only_the_right_party_can_decide_at_each_step(app_db, catalogue, trade, otp_outbox):
    tx = new_tx(trade, catalogue)
    as_user(trade.officer, Role.PERSONNEL)
    with pytest.raises(NotAllowed):
        request_decision_code(reference=tx.reference, user=trade.officer)  # buyer's turn
    as_user(trade.seller, Role.LICENSEE)
    with pytest.raises(NotAllowed):
        request_decision_code(reference=tx.reference, user=trade.seller)
    act(trade.buyer, Role.LICENSEE, tx, otp_outbox, "CONFIRM")
    as_user(trade.buyer, Role.LICENSEE)
    with pytest.raises(NotAllowed):
        request_decision_code(reference=tx.reference, user=trade.buyer)  # officer's turn


def test_buyer_cannot_approve_and_officer_cannot_confirm(app_db, catalogue, trade, otp_outbox):
    tx = new_tx(trade, catalogue)
    with pytest.raises(NotAllowed):
        act(trade.buyer, Role.LICENSEE, tx, otp_outbox, "APPROVE")
    act(trade.buyer, Role.LICENSEE, tx, otp_outbox, "CONFIRM")
    with pytest.raises(NotAllowed):
        act(trade.officer, Role.PERSONNEL, tx, otp_outbox, "CONFIRM")


def test_transferred_officer_cannot_decide(app_db, catalogue, org, trade, otp_outbox, make_user):
    tx = new_tx(trade, catalogue)
    act(trade.buyer, Role.LICENSEE, tx, otp_outbox, "CONFIRM")
    replacement = make_user(role=Role.PERSONNEL, contact="+919800000303")
    assign(org.area_officer, replacement, by="test")
    as_user(trade.officer, Role.PERSONNEL)
    with pytest.raises(NotAllowed):
        request_decision_code(reference=tx.reference, user=trade.officer)
    assert (
        act(replacement, Role.PERSONNEL, tx, otp_outbox, "APPROVE").status
        == TransactionStatus.APPROVED
    )


def test_approval_rechecks_stock(app_db, catalogue, trade, otp_outbox, make_licence, make_licensee):
    first = new_tx(trade, catalogue, qty="300")
    second = new_tx(trade, catalogue, qty="300")
    for tx in (first, second):
        act(trade.buyer, Role.LICENSEE, tx, otp_outbox, "CONFIRM")
    act(trade.officer, Role.PERSONNEL, first, otp_outbox, "APPROVE")
    with pytest.raises(TransactionRefused) as refused:
        act(trade.officer, Role.PERSONNEL, second, otp_outbox, "APPROVE")
    assert "You have 100 L of Whisky in stock, which is less than 300 L." in refused.value.reasons
    with acting_as_system("test"):
        second.refresh_from_db()
        assert second.status == TransactionStatus.AWAITING_OFFICER
        assert balance_of(trade.seller_licence.gstin_index, catalogue.whisky) == Decimal("100")


def test_decision_code_is_bound_to_the_user(app_db, catalogue, trade, otp_outbox, make_user):
    tx = new_tx(trade, catalogue)
    act(trade.buyer, Role.LICENSEE, tx, otp_outbox, "CONFIRM")
    someone_else = make_user(role=Role.PERSONNEL, contact="+919800000304")
    foreign = otp.issue(someone_else, OtpPurpose.DECISION)  # a valid code, but not the officer's
    as_user(trade.officer, Role.PERSONNEL)
    with pytest.raises(NotAllowed, match="belongs to someone else"):
        decide(
            reference=tx.reference,
            user=trade.officer,
            challenge_id=str(foreign.public_id),
            code=otp_outbox[-1][1],
            outcome="APPROVE",
        )
