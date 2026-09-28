from datetime import timedelta

import pytest
from django.db import transaction
from django.utils import timezone

from audit.models import AuditEvent
from core.db_context import SYSTEM_ROLE, set_actor
from identity.models import User
from identity.roles import Role
from tests.conftest import TEST_PASSWORD

pytestmark = pytest.mark.django_db


def start(client, user_id, password=TEST_PASSWORD):
    return client.post(
        "/api/auth/login",
        {"user_id": user_id, "password": password},
        content_type="application/json",
    )


def verify(client, challenge_id, code):
    return client.post(
        "/api/auth/login/verify",
        {"challenge_id": challenge_id, "code": code},
        content_type="application/json",
    )


def login(client, user, otp_outbox):
    challenge_id = start(client, user.user_id).json()["challenge_id"]
    return verify(client, challenge_id, otp_outbox[-1][1])


def test_full_login_requires_password_and_otp(app_db, client, make_user, otp_outbox):
    user = make_user(role=Role.LICENSEE)
    first = start(client, user.user_id)
    assert first.status_code == 200
    assert client.get("/api/auth/me").status_code == 403  # password alone is not a login

    second = verify(client, first.json()["challenge_id"], otp_outbox[-1][1])
    assert second.status_code == 200
    assert client.get("/api/auth/me").json() == {"user_id": user.user_id, "role": "LICENSEE"}


def test_user_id_is_case_insensitive(app_db, client, make_user, otp_outbox):
    user = make_user()
    assert start(client, user.user_id.lower()).status_code == 200


def test_wrong_password_and_unknown_user_look_identical(app_db, client, make_user, otp_outbox):
    user = make_user()
    wrong_password = start(client, user.user_id, "wrong-password-123")
    unknown_user = start(client, "GJNOSUCHUSER")
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json() == {"detail": "Invalid credentials"}
    assert otp_outbox == []


def test_wrong_otp_is_rejected(app_db, client, make_user, otp_outbox):
    user = make_user()
    challenge_id = start(client, user.user_id).json()["challenge_id"]
    code = otp_outbox[-1][1]
    wrong = "000000" if code != "000000" else "111111"
    assert verify(client, challenge_id, wrong).status_code == 401
    assert client.get("/api/auth/me").status_code == 403


def test_account_locks_after_repeated_failures(app_db, client, make_user, otp_outbox):
    user = make_user()
    for _ in range(5):
        start(client, user.user_id, "wrong-password-123")
    assert start(client, user.user_id).status_code == 401  # even the right password
    user.refresh_from_db()
    assert user.locked_until is not None


def test_account_locks_after_too_many_code_requests(app_db, client, make_user, otp_outbox):
    user = make_user()
    for _ in range(5):
        assert start(client, user.user_id).status_code == 200
    assert start(client, user.user_id).status_code == 401
    user.refresh_from_db()
    assert user.locked_until is not None


def test_login_is_rate_limited(app_db, client):
    statuses = [start(client, "GJNOSUCHUSER").status_code for _ in range(11)]
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429


def test_session_cookie_is_hardened(app_db, client, make_user, otp_outbox):
    response = login(client, make_user(), otp_outbox)
    cookie = response.cookies["sessionid"]
    assert cookie["httponly"] is True
    assert cookie["secure"] is True
    assert cookie["samesite"] == "Strict"


def test_logout_ends_session(app_db, client, make_user, otp_outbox):
    login(client, make_user(), otp_outbox)
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 403


def test_login_events_are_audited(app_db, client, make_user, otp_outbox, audit_actions):
    user = make_user()
    start(client, user.user_id, "wrong-password-123")
    login(client, user, otp_outbox)
    client.post("/api/auth/logout")
    assert audit_actions() == ["login.failed", "login.succeeded", "logout"]


def test_csrf_endpoint_sets_cookie(app_db, client):
    response = client.get("/api/auth/csrf")
    assert response.status_code == 204
    assert "csrftoken" in response.cookies


def test_rate_limit_ignores_spoofed_forwarded_for(app_db, client):
    statuses = [
        client.post(
            "/api/auth/login",
            {"user_id": "GJNOSUCHUSER", "password": TEST_PASSWORD},
            content_type="application/json",
            HTTP_X_FORWARDED_FOR=f"10.0.0.{i}",
        ).status_code
        for i in range(11)
    ]
    assert statuses[10] == 429


def test_locked_and_inactive_accounts_still_check_the_password(
    app_db, client, make_user, monkeypatch
):
    calls = {"count": 0}
    original = User.check_password

    def counting_check_password(self, raw_password):
        calls["count"] += 1
        return original(self, raw_password)

    monkeypatch.setattr(User, "check_password", counting_check_password)

    locked_user = make_user()
    locked_user.locked_until = timezone.now() + timedelta(minutes=15)
    locked_user.save(update_fields=["locked_until"])
    calls["count"] = 0
    start(client, locked_user.user_id)
    assert calls["count"] == 1

    inactive_user = make_user()
    inactive_user.is_active = False
    inactive_user.save(update_fields=["is_active"])
    calls["count"] = 0
    start(client, inactive_user.user_id)
    assert calls["count"] == 1


def test_locking_cancels_outstanding_login_code(app_db, client, make_user, otp_outbox):
    user = make_user()
    challenge_id = start(client, user.user_id).json()["challenge_id"]
    code = otp_outbox[-1][1]

    for _ in range(5):
        start(client, user.user_id, "wrong-password-123")

    assert verify(client, challenge_id, code).status_code == 401
    assert client.get("/api/auth/me").status_code == 403


def test_unknown_user_attempt_is_not_stored_in_plaintext(app_db, client):
    start(client, "GJSECRET1234")

    with transaction.atomic():
        set_actor(user_id="test", role=SYSTEM_ROLE)
        payloads = list(AuditEvent.objects.order_by("id").values_list("payload", flat=True))

    for payload in payloads:
        for value in (payload or {}).values():
            assert "GJSECRET1234" not in str(value)
