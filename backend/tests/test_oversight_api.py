from datetime import date

import pytest

from core.db_context import acting_as_system
from oversight.service import create_due_batches
from tests.conftest import TEST_PASSWORD, set_decided_on

pytestmark = pytest.mark.django_db


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


@pytest.fixture
def batch_id(settle, review_setting):
    tx = settle()
    set_decided_on(tx, date(2026, 6, 10))
    with acting_as_system("test"):
        [made] = create_due_batches(date(2026, 6, 16))
    return made.id, tx.reference


def test_superintendent_reviews_flags_and_signs(app_db, client, trade, batch_id, otp_outbox):
    bid, ref = batch_id
    login(client, trade.superintendent, otp_outbox)
    [summary] = client.get("/api/oversight/batches").json()
    assert summary["item_count"] == 1 and summary["flag_count"] == 0
    assert summary["position"] == "District Officer, Ahmedabad"
    detail = client.get(f"/api/oversight/batches/{bid}").json()
    assert detail["can_sign"] is True
    assert detail["items"][0]["reference"] == ref
    assert detail["items"][0]["approved_by_position"] == "Area Officer, Sanand"
    assert detail["items"][0]["approved_by_superintendent"] is False
    flagged = post(
        client,
        f"/api/oversight/batches/{bid}/flag",
        {"reference": ref, "reason_code": "QUANTITY_UNUSUAL", "comment": "Check volumes"},
    ).json()
    assert (
        flagged["flag_count"] == 1
        and flagged["items"][0]["flag"]["reason"] == "Quantity unusually high"
    )
    challenge = post(client, f"/api/oversight/batches/{bid}/sign-off-code").json()["challenge_id"]
    signed = post(
        client,
        f"/api/oversight/batches/{bid}/sign-off",
        {"challenge_id": challenge, "code": otp_outbox[-1][1]},
    )
    assert (
        signed.status_code == 200
        and signed.json()["status"] == "SIGNED"
        and signed.json()["can_sign"] is False
    )


def test_flag_reaches_the_officer_as_an_alert(app_db, client, trade, batch_id, otp_outbox):
    bid, ref = batch_id
    login(client, trade.superintendent, otp_outbox)
    post(
        client,
        f"/api/oversight/batches/{bid}/flag",
        {"reference": ref, "reason_code": "PATTERN_CONCERN"},
    )
    login(client, trade.officer, otp_outbox)
    alerts = client.get("/api/alerts").json()["alerts"]
    assert [a["kind"] for a in alerts] == ["SUPERINTENDENT_FLAG"] and alerts[0]["pattern"] is None
    assert alerts[0]["pattern_count"] is None


def test_others_cannot_see_or_act_on_batches(app_db, client, trade, batch_id, otp_outbox):
    bid, ref = batch_id
    login(client, trade.officer, otp_outbox)
    assert client.get("/api/oversight/batches").json() == []
    assert client.get(f"/api/oversight/batches/{bid}").status_code == 404
    assert (
        post(
            client,
            f"/api/oversight/batches/{bid}/flag",
            {"reference": ref, "reason_code": "PATTERN_CONCERN"},
        ).status_code
        == 403
    )


def test_bad_reason_is_400_and_wrong_code_is_401(app_db, client, trade, batch_id, otp_outbox):
    bid, ref = batch_id
    login(client, trade.superintendent, otp_outbox)
    assert (
        post(
            client,
            f"/api/oversight/batches/{bid}/flag",
            {"reference": ref, "reason_code": "NOT_ORDERED"},
        ).status_code
        == 400
    )
    challenge = post(client, f"/api/oversight/batches/{bid}/sign-off-code").json()["challenge_id"]
    real = otp_outbox[-1][1]
    wrong = "000000" if real != "000000" else "111111"
    response = post(
        client, f"/api/oversight/batches/{bid}/sign-off", {"challenge_id": challenge, "code": wrong}
    )
    assert response.status_code == 401


def test_superintendent_approved_item_is_marked_and_cannot_be_flagged(
    app_db, client, trade, settle, review_setting, threshold, otp_outbox
):
    tx = settle("300", officer="RECOMMEND", superintendent="APPROVE")
    set_decided_on(tx, date(2026, 6, 10))
    with acting_as_system("test"):
        [made] = create_due_batches(date(2026, 6, 16))
    login(client, trade.superintendent, otp_outbox)
    detail = client.get(f"/api/oversight/batches/{made.id}").json()
    assert detail["items"][0]["approved_by_superintendent"] is True
    refused = post(
        client,
        f"/api/oversight/batches/{made.id}/flag",
        {"reference": tx.reference, "reason_code": "PATTERN_CONCERN"},
    )
    assert refused.status_code == 403
    assert refused.json() == {
        "detail": "You approved this transaction; the Head Authority reviews it."
    }
