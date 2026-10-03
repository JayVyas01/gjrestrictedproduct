"""The buyer's stock limit is the buyer's decision: the seller is never refused because of it
and never sees the buyer's stock numbers. The buyer can only reject; that rejection raises no
alert and is not counted in the seller's rejection pattern."""

import json
from decimal import Decimal

import pytest
from django.db import transaction

from alerts.models import AuthorityAlert
from audit.models import AuditEvent
from core.db_context import SYSTEM_ROLE, acting_as_system, set_actor
from identity.roles import Role
from reasons.models import ReasonCode, ReasonKind
from reasons.service import InvalidReason
from stock.service import set_opening_balance
from tests.test_transaction_api import NEW_TX, login, post, sign
from tests.test_transaction_decisions import act, as_user, new_tx
from transactions.models import TransactionDecision, TransactionStatus
from transactions.service import TransactionRefused, decide, request_decision_code

pytestmark = pytest.mark.django_db
PROBLEM = (
    "Confirming would take your Whisky stock to 1005 L, above your licence limit of 1000 L. "
    "You can only reject this sale."
)
CAP_MESSAGE = (
    "This sale would take the buyer's stock of Whisky to 1005 L, above their licence limit of "
    "1000 L."
)
NO_PROBLEM = "Your stock limit allows this sale, so choose another reason."
STOCK_LIMIT_LABEL = "This would take me over my licence's stock limit"


def buyer_holds(trade, catalogue, qty="995"):
    """Retail/Spirits allows 1000 L, so a 10 L sale takes the buyer over the limit."""
    with acting_as_system("test"):
        set_opening_balance(
            gstin_index=trade.buyer_licence.gstin_index,
            substance=catalogue.whisky,
            quantity=Decimal(qty),
            by="test",
        )


def last_payload():
    with transaction.atomic():
        set_actor(user_id="test", role=SYSTEM_ROLE)
        return AuditEvent.objects.order_by("-id").values_list("payload", flat=True).first()


def shows_buyer_stock(body) -> bool:
    """Any of the buyer's stock numbers in what the viewer reads (timestamps left out)."""
    events = [{k: v for k, v in e.items() if k != "at"} for e in body["timeline"]]
    text = json.dumps(events) + (body["next_action"] or "") + json.dumps(body.get("reasons"))
    return any(number in text for number in ("995", "1005", "1000"))


def test_start_is_not_refused_for_buyer_stock(app_db, catalogue, trade):
    buyer_holds(trade, catalogue)
    tx = new_tx(trade, catalogue, qty="10")
    assert tx.status == TransactionStatus.AWAITING_BUYER


def test_seller_never_sees_buyer_stock(app_db, client, catalogue, trade, otp_outbox):
    buyer_holds(trade, catalogue)
    login(client, trade.seller, otp_outbox)
    created = post(client, "/api/transactions", {**NEW_TX, "quantity": "10"})
    assert created.status_code == 201
    ref = created.json()["reference"]
    detail = client.get(f"/api/transactions/{ref}").json()
    for body in (created.json(), detail):
        assert body["stock_limit_problem"] is None
        assert not shows_buyer_stock(body)

    login(client, trade.buyer, otp_outbox)
    assert sign(client, ref, otp_outbox, "REJECT").status_code == 200

    login(client, trade.seller, otp_outbox)
    detail = client.get(f"/api/transactions/{ref}").json()
    assert detail["stock_limit_problem"] is None
    rejection = detail["timeline"][-1]
    assert rejection["reason"] == STOCK_LIMIT_LABEL and rejection["comment"] is None
    assert not shows_buyer_stock(detail)


def test_buyer_sees_problem_and_only_reject(app_db, client, catalogue, trade, otp_outbox):
    buyer_holds(trade, catalogue)
    login(client, trade.seller, otp_outbox)
    ref = post(client, "/api/transactions", {**NEW_TX, "quantity": "10"}).json()["reference"]
    login(client, trade.buyer, otp_outbox)
    detail = client.get(f"/api/transactions/{ref}").json()
    assert detail["stock_limit_problem"] == PROBLEM
    assert detail["allowed_outcomes"] == ["REJECT"]


def test_buyer_without_problem_may_confirm_or_reject(app_db, client, catalogue, trade, otp_outbox):
    login(client, trade.seller, otp_outbox)
    ref = post(client, "/api/transactions", {**NEW_TX, "quantity": "10"}).json()["reference"]
    login(client, trade.buyer, otp_outbox)
    detail = client.get(f"/api/transactions/{ref}").json()
    assert detail["stock_limit_problem"] is None
    assert detail["allowed_outcomes"] == ["CONFIRM", "REJECT"]


