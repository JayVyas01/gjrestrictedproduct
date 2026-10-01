from decimal import Decimal

import pytest
from django.db import transaction as db_transaction

from core.db_context import acting_as_system, set_actor
from identity.roles import Role
from tests.conftest import BUYER_GSTIN, DEMO_GSTIN
from transactions.models import Transaction, TransactionStatus
from transactions.service import (
    NotAllowed,
    TransactionRefused,
    Transport,
    cancel_transaction,
    find_buyer,
    start_transaction,
)

pytestmark = pytest.mark.django_db
TRANSPORT = Transport(
    name="Ravi Transport Co",
    id_number="GJ-TR-4411",
    vehicle_number="GJ01AB1234",
    route="Sanand to Bopal via SG Highway",
)


def as_user(user, role):
    set_actor(user_id=user.user_id, role=role)


def start(trade, catalogue, qty="150", gstin=BUYER_GSTIN):
    as_user(trade.seller, Role.LICENSEE)
    return start_transaction(
        seller=trade.seller,
        buyer_gstin=gstin,
        substance=catalogue.whisky,
        quantity=Decimal(qty),
        transport=TRANSPORT,
    )


def test_find_buyer_returns_registered_name_only(app_db, trade, audit_actions):
    as_user(trade.seller, Role.LICENSEE)
    assert find_buyer(gstin=" 99bbbbb1111b1z5 ", by=trade.seller) == "Bopal Bar & Kitchen"
    assert find_buyer(gstin="99ZZZZZ9999Z1Z5", by=trade.seller) is None
    assert find_buyer(gstin="not-a-gstin", by=trade.seller) is None
    assert audit_actions()[-2:] == ["transaction.buyer_lookup", "transaction.buyer_lookup"]


def test_buyer_lookup_audit_holds_no_gstin(app_db, trade):
    from audit.models import AuditEvent
    from core.db_context import SYSTEM_ROLE

    as_user(trade.seller, Role.LICENSEE)
    find_buyer(gstin=BUYER_GSTIN, by=trade.seller)
    with db_transaction.atomic():
        set_actor(user_id="test", role=SYSTEM_ROLE)
        payloads = [str(p) for p in AuditEvent.objects.values_list("payload", flat=True)]
    assert not any(BUYER_GSTIN in p for p in payloads)


def test_start_creates_transaction_routed_to_seller_area_officer(
    app_db, catalogue, org, trade, audit_actions
):
    tx = start(trade, catalogue)
    assert tx.status == TransactionStatus.AWAITING_BUYER
    assert tx.designated_position == org.area_officer
    assert tx.superintendent_position == org.district_officer
    assert tx.seller_licence == trade.seller_licence and tx.buyer_licence == trade.buyer_licence
    assert tx.unit == "L" and tx.vehicle_number() == "GJ01AB1234"
    assert audit_actions()[-1] == "transaction.started"


def test_transporter_identifiers_are_encrypted(app_db, catalogue, trade):
    tx = start(trade, catalogue)
    assert "GJ01AB1234" not in tx.vehicle_number_encrypted
    assert "GJ-TR-4411" not in tx.transporter_id_encrypted


def test_over_limit_is_refused_with_plain_reasons(app_db, catalogue, trade):
    with pytest.raises(TransactionRefused) as refused:
        start(trade, catalogue, qty="600")
    assert (
        "Quantity 600 L exceeds your licence's per-transaction limit of 500 L."
        in refused.value.reasons
    )
    with acting_as_system("test"):
        assert Transaction.objects.count() == 0


def test_unknown_buyer_is_refused(app_db, catalogue, trade):
    with pytest.raises(TransactionRefused) as refused:
        start(trade, catalogue, gstin="99ZZZZZ9999Z1Z5")
    assert refused.value.reasons == ["This buyer has no valid licence that allows buying Whisky."]


def test_cannot_sell_to_own_business(app_db, catalogue, trade):
    with pytest.raises(TransactionRefused) as refused:
        start(trade, catalogue, gstin=DEMO_GSTIN)
    assert refused.value.reasons == ["You cannot sell to your own business."]


def test_area_without_officer_position_is_refused(app_db, catalogue, org, trade):
    from positions.models import Position

    with acting_as_system("test"):
        Position.objects.filter(pk=org.area_officer.pk).update(
            area=org.state
        )  # detach Sanand's post
    with pytest.raises(TransactionRefused) as refused:
        start(trade, catalogue)
    assert refused.value.reasons == [
        "No officer is responsible for your area yet. Please contact the Licensing Authority."
    ]


def test_district_without_superintendent_is_refused(app_db, catalogue, org, trade):
    from positions.models import Position

    with acting_as_system("test"):
        Position.objects.filter(pk=org.district_officer.pk).update(
            area=org.state
        )  # detach Ahmedabad's post
    with pytest.raises(TransactionRefused) as refused:
        start(trade, catalogue)
    assert refused.value.reasons == [
        "No superintendent is responsible for your district yet. "
        "Please contact the Licensing Authority."
    ]


def test_seller_can_cancel_only_while_awaiting_buyer(app_db, catalogue, trade, audit_actions):
    tx = start(trade, catalogue)
    cancelled = cancel_transaction(reference=tx.reference, seller=trade.seller)
    assert cancelled.status == TransactionStatus.CANCELLED
    assert audit_actions()[-1] == "transaction.cancelled"
    with pytest.raises(NotAllowed):
        cancel_transaction(reference=tx.reference, seller=trade.seller)


def test_buyer_cannot_cancel(app_db, catalogue, trade):
    tx = start(trade, catalogue)
    as_user(trade.buyer, Role.LICENSEE)
    with pytest.raises(NotAllowed):
        cancel_transaction(reference=tx.reference, seller=trade.buyer)
