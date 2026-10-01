from decimal import Decimal

import pytest
from django.test import Client

from core.db_context import acting_as_system
from stock.service import balance_of
from tests.conftest import BUYER_GSTIN, TEST_PASSWORD

pytestmark = pytest.mark.django_db
NEW_TX = {
    "buyer_gstin": BUYER_GSTIN,
    "substance_code": "WHISKY",
    "quantity": "150",
    "transporter_name": "Ravi Transport Co",
    "transporter_id_number": "GJ-TR-4411",
    "vehicle_number": "GJ01AB1234",
    "route": "Sanand to Bopal via SG Highway",
}


def login(client, user, otp_outbox):
    client.logout()
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


def post(client, url, body=None):
    return client.post(url, body or {}, content_type="application/json")


def sign(client, ref, otp_outbox, outcome, **extra):
    challenge = post(client, f"/api/transactions/{ref}/decision-code").json()["challenge_id"]
    return post(
        client,
        f"/api/transactions/{ref}/decide",
        {"challenge_id": challenge, "code": otp_outbox[-1][1], "outcome": outcome, **extra},
    )


def test_full_journey_over_http(app_db, client, catalogue, trade, otp_outbox):
    login(client, trade.seller, otp_outbox)
    assert post(client, "/api/transactions/buyer-lookup", {"gstin": BUYER_GSTIN}).json() == {
        "holder_name": "Bopal Bar & Kitchen"
    }
    created = post(client, "/api/transactions", NEW_TX)
    assert created.status_code == 201
    ref = created.json()["reference"]
    assert created.json()["next_action"] == "Waiting for the buyer to confirm."

    login(client, trade.buyer, otp_outbox)
    assert sign(client, ref, otp_outbox, "CONFIRM").json()["status"] == "AWAITING_OFFICER"

    login(client, trade.officer, otp_outbox)
    detail = client.get(f"/api/transactions/{ref}").json()
    assert detail["your_role"] == "officer" and detail["next_action"] == "Your decision is needed."
    approved = sign(client, ref, otp_outbox, "APPROVE").json()
    assert approved["status"] == "APPROVED"
    assert [e["outcome"] for e in approved["timeline"]] == ["STARTED", "CONFIRM", "APPROVE"]
    with acting_as_system("test"):
        assert balance_of(trade.buyer_licence.gstin_index, catalogue.whisky) == Decimal("150")


def test_refused_transaction_returns_reasons(app_db, client, trade, otp_outbox):
    login(client, trade.seller, otp_outbox)
    response = post(client, "/api/transactions", {**NEW_TX, "quantity": "600"})
    assert response.status_code == 422
    assert response.json()["detail"] == "This transaction can't go ahead."
    assert (
        "Quantity 600 L exceeds your licence's per-transaction limit of 500 L."
        in response.json()["reasons"]
    )


def test_invalid_input_is_400(app_db, client, trade, otp_outbox):
    login(client, trade.seller, otp_outbox)
    assert post(client, "/api/transactions", {**NEW_TX, "vehicle_number": ""}).status_code == 400
    assert post(client, "/api/transactions", {**NEW_TX, "quantity": "-5"}).status_code == 400
    assert (
        post(client, "/api/transactions", {**NEW_TX, "substance_code": "NOPE"}).status_code == 400
    )


def test_unknown_buyer_lookup_is_404(app_db, client, trade, otp_outbox):
    login(client, trade.seller, otp_outbox)
    response = post(client, "/api/transactions/buyer-lookup", {"gstin": "99ZZZZZ9999Z1Z5"})
    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == "No licensed business was found for this GSTIN. Check all 15 characters."
    )


def test_wrong_code_is_401(app_db, client, trade, otp_outbox):
    login(client, trade.seller, otp_outbox)
    ref = post(client, "/api/transactions", NEW_TX).json()["reference"]
    login(client, trade.buyer, otp_outbox)
    challenge = post(client, f"/api/transactions/{ref}/decision-code").json()["challenge_id"]
    real = otp_outbox[-1][1]
    wrong = "000000" if real != "000000" else "111111"
    response = post(
        client,
        f"/api/transactions/{ref}/decide",
        {"challenge_id": challenge, "code": wrong, "outcome": "CONFIRM"},
    )
    assert response.status_code == 401


def test_outsider_cannot_see_transaction(
    app_db, client, trade, otp_outbox, make_licence, make_licensee
):
    login(client, trade.seller, otp_outbox)
    ref = post(client, "/api/transactions", NEW_TX).json()["reference"]
    outsider = make_licensee(make_licence(gstin="99CCCCC2222C1Z5"), contact="+919800000999")
    login(client, outsider, otp_outbox)
    assert client.get(f"/api/transactions/{ref}").status_code == 404
    assert client.get("/api/transactions").json() == []


