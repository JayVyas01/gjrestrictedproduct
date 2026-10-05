"""Demo mode: fenced off from production, an SMS inbox for codes, and a persona list."""

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, transaction
from django.test import override_settings

from config.checks import DEMO_MODE_MESSAGE, DEMO_SENDER, demo_mode_problems
from demo.dataset import PERSONAS
from demo.models import DemoInboxMessage, DemoPersona
from demo.sender import DemoInboxOtpSender
from identity import otp
from identity.models import OtpPurpose
from identity.otp_delivery import ConsoleOtpSender, OutboxOtpSender
from identity.roles import Role
from positions.service import assign

pytestmark = pytest.mark.django_db

BACKEND = Path(__file__).resolve().parent.parent
DEMO = {"DEMO_MODE": True, "OTP_SENDER": DEMO_SENDER, "DEMO_PASSWORD": "demo-password-2026"}


def good_settings(**overrides):
    values = dict(
        DEMO_MODE=True,
        ALLOWED_HOSTS=["localhost", "127.0.0.1", "[::1]"],
        SECURE_SSL_REDIRECT=False,
        OTP_SENDER=DEMO_SENDER,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


# --- The startup guard --------------------------------------------------------------------


def test_guard_accepts_localhost_with_the_inbox_sender():
    assert demo_mode_problems(good_settings()) == []


def test_guard_ignores_everything_when_demo_mode_is_off():
    off = good_settings(
        DEMO_MODE=False,
        ALLOWED_HOSTS=["permits.gujarat.gov.in"],
        SECURE_SSL_REDIRECT=True,
        OTP_SENDER="identity.otp_delivery.ConsoleOtpSender",
    )
    assert demo_mode_problems(off) == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"ALLOWED_HOSTS": ["localhost", "permits.example.in"]},
        {"ALLOWED_HOSTS": ["*"]},
        {"ALLOWED_HOSTS": [".localhost"]},
        {"ALLOWED_HOSTS": ["0.0.0.0"]},  # noqa: S104 - a host name under test, not a bind
        {"SECURE_SSL_REDIRECT": True},
        {"OTP_SENDER": "identity.otp_delivery.ConsoleOtpSender"},
        {"OTP_SENDER": "identity.otp_delivery.OutboxOtpSender"},
    ],
)
def test_guard_reports_each_bad_combination(overrides):
    assert len(demo_mode_problems(good_settings(**overrides))) == 1


def test_guard_reports_every_problem_at_once():
    bad = good_settings(
        ALLOWED_HOSTS=["example.in"], SECURE_SSL_REDIRECT=True, OTP_SENDER="x.Sender"
    )
    assert len(demo_mode_problems(bad)) == 3


