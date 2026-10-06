import pytest

from alerts.models import AuthorityAlert
from core.db_context import acting_as_system
from tests.conftest import login_body

pytestmark = pytest.mark.django_db


def login(client, user, otp_outbox):
    client.logout()
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


def test_officer_sees_alert_with_pattern(app_db, client, trade, settle, otp_outbox):
    settle(buyer="REJECT", reason_code="NOT_ORDERED")
    login(client, trade.officer, otp_outbox)
    body = client.get("/api/alerts").json()
    assert body["unacknowledged"] == 1
    alert = body["alerts"][0]
    assert alert["kind"] == "BUYER_REJECTION"
    assert alert["reason"] == "I did not place this order"
    assert alert["pattern"] == "1st buyer rejection for this seller in the last 30 days"
    assert alert["pattern_count"] == 1  # the web app highlights a repeat (2 or more)
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


def test_unacknowledged_count_is_not_capped_by_the_list(
    app_db, client, trade, org, settle, otp_outbox
):
    tx = settle(buyer="REJECT", reason_code="NOT_ORDERED")
    with acting_as_system("test"):
        first = AuthorityAlert.objects.filter(transaction=tx, position=org.area_officer).get()
        AuthorityAlert.objects.bulk_create(
            [
                AuthorityAlert(
                    kind=first.kind,
                    position=first.position,
                    transaction=tx,
                    reason=first.reason,
                    pattern_count=1,
                )
                for _ in range(100)
            ]
        )
    login(client, trade.officer, otp_outbox)
    body = client.get("/api/alerts").json()
    assert len(body["alerts"]) == 100
    assert body["unacknowledged"] == 101


def _officer_alert(client, trade, settle, otp_outbox):
    settle(buyer="REJECT", reason_code="NOT_ORDERED")
    login(client, trade.officer, otp_outbox)
    return client.get("/api/alerts").json()["alerts"][0]["id"]


def test_acknowledge_rejects_bad_input(app_db, client, trade, settle, otp_outbox):
    alert_id = _officer_alert(client, trade, settle, otp_outbox)
    url = f"/api/alerts/{alert_id}/acknowledge"
    too_long = client.post(url, {"note": "x" * 501}, content_type="application/json")
    assert too_long.status_code == 400
    null = client.post(url, {"note": None}, content_type="application/json")
    assert null.status_code == 400
    assert null.json()["note"] == ["This field may not be null."]
    not_object = client.post(url, [1, 2], content_type="application/json")
    assert not_object.status_code == 400
    assert client.get("/api/alerts").json()["unacknowledged"] == 1


def test_acknowledge_without_body_works(app_db, client, trade, settle, otp_outbox):
    alert_id = _officer_alert(client, trade, settle, otp_outbox)
    response = client.post(f"/api/alerts/{alert_id}/acknowledge", content_type="application/json")
    assert response.status_code == 200
    assert response.json()["acknowledged"] is True
    assert response.json()["note"] is None
