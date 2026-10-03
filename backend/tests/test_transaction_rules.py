from datetime import date
from decimal import Decimal

import pytest
from django.db import DatabaseError, transaction

from catalogue.models import LicenceTypeRule
from catalogue.service import add_rule_version
from core.db_context import acting_as_system, set_actor
from identity.roles import Role
from licensing.models import LicenceStatus
from licensing.service import set_status
from stock.service import set_opening_balance
from tests.conftest import BUYER_GSTIN, _permissions
from transactions.checks import eligibility_problems, fmt_qty, transaction_problems
from transactions.models import Transaction, TransactionDecision, generate_reference
from transactions.selection import select_licence

pytestmark = pytest.mark.django_db
TODAY = date(2026, 6, 1)


def test_fmt_qty_drops_trailing_zeros():
    assert fmt_qty(Decimal("600.000")) == "600"
    assert fmt_qty(Decimal("12.500")) == "12.5"


def test_reference_format():
    ref = generate_reference()
    assert ref.startswith("TX") and len(ref) == 12


def test_selects_licence_that_allows_the_action(app_db, catalogue, trade):
    with acting_as_system("test"):
        assert (
            select_licence(trade.seller_licence.gstin_index, catalogue.whisky, "sell", TODAY)
            == trade.seller_licence
        )
        assert (
            select_licence(trade.buyer_licence.gstin_index, catalogue.whisky, "buy", TODAY)
            == trade.buyer_licence
        )


def test_substance_scoped_licence_is_preferred(app_db, catalogue, make_licence):
    class_licence = make_licence(gstin=BUYER_GSTIN)
    whisky_licence = make_licence(gstin=BUYER_GSTIN, substance=catalogue.whisky)
    assert class_licence.id < whisky_licence.id
    with acting_as_system("test"):
        assert (
            select_licence(whisky_licence.gstin_index, catalogue.whisky, "buy", TODAY)
            == whisky_licence
        )


def test_expired_or_suspended_licence_is_not_selected(app_db, catalogue, trade):
    with acting_as_system("test"):
        assert (
            select_licence(
                trade.seller_licence.gstin_index, catalogue.whisky, "sell", date(2048, 1, 1)
            )
            is None
        )
        set_status(trade.seller_licence, LicenceStatus.SUSPENDED, by="test", reason="inspection")
        assert (
            select_licence(trade.seller_licence.gstin_index, catalogue.whisky, "sell", TODAY)
            is None
        )


def test_substance_override_can_forbid_selling(app_db, catalogue, make_licence):
    rum_rule = LicenceTypeRule.objects.create(
        licence_type=catalogue.retail, substance=catalogue.rum
    )
    add_rule_version(rum_rule, created_by="test", **_permissions(may_sell=False))
    licence = make_licence()
    with acting_as_system("test"):
        assert select_licence(licence.gstin_index, catalogue.rum, "sell", TODAY) is None
        assert select_licence(licence.gstin_index, catalogue.whisky, "sell", TODAY) == licence


def test_eligibility_problems_are_plain(app_db, catalogue):
    assert eligibility_problems(None, None, catalogue.whisky) == [
        "You have no valid licence that allows selling Whisky.",
        "This buyer has no valid licence that allows buying Whisky.",
    ]


def test_per_transaction_limit_message(app_db, catalogue, trade):
    with acting_as_system("test"):
        problems = transaction_problems(
            seller_licence=trade.seller_licence,
            buyer_licence=trade.buyer_licence,
            substance=catalogue.whisky,
            quantity=Decimal("600"),
        )
    assert "Quantity 600 L exceeds your licence's per-transaction limit of 500 L." in problems
    assert (
        "Quantity 600 L exceeds the buyer's licence's per-transaction limit of 500 L." in problems
    )


def test_stock_and_buyer_capacity_messages(app_db, catalogue, trade):
    with acting_as_system("test"):
        problems = transaction_problems(
            seller_licence=trade.seller_licence,
            buyer_licence=trade.buyer_licence,
            substance=catalogue.whisky,
            quantity=Decimal("450"),
        )
    assert "You have 400 L of Whisky in stock, which is less than 450 L." in problems


