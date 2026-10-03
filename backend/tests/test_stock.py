from decimal import Decimal

import pytest
from django.db import DatabaseError, IntegrityError, transaction

from core.db_context import acting_as_system, set_actor
from identity.roles import Role
from stock.models import StockBalance, StockMovement
from stock.service import (
    InsufficientStock,
    StockLimitExceeded,
    balance_of,
    set_opening_balance,
    transfer,
)
from tests.conftest import TEST_PASSWORD

pytestmark = pytest.mark.django_db
SELLER = "a" * 64
BUYER = "b" * 64


def opening(catalogue, index, qty):
    with acting_as_system("test"):
        return set_opening_balance(
            gstin_index=index, substance=catalogue.whisky, quantity=Decimal(qty), by="test"
        )


def test_balance_is_zero_without_a_row(app_db, catalogue):
    with acting_as_system("test"):
        assert balance_of(SELLER, catalogue.whisky) == Decimal("0")


def test_opening_balance_is_recorded_once_with_a_movement(app_db, catalogue, audit_actions):
    opening(catalogue, SELLER, "400")
    with acting_as_system("test"):
        assert balance_of(SELLER, catalogue.whisky) == Decimal("400")
        movement = StockMovement.objects.get(gstin_index=SELLER)
        assert (movement.delta, movement.balance_after, movement.reason) == (
            Decimal("400"),
            Decimal("400"),
            "OPENING",
        )
    assert audit_actions() == ["stock.opening_recorded"]
    with pytest.raises(ValueError, match="already recorded"):
        opening(catalogue, SELLER, "10")


def test_transfer_moves_stock_and_logs_both_sides(app_db, catalogue):
    opening(catalogue, SELLER, "400")
    with acting_as_system("test"):
        transfer(
            from_gstin_index=SELLER,
            to_gstin_index=BUYER,
            substance=catalogue.whisky,
            quantity=Decimal("150"),
            transaction_reference="TXTEST00001",
            max_target=Decimal("1000"),
        )
        assert balance_of(SELLER, catalogue.whisky) == Decimal("250")
        assert balance_of(BUYER, catalogue.whisky) == Decimal("150")
        deltas = sorted(
            StockMovement.objects.filter(reason="TRANSACTION").values_list("delta", flat=True)
        )
        assert deltas == [Decimal("-150"), Decimal("150")]


def test_transfer_refuses_more_than_the_seller_holds(app_db, catalogue):
    opening(catalogue, SELLER, "100")
    with pytest.raises(InsufficientStock):
        with acting_as_system("test"):
            transfer(
                from_gstin_index=SELLER,
                to_gstin_index=BUYER,
                substance=catalogue.whisky,
                quantity=Decimal("101"),
                transaction_reference="TXTEST00002",
                max_target=Decimal("1000"),
            )
    with acting_as_system("test"):
        assert balance_of(SELLER, catalogue.whisky) == Decimal("100")


def test_transfer_refuses_above_target_limit(app_db, catalogue):
    opening(catalogue, SELLER, "400")
    opening(catalogue, BUYER, "90")
    with pytest.raises(StockLimitExceeded, match="above their licence limit"):
        with acting_as_system("test"):
            transfer(
                from_gstin_index=SELLER,
                to_gstin_index=BUYER,
                substance=catalogue.whisky,
                quantity=Decimal("20"),
                transaction_reference="TXTEST00003",
                max_target=Decimal("100"),
            )
    with acting_as_system("test"):
        assert balance_of(SELLER, catalogue.whisky) == Decimal("400")
        assert balance_of(BUYER, catalogue.whisky) == Decimal("90")


def test_database_never_allows_negative_stock(app_db, catalogue):
    opening(catalogue, SELLER, "10")
    with pytest.raises(IntegrityError):
        with transaction.atomic(), acting_as_system("test"):
            StockBalance.objects.filter(gstin_index=SELLER).update(quantity=Decimal("-1"))


def test_holder_sees_only_own_stock(app_db, catalogue, make_licence, make_licensee):
    licence = make_licence()
    opening(catalogue, licence.gstin_index, "50")
    opening(catalogue, BUYER, "70")
    holder = make_licensee(licence)
    with transaction.atomic():
        set_actor(user_id=holder.user_id, role=Role.LICENSEE)
        assert list(StockBalance.objects.values_list("quantity", flat=True)) == [Decimal("50.000")]
        assert StockMovement.objects.count() == 1


def test_licensing_authority_cannot_read_stock(app_db, catalogue, make_user):
    opening(catalogue, SELLER, "50")
    authority = make_user(role=Role.LICENSING_AUTHORITY, contact="+919800000501")
    with transaction.atomic():
        set_actor(user_id=authority.user_id, role=Role.LICENSING_AUTHORITY)
        assert StockBalance.objects.count() == 0
        assert StockMovement.objects.count() == 0


def test_only_system_can_write_stock(app_db, catalogue):
    with pytest.raises(DatabaseError):
        with transaction.atomic():
            set_actor(user_id="GJLICENSEE01", role=Role.LICENSEE)
            StockBalance.objects.create(
                gstin_index=SELLER, substance=catalogue.whisky, quantity=Decimal("1")
            )


def test_movements_are_append_only_even_for_owner(db, catalogue):
    opening(catalogue, SELLER, "10")
    with pytest.raises(DatabaseError, match="append-only"):
        with transaction.atomic():
            StockMovement.objects.update(delta=Decimal("999"))


def test_my_stock_api(app_db, client, catalogue, make_licence, make_licensee, otp_outbox):
    licence = make_licence()
    opening(catalogue, licence.gstin_index, "320")
    user = make_licensee(licence)
    first = client.post(
        "/api/auth/login",
        {"user_id": user.user_id, "password": TEST_PASSWORD},
        content_type="application/json",
    )
    client.post(
        "/api/auth/login/verify",
        {"challenge_id": first.json()["challenge_id"], "code": otp_outbox[-1][1]},
        content_type="application/json",
    )
    assert client.get("/api/stock/mine").json() == [
        {"substance_code": "WHISKY", "substance": "Whisky", "quantity": "320.000", "unit": "L"}
    ]
