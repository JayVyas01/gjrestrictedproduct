"""Severity routing: above the approval threshold the officer recommends and the district
superintendent gives final approval. Only the final approval moves stock."""

from decimal import Decimal

import pytest

from core import crypto
from core.db_context import acting_as_system
from identity.roles import Role
from licensing.models import LicenceStatus
from licensing.service import set_status
from positions.service import assign
from reasons.service import InvalidReason
from stock.models import StockMovement
from stock.service import balance_of, transfer
from tests.test_transaction_api import NEW_TX, login, post, sign
from tests.test_transaction_decisions import act, as_user, new_tx
from transactions.models import ApprovalChain, TransactionDecision, TransactionStatus
from transactions.service import NotAllowed, TransactionRefused, request_decision_code

pytestmark = pytest.mark.django_db
SAME_PERSON = (
    "You made the officer decision on this transaction; another officer must give final approval."
)


def recommended(trade, catalogue, otp_outbox, qty="250"):
    tx = new_tx(trade, catalogue, qty=qty)
    act(trade.buyer, Role.LICENSEE, tx, otp_outbox, "CONFIRM")
    return act(trade.officer, Role.PERSONNEL, tx, otp_outbox, "RECOMMEND")


def balances(trade, catalogue):
    with acting_as_system("test"):
        return (
            balance_of(trade.seller_licence.gstin_index, catalogue.whisky),
            balance_of(trade.buyer_licence.gstin_index, catalogue.whisky),
        )


def test_start_records_the_chain(app_db, catalogue, trade, threshold):
    assert new_tx(trade, catalogue, qty="150").approval_chain == ApprovalChain.OFFICER
    assert (
        new_tx(trade, catalogue, qty="250").approval_chain
        == ApprovalChain.OFFICER_THEN_SUPERINTENDENT
    )


def test_officer_must_recommend_on_two_step_chain(app_db, catalogue, trade, threshold, otp_outbox):
    tx = new_tx(trade, catalogue, qty="250")
    act(trade.buyer, Role.LICENSEE, tx, otp_outbox, "CONFIRM")
    with pytest.raises(NotAllowed, match="That decision is not available at this step."):
        act(trade.officer, Role.PERSONNEL, tx, otp_outbox, "APPROVE")
    assert (
        act(trade.officer, Role.PERSONNEL, tx, otp_outbox, "RECOMMEND").status
        == TransactionStatus.AWAITING_SUPERINTENDENT
    )


def test_officer_cannot_recommend_on_officer_chain(app_db, catalogue, trade, otp_outbox):
    tx = new_tx(trade, catalogue, qty="150")
    act(trade.buyer, Role.LICENSEE, tx, otp_outbox, "CONFIRM")
    with pytest.raises(NotAllowed, match="That decision is not available at this step."):
        act(trade.officer, Role.PERSONNEL, tx, otp_outbox, "RECOMMEND")


def test_two_step_chain_moves_stock_only_on_final_approval(
    app_db, catalogue, org, trade, threshold, otp_outbox, audit_actions
):
    tx = recommended(trade, catalogue, otp_outbox)
    assert tx.status == TransactionStatus.AWAITING_SUPERINTENDENT and tx.decided_at is None
    assert balances(trade, catalogue) == (Decimal("400"), Decimal("0"))
    with acting_as_system("test"):
        assert not StockMovement.objects.filter(transaction_reference=tx.reference).exists()

    approved = act(trade.superintendent, Role.PERSONNEL, tx, otp_outbox, "APPROVE")
    assert approved.status == TransactionStatus.APPROVED and approved.decided_at is not None
    assert balances(trade, catalogue) == (Decimal("150"), Decimal("250"))
    with acting_as_system("test"):
        decisions = list(
            TransactionDecision.objects.filter(transaction=tx)
            .order_by("id")
            .values_list("step", "outcome", "position", "actor_user_id")
        )
    assert decisions == [
        ("BUYER", "CONFIRM", None, trade.buyer.user_id),
        ("OFFICER", "RECOMMEND", org.area_officer.pk, trade.officer.user_id),
        ("SUPERINTENDENT", "APPROVE", org.district_officer.pk, trade.superintendent.user_id),
    ]
    actions = audit_actions()
    assert actions[-2:] == ["transaction.recommended", "transaction.approved"]


