import pytest

from identity.models import User
from identity.roles import Role
from tests.conftest import TEST_PASSWORD, login_body

pytestmark = pytest.mark.django_db


def log_in(client, user, otp_outbox):
    first = client.post(
        "/api/auth/login",
        login_body(user),
        content_type="application/json",
    )
    client.post(
        "/api/auth/login/verify",
        {"challenge_id": first.json()["challenge_id"], "code": otp_outbox[-1][1]},
        content_type="application/json",
    )


def licensee_for(licence) -> User:
    return User.objects.create_user(
        role=Role.LICENSEE,
        password=TEST_PASSWORD,
        contact="+919800000999",
        licensee_gstin_index=licence.gstin_index,
    )


def test_licensee_sees_own_licence_card(app_db, client, catalogue, make_licence, otp_outbox):
    licence = make_licence(substance=catalogue.whisky)
    make_licence(gstin="99BBBBB1111B1Z5")
    log_in(client, licensee_for(licence), otp_outbox)

    cards = client.get("/api/licences/mine").json()
    assert len(cards) == 1
    card = cards[0]
    assert card["licence_number"] == "GJ/TEST/0001"
    assert card["licence_type"] == "Retail"
    assert card["scope"] == "Whisky"
    assert card["unit"] == "L"
    assert card["scope_kind"] == "substance"
    assert card["may_sell"] is True
    assert card["max_per_transaction_qty"] == "500.000"
    assert card["valid_from"] == "2026-01-01" and card["valid_to"] == "2047-12-31"
    assert set(card) == {
        "licence_number",
        "holder_name",
        "licence_type",
        "scope",
        "scope_kind",
        "unit",
        "status",
        "valid_from",
        "valid_to",
        "trading_permitted",
        "may_buy",
        "may_sell",
        "may_transport",
        "max_stock_qty",
        "max_per_transaction_qty",
    }


def test_class_licence_card_carries_the_class_unit(
    app_db, client, catalogue, make_licence, otp_outbox
):
    licence = make_licence(substance_class=catalogue.spirits)
    log_in(client, licensee_for(licence), otp_outbox)

    (card,) = client.get("/api/licences/mine").json()
    assert card["scope"] == "Spirits"
    assert card["scope_kind"] == "class"
    # A class shares one unit, so its limits show with it (catalogue.service.class_unit).
    assert card["unit"] == "L"


@pytest.mark.parametrize("role", [Role.PERSONNEL, Role.LICENSING_AUTHORITY, Role.HEAD_AUTHORITY])
def test_only_licensees_have_my_licences(app_db, client, make_member, otp_outbox, role):
    log_in(client, make_member(role), otp_outbox)
    assert client.get("/api/licences/mine").status_code == 403


def test_my_licences_requires_login(app_db, client):
    assert client.get("/api/licences/mine").status_code == 403


def test_substance_list_for_logged_in_users(app_db, client, catalogue, make_member, otp_outbox):
    log_in(client, make_member(Role.LICENSEE), otp_outbox)
    body = client.get("/api/catalogue/substances").json()
    assert {"code": "WHISKY", "name": "Whisky", "substance_class": "Spirits", "unit": "L"} in body
