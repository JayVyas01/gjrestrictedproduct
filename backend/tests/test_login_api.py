from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.test import Client
from django.utils import timezone

from audit.models import AuditEvent
from core.db_context import SYSTEM_ROLE, set_actor
from identity.models import User
from identity.roles import Role
from positions.service import assign
from tests.conftest import DEMO_GSTIN, TEST_PASSWORD, api_login, login_body

pytestmark = pytest.mark.django_db

OFFICIAL_EMAIL = "authority@test.example"
NEW_PASSWORD = "a-brand-new-secret-77"


def start(client, role, identifier, password=TEST_PASSWORD):
    return client.post(
        "/api/auth/login",
        {"role": role, "identifier": identifier, "password": password},
        content_type="application/json",
    )


def start_as(client, user, password=TEST_PASSWORD):
    return client.post(
        "/api/auth/login", login_body(user, password), content_type="application/json"
    )


def verify(client, challenge_id, code):
    return client.post(
        "/api/auth/login/verify",
        {"challenge_id": challenge_id, "code": code},
        content_type="application/json",
    )


@pytest.fixture
def official(make_user):
    return make_user(role=Role.LICENSING_AUTHORITY, email=OFFICIAL_EMAIL)


def change_password(client, current=TEST_PASSWORD, new=NEW_PASSWORD):
    return client.post(
        "/api/auth/password",
        {"current_password": current, "new_password": new},
        content_type="application/json",
    )


# --- Signing in by role -------------------------------------------------------------------------


def test_full_login_requires_password_and_otp(app_db, client, official, otp_outbox):
    first = start(client, "LICENSING_AUTHORITY", OFFICIAL_EMAIL)
    assert first.status_code == 200
    assert client.get("/api/auth/me").status_code == 403  # password alone is not a login

    second = verify(client, first.json()["challenge_id"], otp_outbox[-1][1])
    assert second.status_code == 200
    assert second.json() == {
        "user_id": official.user_id,
        "role": "LICENSING_AUTHORITY",
        "must_change_password": False,
    }
    me = client.get("/api/auth/me").json()
    assert (me["user_id"], me["role"], me["must_change_password"]) == (
        official.user_id,
        "LICENSING_AUTHORITY",
        False,
    )


def test_a_party_signs_in_with_its_gstin(app_db, client, trade, otp_outbox):
    # Normalised as licensing does: surrounding spaces and lower case are fine.
    response = start(client, "PARTY", f"  {DEMO_GSTIN.lower()} ")
    assert response.status_code == 200
    verified = verify(client, response.json()["challenge_id"], otp_outbox[-1][1])
    assert verified.json()["user_id"] == trade.seller.user_id


@pytest.mark.parametrize(
    "role", [Role.LICENSING_AUTHORITY, Role.HEAD_AUTHORITY, Role.SOFTWARE_OWNER]
)
def test_authorities_sign_in_with_their_email(app_db, client, make_user, otp_outbox, role):
    user = make_user(role=role, email="Someone@Test.Example")
    assert start(client, role, " someone@TEST.example").status_code == 200
    assert api_login(client, user, otp_outbox).json()["user_id"] == user.user_id


def test_officers_sign_in_by_the_position_they_hold(app_db, client, trade, otp_outbox):
    officer, superintendent = trade.officer, trade.superintendent
    assert start(client, "AREA_OFFICER", officer.get_email()).status_code == 200
    assert start(client, "SUPERINTENDENT", superintendent.get_email()).status_code == 200
    # The other officer role does not match the position held.
    assert start(client, "SUPERINTENDENT", officer.get_email()).status_code == 401
    assert start(client, "AREA_OFFICER", superintendent.get_email()).status_code == 401


def test_an_officer_holding_both_levels_may_use_either_role(app_db, client, org, trade):
    assign(org.district_officer, trade.officer, by="test")
    assert start(client, "AREA_OFFICER", trade.officer.get_email()).status_code == 200
    assert start(client, "SUPERINTENDENT", trade.officer.get_email()).status_code == 200


def test_an_officer_without_a_position_cannot_sign_in(app_db, client, make_user):
    officer = make_user(role=Role.PERSONNEL, email="idle@test.example")
    assert start(client, "AREA_OFFICER", "idle@test.example").status_code == 401
    assert start(client, "SUPERINTENDENT", "idle@test.example").status_code == 401
    assert officer.locked_until is None


def test_wrong_role_unknown_identifier_and_wrong_password_look_identical(
    app_db, client, official, trade, otp_outbox
):
    answers = [
        start(client, "LICENSING_AUTHORITY", OFFICIAL_EMAIL, "wrong-password-123"),
        start(client, "LICENSING_AUTHORITY", "nobody@test.example"),
        start(client, "HEAD_AUTHORITY", OFFICIAL_EMAIL),  # right email, wrong role
        start(client, "LICENSING_AUTHORITY", DEMO_GSTIN),  # a GSTIN is not an email
        start(client, "PARTY", OFFICIAL_EMAIL),
        start(client, "PARTY", "99ZZZZZ9999Z1Z5"),
    ]
    assert {answer.status_code for answer in answers} == {401}
    assert {str(answer.json()) for answer in answers} == {str({"detail": "Invalid credentials"})}
    assert otp_outbox == []