def test_superintendent_rejects_with_reason(
    app_db, catalogue, trade, threshold, otp_outbox, audit_actions
):
    tx = recommended(trade, catalogue, otp_outbox)
    with pytest.raises(InvalidReason):
        act(trade.superintendent, Role.PERSONNEL, tx, otp_outbox, "REJECT", "NOT_ORDERED")
    rejected = act(
        trade.superintendent, Role.PERSONNEL, tx, otp_outbox, "REJECT", "TRANSPORTER_INVALID"
    )
    assert rejected.status == TransactionStatus.REJECTED_BY_SUPERINTENDENT
    assert rejected.decided_at is not None
    assert balances(trade, catalogue) == (Decimal("400"), Decimal("0"))
    assert audit_actions()[-1] == "transaction.superintendent_rejected"


def test_only_current_superintendent_can_decide(
    app_db, catalogue, org, trade, threshold, otp_outbox, make_user
):
    tx = recommended(trade, catalogue, otp_outbox)
    replacement = make_user(role=Role.PERSONNEL, contact="+919800000305")
    assign(org.district_officer, replacement, by="test")
    as_user(trade.superintendent, Role.PERSONNEL)
    with pytest.raises(NotAllowed):
        request_decision_code(reference=tx.reference, user=trade.superintendent)
    assert (
        act(replacement, Role.PERSONNEL, tx, otp_outbox, "APPROVE").status
        == TransactionStatus.APPROVED
    )


def test_officer_cannot_also_give_final_approval(
    app_db, client, catalogue, org, trade, threshold, otp_outbox
):
    assign(org.district_officer, trade.officer, by="test")
    tx = recommended(trade, catalogue, otp_outbox)
    as_user(trade.officer, Role.PERSONNEL)
    issued = len(otp_outbox)
    with pytest.raises(NotAllowed) as refused:
        request_decision_code(reference=tx.reference, user=trade.officer)
    assert str(refused.value) == SAME_PERSON
    assert len(otp_outbox) == issued  # no code is ever issued
    login(client, trade.officer, otp_outbox)
    detail = client.get(f"/api/transactions/{tx.reference}").json()
    assert detail["can_decide"] is False and detail["allowed_outcomes"] == []
    assert post(client, f"/api/transactions/{tx.reference}/decision-code").json() == {
        "detail": SAME_PERSON
    }
    with acting_as_system("test"):
        tx.refresh_from_db()
        assert tx.status == TransactionStatus.AWAITING_SUPERINTENDENT
        assert not TransactionDecision.objects.filter(
            transaction=tx, step="SUPERINTENDENT"
        ).exists()
    assert balances(trade, catalogue) == (Decimal("400"), Decimal("0"))


def test_recommend_rechecks_and_refuses(
    app_db, catalogue, trade, threshold, otp_outbox, audit_actions
):
    tx = new_tx(trade, catalogue, qty="250")
    act(trade.buyer, Role.LICENSEE, tx, otp_outbox, "CONFIRM")
    with acting_as_system("test"):
        set_status(trade.seller_licence, LicenceStatus.SUSPENDED, by="test", reason="test")
    with pytest.raises(TransactionRefused) as refused:
        act(trade.officer, Role.PERSONNEL, tx, otp_outbox, "RECOMMEND")
    assert "You have no valid licence that allows selling Whisky." in refused.value.reasons
    assert audit_actions()[-1] == "transaction.approval_refused"
    with acting_as_system("test"):
        tx.refresh_from_db()
        assert tx.status == TransactionStatus.AWAITING_OFFICER
        assert not TransactionDecision.objects.filter(transaction=tx, step="OFFICER").exists()


def test_final_approval_rechecks_stock(
    app_db, catalogue, trade, threshold, otp_outbox, audit_actions
):
    tx = recommended(trade, catalogue, otp_outbox)
    with acting_as_system("test"):
        transfer(
            from_gstin_index=trade.seller_licence.gstin_index,
            to_gstin_index=crypto.blind_index("gstin", "99DDDDD3333D1Z5"),
            substance=catalogue.whisky,
            quantity=Decimal("200"),
            transaction_reference="ELSEWHERE",
            max_target=Decimal("1000"),
        )
    with pytest.raises(TransactionRefused) as refused:
        act(trade.superintendent, Role.PERSONNEL, tx, otp_outbox, "APPROVE")
    assert "You have 200 L of Whisky in stock, which is less than 250 L." in refused.value.reasons
    assert audit_actions()[-1] == "transaction.approval_refused"
    assert balances(trade, catalogue) == (Decimal("200"), Decimal("0"))
    with acting_as_system("test"):
        tx.refresh_from_db()
        assert tx.status == TransactionStatus.AWAITING_SUPERINTENDENT and tx.decided_at is None
        assert not StockMovement.objects.filter(transaction_reference=tx.reference).exists()