def test_buyer_comment_is_hidden_from_seller(app_db, client, trade, otp_outbox):
    login(client, trade.seller, otp_outbox)
    ref = post(client, "/api/transactions", NEW_TX).json()["reference"]
    login(client, trade.buyer, otp_outbox)
    sign(client, ref, otp_outbox, "REJECT", reason_code="OTHER", comment="Never ordered from them")
    login(client, trade.seller, otp_outbox)
    seller_view = client.get(f"/api/transactions/{ref}").json()["timeline"][-1]
    assert seller_view["reason"] == "Other" and seller_view["comment"] is None
    login(client, trade.officer, otp_outbox)
    officer_view = client.get(f"/api/transactions/{ref}").json()["timeline"][-1]
    assert officer_view["comment"] == "Never ordered from them"


def test_seller_sees_buyer_name_but_not_licence_number(app_db, client, trade, otp_outbox):
    login(client, trade.seller, otp_outbox)
    detail = post(client, "/api/transactions", NEW_TX).json()
    assert detail["buyer_name"] == "Bopal Bar & Kitchen"
    assert "GJ/TEST" not in str(detail)  # licence numbers are never shown


def test_confirm_with_blank_reason_code_is_accepted(app_db, client, trade, otp_outbox):
    login(client, trade.seller, otp_outbox)
    ref = post(client, "/api/transactions", NEW_TX).json()["reference"]
    login(client, trade.buyer, otp_outbox)
    response = sign(client, ref, otp_outbox, "CONFIRM", reason_code="")
    assert response.status_code == 200
    assert response.json()["status"] == "AWAITING_OFFICER"


def test_seller_can_cancel_and_buyer_cannot(app_db, client, trade, otp_outbox):
    login(client, trade.seller, otp_outbox)
    first = post(client, "/api/transactions", NEW_TX).json()["reference"]
    second = post(client, "/api/transactions", NEW_TX).json()["reference"]
    cancelled = post(client, f"/api/transactions/{first}/cancel")
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "CANCELLED"
    login(client, trade.buyer, otp_outbox)
    assert post(client, f"/api/transactions/{second}/cancel").status_code == 403


def test_non_licensee_cannot_start_or_look_up(app_db, client, trade, otp_outbox):
    login(client, trade.officer, otp_outbox)
    assert post(client, "/api/transactions", NEW_TX).status_code == 403
    lookup = post(client, "/api/transactions/buyer-lookup", {"gstin": BUYER_GSTIN})
    assert lookup.status_code == 403


def test_decide_maps_errors(app_db, client, trade, otp_outbox):
    login(client, trade.seller, otp_outbox)
    big = {**NEW_TX, "quantity": "300"}
    first = post(client, "/api/transactions", big).json()["reference"]
    second = post(client, "/api/transactions", big).json()["reference"]
    third = post(client, "/api/transactions", big).json()["reference"]

    login(client, trade.buyer, otp_outbox)
    wrong_kind = sign(client, third, otp_outbox, "REJECT", reason_code="TRANSPORTER_INVALID")
    assert wrong_kind.status_code == 400
    assert sign(client, first, otp_outbox, "CONFIRM").status_code == 200
    assert sign(client, second, otp_outbox, "CONFIRM").status_code == 200

    login(client, trade.officer, otp_outbox)
    assert sign(client, first, otp_outbox, "APPROVE").status_code == 200
    refused = sign(client, second, otp_outbox, "APPROVE")
    assert refused.status_code == 422
    assert any("in stock" in r for r in refused.json()["reasons"])


def test_post_requires_csrf_token(app_db, trade, otp_outbox):
    c = Client(enforce_csrf_checks=True)
    token = c.get("/api/auth/csrf").cookies["csrftoken"].value
    headers = {"HTTP_X_CSRFTOKEN": token}
    first = c.post(
        "/api/auth/login",
        {"user_id": trade.seller.user_id, "password": TEST_PASSWORD},
        content_type="application/json",
        **headers,
    )
    c.post(
        "/api/auth/login/verify",
        {"challenge_id": first.json()["challenge_id"], "code": otp_outbox[-1][1]},
        content_type="application/json",
        **headers,
    )
    token = c.cookies["csrftoken"].value
    assert post(c, "/api/transactions", NEW_TX).status_code == 403
    created = c.post(
        "/api/transactions", NEW_TX, content_type="application/json", HTTP_X_CSRFTOKEN=token
    )
    assert created.status_code == 201