def test_every_failure_path_spends_a_password_hash(app_db, client, official, monkeypatch):
    calls = {"count": 0}
    original_check = User.check_password

    def counting_check(self, raw_password):
        calls["count"] += 1
        return original_check(self, raw_password)

    def counting_make(password):
        calls["count"] += 1
        return "x"

    monkeypatch.setattr(User, "check_password", counting_check)
    monkeypatch.setattr("identity.login.make_password", counting_make)
    for role, identifier in [
        ("LICENSING_AUTHORITY", "nobody@test.example"),
        ("HEAD_AUTHORITY", OFFICIAL_EMAIL),
        ("PARTY", DEMO_GSTIN),
        ("AREA_OFFICER", OFFICIAL_EMAIL),
    ]:
        calls["count"] = 0
        start(client, role, identifier)
        assert calls["count"] == 1, (role, identifier)


def test_old_request_shape_is_refused(app_db, client, official):
    response = client.post(
        "/api/auth/login",
        {"user_id": official.user_id, "password": TEST_PASSWORD},
        content_type="application/json",
    )
    assert response.status_code == 400


def test_emails_are_unique_whatever_the_case(app_db, make_user):
    make_user(role=Role.HEAD_AUTHORITY, email="same@test.example")
    with pytest.raises(IntegrityError), transaction.atomic():
        make_user(role=Role.LICENSING_AUTHORITY, email=" SAME@test.example")
    # Accounts without an email (parties) do not collide.
    make_user(role=Role.LICENSEE)
    make_user(role=Role.LICENSEE)


def test_email_and_address_are_encrypted_at_rest(app_db, make_user):
    user = make_user(role=Role.HEAD_AUTHORITY, email="head@test.example")
    user.set_address("12 Ashram Road, Ahmedabad")
    user.save()
    user.refresh_from_db()
    assert "head@" not in user.email_encrypted and "Ashram" not in user.address_encrypted
    assert (user.get_email(), user.get_address()) == (
        "head@test.example",
        "12 Ashram Road, Ahmedabad",
    )


# --- Codes, lockout and the session -------------------------------------------------------------


def test_wrong_otp_is_rejected(app_db, client, official, otp_outbox):
    challenge_id = start_as(client, official).json()["challenge_id"]
    code = otp_outbox[-1][1]
    wrong = "000000" if code != "000000" else "111111"
    assert verify(client, challenge_id, wrong).status_code == 401
    assert client.get("/api/auth/me").status_code == 403


def test_account_locks_after_repeated_failures(app_db, client, official, otp_outbox):
    for _ in range(5):
        start_as(client, official, "wrong-password-123")
    assert start_as(client, official).status_code == 401  # even the right password
    official.refresh_from_db()
    assert official.locked_until is not None


def test_lockout_counts_per_account_whatever_the_identifier(app_db, client, trade, otp_outbox):
    # Different spellings of the same GSTIN all count against the one account.
    for spelling in (DEMO_GSTIN, DEMO_GSTIN.lower(), f" {DEMO_GSTIN}", DEMO_GSTIN, DEMO_GSTIN):
        start(client, "PARTY", spelling, "wrong-password-123")
    trade.seller.refresh_from_db()
    assert trade.seller.locked_until is not None
    assert start(client, "PARTY", DEMO_GSTIN).status_code == 401


def test_account_locks_after_too_many_code_requests(app_db, client, official, otp_outbox):
    for _ in range(5):
        assert start_as(client, official).status_code == 200
    assert start_as(client, official).status_code == 401
    official.refresh_from_db()
    assert official.locked_until is not None


def test_demo_mode_allows_30_code_requests_before_locking(app_db, official, otp_outbox, settings):
    # Presenters switch personas often; demo mode (localhost only) raises the cap to 30.
    from identity.login import start_login

    settings.DEMO_MODE = True
    for _ in range(30):
        assert start_login("LICENSING_AUTHORITY", OFFICIAL_EMAIL, TEST_PASSWORD) is not None
    assert start_login("LICENSING_AUTHORITY", OFFICIAL_EMAIL, TEST_PASSWORD) is None
    official.refresh_from_db()
    assert official.locked_until is not None


def test_wrong_passwords_still_lock_after_5_in_demo_mode(app_db, official, settings):
    from identity.login import start_login

    settings.DEMO_MODE = True
    for _ in range(5):
        assert start_login("LICENSING_AUTHORITY", OFFICIAL_EMAIL, "wrong-password") is None
    official.refresh_from_db()
    assert official.locked_until is not None


def test_login_is_rate_limited(app_db, client):
    statuses = [start(client, "PARTY", DEMO_GSTIN).status_code for _ in range(11)]
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429


def test_session_cookie_is_hardened(app_db, client, official, otp_outbox):
    response = api_login(client, official, otp_outbox)
    cookie = response.cookies["sessionid"]
    assert cookie["httponly"] is True
    assert cookie["secure"] is True
    assert cookie["samesite"] == "Strict"