def _start_settings(**env):
    environment = {**os.environ, **env}
    return subprocess.run(  # noqa: S603 - fixed interpreter and code, test-controlled env
        [sys.executable, "-c", "import config.settings"],
        cwd=BACKEND,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_settings_refuse_to_load_demo_mode_on_a_real_host():
    result = _start_settings(
        DEMO_MODE="1", DJANGO_ALLOWED_HOSTS="permits.example.in", OTP_SENDER=DEMO_SENDER
    )
    assert result.returncode != 0
    assert "ImproperlyConfigured" in result.stderr
    assert DEMO_MODE_MESSAGE in result.stderr


def test_settings_load_in_demo_mode_on_localhost():
    result = _start_settings(
        DEMO_MODE="1",
        DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1",
        DJANGO_SSL_REDIRECT="0",
        OTP_SENDER=DEMO_SENDER,
    )
    assert result.returncode == 0, result.stderr


def test_demo_mode_is_off_unless_set(settings):
    assert settings.DEMO_MODE is False


def test_system_check_reports_the_guard_message():
    from config.checks import demo_mode_check

    with override_settings(DEMO_MODE=True, SECURE_SSL_REDIRECT=True, OTP_SENDER=DEMO_SENDER):
        errors = demo_mode_check(None)
    assert [error.msg for error in errors] == [DEMO_MODE_MESSAGE]
    with override_settings(DEMO_MODE=False):
        assert demo_mode_check(None) == []


# --- Demo endpoints are dead outside demo mode -----------------------------------------------


@pytest.mark.parametrize("url", ["/api/demo/inbox", "/api/demo/personas"])
def test_endpoints_404_when_demo_mode_is_off(app_db, client, url):
    with override_settings(DEMO_MODE=False):
        response = client.get(url)
    assert response.status_code == 404
    assert response.json() == {"detail": "Not found."}


@pytest.mark.parametrize("url", ["/api/demo/inbox", "/api/demo/personas"])
def test_endpoints_are_read_only(app_db, client, url):
    with override_settings(**DEMO):
        assert client.post(url, {}, content_type="application/json").status_code == 405


def test_sender_refuses_outside_demo_mode(app_db):
    with override_settings(DEMO_MODE=False), pytest.raises(ImproperlyConfigured):
        DemoInboxOtpSender().send("+919800000001", "123456")
    assert DemoInboxMessage.objects.count() == 0


# --- Senders accept the optional user id -----------------------------------------------------


def test_outbox_and_console_senders_accept_the_user_id(otp_outbox, capsys):
    OutboxOtpSender().send("+919800000001", "123456", user_id="GJABCDEFGHJK")
    assert otp_outbox[-1] == ("+919800000001", "123456")
    with override_settings(DEBUG=True):
        ConsoleOtpSender().send("+919800000001", "654321", user_id="GJABCDEFGHJK")
    assert "654321" in capsys.readouterr().out


# --- The SMS inbox ---------------------------------------------------------------------------


def _login_start(client, user):
    from tests.conftest import TEST_PASSWORD

    return client.post(
        "/api/auth/login",
        {"user_id": user.user_id, "password": TEST_PASSWORD},
        content_type="application/json",
    )


def test_login_code_lands_in_the_inbox_with_name_and_last4(app_db, client, trade):
    with override_settings(**DEMO):
        assert _login_start(client, trade.seller).status_code == 200
        inbox = client.get("/api/demo/inbox")
    assert inbox.status_code == 200
    [message] = inbox.json()
    assert message["display_name"] == "Sanand Spirits Pvt Ltd"
    assert message["contact_last4"] == "0201"
    assert len(message["code"]) == 6 and message["code"].isdigit()
    assert set(message) == {"display_name", "contact_last4", "code", "created_at"}
    row = DemoInboxMessage.objects.get()
    assert row.user_id == trade.seller.user_id
    stored = [str(value) for value in DemoInboxMessage.objects.values_list().get()]
    assert not any("+919800000201" in value or "9800000201" in value for value in stored)


def test_the_inbox_code_completes_the_login(app_db, client, trade):
    with override_settings(**DEMO):
        challenge_id = _login_start(client, trade.buyer).json()["challenge_id"]
        code = client.get("/api/demo/inbox").json()[0]["code"]
        verified = client.post(
            "/api/auth/login/verify",
            {"challenge_id": challenge_id, "code": code},
            content_type="application/json",
        )
    assert verified.status_code == 200


def test_display_names_for_personnel_other_roles_and_enrolment(app_db, org, make_user):
    officer = make_user(role=Role.PERSONNEL, contact="+919800010001")
    assign(org.area_officer, officer, by="test")
    unassigned = make_user(role=Role.PERSONNEL, contact="+919800010002")
    authority = make_user(role=Role.LICENSING_AUTHORITY, contact="+919800010003")
    with override_settings(**DEMO):
        for user in (officer, unassigned, authority):
            otp.issue(user, OtpPurpose.LOGIN)
        otp.issue_for_subject(subject="licence:1", contact="+919800010004", purpose="ENROL")
    names = list(
        DemoInboxMessage.objects.order_by("id").values_list(
            "display_name", "contact_last4", "user_id"
        )
    )
    assert names == [
        ("Area Officer, Sanand", "0001", officer.user_id),
        ("Unassigned officer", "0002", unassigned.user_id),
        ("Licensing Authority", "0003", authority.user_id),
        ("Enrolment", "0004", ""),
    ]


def test_inbox_lists_newest_first_and_at_most_twenty(app_db, client):
    with override_settings(**DEMO):
        sender = DemoInboxOtpSender()
        for number in range(25):
            sender.send(f"+91980000{number:04d}", f"{number:06d}")
        inbox = client.get("/api/demo/inbox").json()
    assert len(inbox) == 20
    assert [message["code"] for message in inbox] == [f"{n:06d}" for n in range(24, 4, -1)]
    assert inbox[0]["created_at"] >= inbox[-1]["created_at"]


# --- The persona list ------------------------------------------------------------------------


def test_personas_are_listed_in_the_fixed_order_with_the_password(app_db, client, make_user):
    for persona in reversed(PERSONAS):
        DemoPersona.objects.create(key=persona.key, user_id=make_user().user_id)
    with override_settings(**DEMO):
        response = client.get("/api/demo/personas")
    assert response.status_code == 200
    body = response.json()
    assert [entry["key"] for entry in body] == [persona.key for persona in PERSONAS]
    assert [entry["label"] for entry in body] == [
        "Seller",
        "Buyer",
        "Area Officer (Sanand)",
        "Superintendent (Ahmedabad)",
        "Licensing Authority",
        "Head Authority A",
        "Head Authority B",
    ]
    stored = dict(DemoPersona.objects.values_list("key", "user_id"))
    for entry in body:
        assert set(entry) == {"key", "label", "description", "user_id", "password"}
        assert entry["user_id"] == stored[entry["key"]]
        assert entry["password"] == "demo-password-2026"
        assert entry["description"]


def test_personas_not_yet_seeded_are_left_out(app_db, client, make_user):
    DemoPersona.objects.create(key="buyer", user_id=make_user().user_id)
    with override_settings(**DEMO):
        body = client.get("/api/demo/personas").json()
    assert [entry["key"] for entry in body] == ["buyer"]


def test_persona_keys_are_unique(app_db, make_user):
    DemoPersona.objects.create(key="seller", user_id=make_user().user_id)
    with pytest.raises(DatabaseError), transaction.atomic():
        DemoPersona.objects.create(key="seller", user_id=make_user().user_id)


# --- Append-only for the app role --------------------------------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE demo_demoinboxmessage SET code = '000000'",
        "DELETE FROM demo_demoinboxmessage",
        "TRUNCATE demo_demoinboxmessage",
        "UPDATE demo_demopersona SET user_id = 'GJX'",
        "DELETE FROM demo_demopersona",
        "TRUNCATE demo_demopersona",
    ],
)
def test_demo_tables_reject_update_and_delete_for_the_app_role(app_db, sql):
    from django.db import connection

    with override_settings(**DEMO):
        DemoInboxOtpSender().send("+919800000001", "123456")
    with pytest.raises(DatabaseError, match="permission denied"), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(sql)
