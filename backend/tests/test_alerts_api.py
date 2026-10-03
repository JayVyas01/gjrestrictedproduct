import pytest

from tests.conftest import TEST_PASSWORD

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


def test_officer_sees_alert_with_pattern(app_db, client, trade, settle, otp_outbox):
    settle(buyer="REJECT", reason_code="NOT_ORDERED")
    login(client, trade.officer, otp_outbox)
    body = client.get("/api/alerts").json()
    assert body["unacknowledged"] == 1
    alert = body["alerts"][0]
    assert alert["kind"] == "BUYER_REJECTION"
    assert alert["reason"] == "I did not place this order"
    assert alert["pattern"] == "1st buyer rejection for this seller in the last 30 days"
    assert alert["seller_name"] == "Sanand Spirits Pvt Ltd"
    assert alert["buyer_name"] == "Bopal Bar & Kitchen"
    assert alert["acknowledged"] is False
    assert "GJ/TEST" not in str(alert)


def test_acknowledge_over_http(app_db, client, trade, settle, otp_outbox):
    settle(buyer="REJECT", reason_code="NOT_ORDERED")
    login(client, trade.officer, otp_outbox)
    alert_id = client.get("/api/alerts").json()["alerts"][0]["id"]
    acked = client.post(
        f"/api/alerts/{alert_id}/acknowledge",
        {"note": "Called the buyer"},
        content_type="application/json",
    ).json()
    assert acked["acknowledged"] is True
    assert acked["note"] == "Called the buyer"
    assert acked["acknowledged_by"] == trade.officer.user_id
    assert client.get("/api/alerts").json()["unacknowledged"] == 0


def test_licensees_see_no_alerts(app_db, client, trade, settle, otp_outbox):
    settle(buyer="REJECT", reason_code="NOT_ORDERED")
    login(client, trade.seller, otp_outbox)
    assert client.get("/api/alerts").json() == {"unacknowledged": 0, "alerts": []}


def test_cannot_acknowledge_someone_elses_alert(app_db, client, trade, settle, otp_outbox):
    settle(buyer="REJECT", reason_code="NOT_ORDERED")
    login(client, trade.officer, otp_outbox)
    officer_alert = client.get("/api/alerts").json()["alerts"][0]["id"]
    login(client, trade.superintendent, otp_outbox)
    response = client.post(
        f"/api/alerts/{officer_alert}/acknowledge", {}, content_type="application/json"
    )
    assert response.status_code == 403