def test_logout_ends_session(app_db, client, official, otp_outbox):
    api_login(client, official, otp_outbox)
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 403


def test_login_events_are_audited(app_db, client, official, otp_outbox, audit_actions):
    start_as(client, official, "wrong-password-123")
    api_login(client, official, otp_outbox)
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
            {"role": "PARTY", "identifier": DEMO_GSTIN, "password": TEST_PASSWORD},
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

    locked_user = make_user(role=Role.HEAD_AUTHORITY)
    locked_user.locked_until = timezone.now() + timedelta(minutes=15)
    locked_user.save(update_fields=["locked_until"])
    calls["count"] = 0
    start_as(client, locked_user)
    assert calls["count"] == 1

    inactive_user = make_user(role=Role.HEAD_AUTHORITY)
    inactive_user.is_active = False
    inactive_user.save(update_fields=["is_active"])
    calls["count"] = 0
    start_as(client, inactive_user)
    assert calls["count"] == 1


def test_login_requires_csrf_token(app_db, official):
    enforcing_client = Client(enforce_csrf_checks=True)

    no_token = enforcing_client.post(
        "/api/auth/login", login_body(official), content_type="application/json"
    )
    assert no_token.status_code == 403

    csrf_response = enforcing_client.get("/api/auth/csrf")
    token = csrf_response.cookies["csrftoken"].value
    with_token = enforcing_client.post(
        "/api/auth/login",
        login_body(official),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert with_token.status_code != 403


def test_locking_cancels_outstanding_login_code(app_db, client, official, otp_outbox):
    challenge_id = start_as(client, official).json()["challenge_id"]
    code = otp_outbox[-1][1]

    for _ in range(5):
        start_as(client, official, "wrong-password-123")

    assert verify(client, challenge_id, code).status_code == 401
    assert client.get("/api/auth/me").status_code == 403


def test_unknown_identifier_attempt_is_not_stored_in_plaintext(app_db, client):
    start(client, "HEAD_AUTHORITY", "secret.person@test.example")

    with transaction.atomic():
        set_actor(user_id="test", role=SYSTEM_ROLE)
        payloads = list(AuditEvent.objects.order_by("id").values_list("payload", flat=True))

    for payload in payloads:
        for value in (payload or {}).values():
            assert "secret.person" not in str(value).lower()


# --- Issued passwords must be changed first ------------------------------------------------------


@pytest.fixture
def issued(client, make_user, otp_outbox):
    """A Licensing Authority signed in with a password the system issued."""
    user = make_user(role=Role.LICENSING_AUTHORITY, must_change_password=True)
    verified = api_login(client, user, otp_outbox)
    assert verified.json()["must_change_password"] is True
    return user


GATED = {"detail": "Choose a new password before continuing.", "code": "password_change_required"}


@pytest.mark.parametrize("url", ["/api/home", "/api/licences", "/api/alerts", "/api/reason-codes"])
def test_the_gate_blocks_every_other_api(app_db, client, issued, url):
    response = client.get(url)
    assert response.status_code == 403
    assert response.json() == GATED


def test_the_gate_leaves_me_and_logout_open(app_db, client, issued):
    me = client.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["must_change_password"] is True
    assert client.get("/api/auth/csrf").status_code == 204
    assert client.get("/api/health").status_code == 200
    assert client.post("/api/auth/logout").status_code == 204


def test_the_gate_does_not_touch_other_users(app_db, client, official, otp_outbox):
    api_login(client, official, otp_outbox)
    assert client.get("/api/home").status_code == 200


def test_change_password_refuses_a_wrong_current_password(app_db, client, issued):
    response = change_password(client, current="not-my-password-1")
    assert response.status_code == 400
    assert set(response.json()) == {"current_password"}
    issued.refresh_from_db()
    assert issued.must_change_password is True


@pytest.mark.parametrize("weak", ["short", "123456789012345", TEST_PASSWORD])
def test_change_password_refuses_a_weak_or_unchanged_password(app_db, client, issued, weak):
    response = change_password(client, new=weak)
    assert response.status_code == 400
    assert set(response.json()) == {"new_password"}
    issued.refresh_from_db()
    assert issued.must_change_password is True and issued.check_password(TEST_PASSWORD)


def test_change_password_clears_the_flag_keeps_the_session_and_is_audited(
    app_db, client, issued, otp_outbox, audit_actions
):
    response = change_password(client)
    assert response.status_code == 200
    assert response.json() == {"must_change_password": False}
    issued.refresh_from_db()
    assert issued.must_change_password is False and issued.check_password(NEW_PASSWORD)
    # Still signed in, and now past the gate.
    assert client.get("/api/home").status_code == 200
    assert audit_actions()[-1] == "auth.password_changed"
    # The new password signs in; the old one no longer does.
    client.post("/api/auth/logout")
    assert start_as(client, issued).status_code == 401
    assert api_login(client, issued, otp_outbox, password=NEW_PASSWORD).status_code == 200


def test_change_password_needs_a_session(app_db, client):
    assert change_password(client).status_code == 403