def test_buyer_stock_limit_message(app_db, catalogue, trade):
    with acting_as_system("test"):
        set_opening_balance(
            gstin_index=trade.buyer_licence.gstin_index,
            substance=catalogue.whisky,
            quantity=Decimal("900"),
            by="test",
        )
        problems = transaction_problems(
            seller_licence=trade.seller_licence,
            buyer_licence=trade.buyer_licence,
            substance=catalogue.whisky,
            quantity=Decimal("200"),
        )
    assert problems == [
        "This sale would take the buyer's stock of Whisky to 1100 L, "
        "above their licence limit of 1000 L."
    ]


def test_valid_transaction_has_no_problems(app_db, catalogue, trade):
    with acting_as_system("test"):
        assert (
            transaction_problems(
                seller_licence=trade.seller_licence,
                buyer_licence=trade.buyer_licence,
                substance=catalogue.whisky,
                quantity=Decimal("150"),
            )
            == []
        )


def make_raw_transaction(trade, catalogue, org):
    with acting_as_system("test"):
        return Transaction.objects.create(
            reference=generate_reference(),
            seller_licence=trade.seller_licence,
            buyer_licence=trade.buyer_licence,
            seller_gstin_index=trade.seller_licence.gstin_index,
            buyer_gstin_index=trade.buyer_licence.gstin_index,
            substance=catalogue.whisky,
            quantity=Decimal("10"),
            unit="L",
            transporter_name_encrypted="x",
            transporter_id_encrypted="x",
            vehicle_number_encrypted="x",
            route="Sanand to Bopal",
            designated_position=org.area_officer,
            superintendent_position=org.district_officer,
            created_by=trade.seller.user_id,
        )


def visible_to(user, role):
    with transaction.atomic():
        set_actor(user_id=user.user_id, role=role)
        return Transaction.objects.count()


def test_transaction_visibility(
    app_db, catalogue, org, trade, make_licence, make_licensee, make_user
):
    make_raw_transaction(trade, catalogue, org)
    outsider = make_licensee(make_licence(gstin="99CCCCC2222C1Z5"), contact="+919800000999")
    stranger_officer = make_user(role=Role.PERSONNEL)
    head = make_user(role=Role.HEAD_AUTHORITY)
    assert visible_to(trade.seller, Role.LICENSEE) == 1
    assert visible_to(trade.buyer, Role.LICENSEE) == 1
    assert visible_to(trade.officer, Role.PERSONNEL) == 1
    assert visible_to(trade.superintendent, Role.PERSONNEL) == 1
    assert visible_to(head, Role.HEAD_AUTHORITY) == 1
    assert visible_to(outsider, Role.LICENSEE) == 0
    assert visible_to(stranger_officer, Role.PERSONNEL) == 0


def test_only_system_writes_and_only_status_changes(app_db, catalogue, org, trade):
    tx = make_raw_transaction(trade, catalogue, org)
    with transaction.atomic():
        set_actor(user_id=trade.seller.user_id, role=Role.LICENSEE)
        assert Transaction.objects.filter(pk=tx.pk).update(status="APPROVED") == 0
    with acting_as_system("test"):
        assert Transaction.objects.get(pk=tx.pk).status == "AWAITING_BUYER"
    with pytest.raises(DatabaseError, match="permission denied"):
        with transaction.atomic(), acting_as_system("test"):
            Transaction.objects.filter(pk=tx.pk).update(quantity=Decimal("999"))


def test_decisions_are_append_only_even_for_owner(db, catalogue, org, trade):
    tx = make_raw_transaction(trade, catalogue, org)
    with acting_as_system("test"):
        TransactionDecision.objects.create(
            transaction=tx, step="SELLER", outcome="CANCEL", actor_user_id="x"
        )
    with pytest.raises(DatabaseError, match="append-only"):
        with transaction.atomic():
            TransactionDecision.objects.update(outcome="APPROVE")