def test_buyer_confirm_is_refused_with_422(
    app_db, client, catalogue, trade, otp_outbox, audit_actions
):
    buyer_holds(trade, catalogue)
    login(client, trade.seller, otp_outbox)
    ref = post(client, "/api/transactions", {**NEW_TX, "quantity": "10"}).json()["reference"]
    login(client, trade.buyer, otp_outbox)
    response = sign(client, ref, otp_outbox, "CONFIRM")
    assert response.status_code == 422
    assert response.json()["reasons"] == [PROBLEM]
    assert audit_actions()[-1] == "transaction.confirm_refused"
    detail = client.get(f"/api/transactions/{ref}").json()
    assert detail["status"] == TransactionStatus.AWAITING_BUYER
    assert [e["outcome"] for e in detail["timeline"]] == ["STARTED"]


def test_blank_reason_defaults_to_stock_limit(app_db, catalogue, trade, otp_outbox):
    buyer_holds(trade, catalogue)
    tx = new_tx(trade, catalogue, qty="10")
    rejected = act(trade.buyer, Role.LICENSEE, tx, otp_outbox, "REJECT")
    assert rejected.status == TransactionStatus.REJECTED_BY_BUYER
    with acting_as_system("test"):
        decision = TransactionDecision.objects.get(transaction=tx, step="BUYER")
        assert decision.reason.code == "STOCK_LIMIT"


def test_blank_reason_without_problem_still_needs_a_reason(app_db, catalogue, trade, otp_outbox):
    tx = new_tx(trade, catalogue, qty="10")
    with pytest.raises(InvalidReason, match="Choose a reason"):
        act(trade.buyer, Role.LICENSEE, tx, otp_outbox, "REJECT")


def test_stock_limit_reason_refused_when_no_problem(
    app_db, catalogue, trade, otp_outbox, audit_actions
):
    tx = new_tx(trade, catalogue, qty="10")
    as_user(trade.buyer, Role.LICENSEE)
    challenge = str(request_decision_code(reference=tx.reference, user=trade.buyer).public_id)
    code = otp_outbox[-1][1]
    with pytest.raises(InvalidReason) as refused:
        decide(
            reference=tx.reference,
            user=trade.buyer,
            challenge_id=challenge,
            code=code,
            outcome="REJECT",
            reason_code="STOCK_LIMIT",
        )
    assert str(refused.value) == NO_PROBLEM
    rejected = decide(
        reference=tx.reference,
        user=trade.buyer,
        challenge_id=challenge,
        code=code,
        outcome="REJECT",
        reason_code="NOT_ORDERED",
    )
    assert rejected.status == TransactionStatus.REJECTED_BY_BUYER


def test_stock_limit_rejection_raises_no_alert_and_is_not_counted(
    app_db, catalogue, trade, settle, audit_actions
):
    buyer_holds(trade, catalogue)
    first = settle(buyer="REJECT", reason_code="STOCK_LIMIT")
    assert audit_actions()[-1] == "transaction.buyer_rejected"
    assert last_payload() == {"alerts_raised": 0}
    with acting_as_system("test"):
        assert not AuthorityAlert.objects.filter(transaction=first).exists()
    later = settle(buyer="REJECT", reason_code="NOT_ORDERED")
    with acting_as_system("test"):
        counts = set(
            AuthorityAlert.objects.filter(transaction=later).values_list("pattern_count", flat=True)
        )
    assert counts == {1}


def test_officer_approval_still_checks_buyer_cap(
    app_db, catalogue, trade, otp_outbox, audit_actions
):
    tx = new_tx(trade, catalogue, qty="10")
    act(trade.buyer, Role.LICENSEE, tx, otp_outbox, "CONFIRM")
    buyer_holds(trade, catalogue)
    with pytest.raises(TransactionRefused) as refused:
        act(trade.officer, Role.PERSONNEL, tx, otp_outbox, "APPROVE")
    assert refused.value.reasons == [CAP_MESSAGE]
    assert audit_actions()[-1] == "transaction.approval_refused"
    with acting_as_system("test"):
        tx.refresh_from_db()
        assert tx.status == TransactionStatus.AWAITING_OFFICER


def test_officer_recommend_checks_buyer_cap(app_db, catalogue, trade, threshold, otp_outbox):
    tx = new_tx(trade, catalogue, qty="250")
    act(trade.buyer, Role.LICENSEE, tx, otp_outbox, "CONFIRM")
    buyer_holds(trade, catalogue, qty="800")
    with pytest.raises(TransactionRefused) as refused:
        act(trade.officer, Role.PERSONNEL, tx, otp_outbox, "RECOMMEND")
    assert refused.value.reasons == [
        "This sale would take the buyer's stock of Whisky to 1050 L, above their licence limit "
        "of 1000 L."
    ]


def test_stock_limit_reason_is_seeded(app_db):
    reason = ReasonCode.objects.get(kind=ReasonKind.BUYER_REJECTION, code="STOCK_LIMIT")
    assert reason.label == STOCK_LIMIT_LABEL
    assert reason.sort_order == 50 and reason.active and not reason.requires_text