def test_detail_shows_chain_and_allowed_outcomes(
    app_db, client, catalogue, trade, threshold, otp_outbox, make_user
):
    login(client, trade.seller, otp_outbox)
    created = post(client, "/api/transactions", {**NEW_TX, "quantity": "250"}).json()
    ref = created["reference"]
    assert created["approval_chain"] == "OFFICER_THEN_SUPERINTENDENT"
    assert created["approval_chain_label"] == "Officer, then superintendent"
    assert created["allowed_outcomes"] == []
    login(client, trade.buyer, otp_outbox)
    assert client.get(f"/api/transactions/{ref}").json()["allowed_outcomes"] == [
        "CONFIRM",
        "REJECT",
    ]
    sign(client, ref, otp_outbox, "CONFIRM")

    login(client, trade.officer, otp_outbox)
    assert client.get(f"/api/transactions/{ref}").json()["allowed_outcomes"] == [
        "RECOMMEND",
        "REJECT",
    ]
    assert sign(client, ref, otp_outbox, "RECOMMEND").json()["allowed_outcomes"] == []

    login(client, trade.superintendent, otp_outbox)
    assert client.get(f"/api/transactions/{ref}").json()["allowed_outcomes"] == [
        "APPROVE",
        "REJECT",
    ]
    final = sign(client, ref, otp_outbox, "APPROVE").json()
    assert final["status"] == "APPROVED"
    timeline = [(e["step"], e["outcome"], e["by"], e["held_by"]) for e in final["timeline"]]
    assert timeline == [
        ("SELLER", "STARTED", "Seller", None),
        ("BUYER", "CONFIRM", "Buyer", None),
        ("OFFICER", "RECOMMEND", "Area Officer, Sanand", trade.officer.user_id),
        (
            "SUPERINTENDENT",
            "APPROVE",
            "District Officer, Ahmedabad",
            trade.superintendent.user_id,
        ),
    ]

    login(client, trade.seller, otp_outbox)
    seller_view = client.get(f"/api/transactions/{ref}").json()
    assert [e["by"] for e in seller_view["timeline"]][2:] == [
        "Area Officer, Sanand",
        "District Officer, Ahmedabad",
    ]
    assert [e["held_by"] for e in seller_view["timeline"]] == [None, None, None, None]
    assert seller_view["allowed_outcomes"] == []

    head = make_user(role=Role.HEAD_AUTHORITY, contact="+919800000306")
    login(client, head, otp_outbox)
    head_view = client.get(f"/api/transactions/{ref}").json()
    assert [e["held_by"] for e in head_view["timeline"]][2:] == [
        trade.officer.user_id,
        trade.superintendent.user_id,
    ]


def test_superintendent_sees_final_approval_next_action(
    app_db, client, catalogue, trade, threshold, otp_outbox
):
    tx = recommended(trade, catalogue, otp_outbox)
    login(client, trade.superintendent, otp_outbox)
    detail = client.get(f"/api/transactions/{tx.reference}").json()
    assert detail["status"] == "AWAITING_SUPERINTENDENT"
    assert detail["your_role"] == "superintendent"
    assert detail["next_action"] == "Your decision is needed."
    assert detail["can_decide"] is True
    login(client, trade.officer, otp_outbox)
    officer_view = client.get(f"/api/transactions/{tx.reference}").json()
    assert officer_view["next_action"] == "Waiting for the superintendent's final approval."
    assert officer_view["can_decide"] is False


def test_settle_drives_the_two_step_chain(app_db, catalogue, trade, threshold, settle):
    tx = settle("250", officer="RECOMMEND", superintendent="APPROVE")
    assert tx.status == TransactionStatus.APPROVED
