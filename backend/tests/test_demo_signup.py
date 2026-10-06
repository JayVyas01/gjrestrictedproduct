"""Demo party sign-up (A4, A5): a GSTIN plus the phone on file of an ACTIVE licence, then the
code sent to that phone. Every licence of the GSTIN, and so its stock, joins the account.
Passwords are kept in plain text nowhere; the demo-only DemoCredential holds them encrypted."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import DatabaseError, connection, transaction
from django.test import override_settings

from audit.models import AuditEvent
from core import crypto
from core.db_context import acting_as_system
from demo.models import DemoCredential, DemoPendingSignup, DemoPersona
from demo.signup import phones_match
from identity.models import User
from identity.roles import Role
from licensing.models import LicenceStatus
from licensing.service import set_status
from stock.service import set_opening_balance
from tests.conftest import BUYER_GSTIN, DEMO_GSTIN, TEST_PASSWORD, api_login

pytestmark = pytest.mark.django_db

DEMO = {"DEMO_MODE": True, "DEMO_PASSWORD": "demo-password-2026"}
CHOSEN = "my-own-signup-pass-42"
FAILED = {"detail": "We couldn't match those details to a licensed business."}
ON_FILE = "+919800000777"


def form(**overrides):
    values = {
        "gstin": DEMO_GSTIN,
        "phone": ON_FILE,
        "email": "Owner@Sanand-Traders.example",
        "business_name": "Sanand Test Traders",
        "address": "12 Station Road, Sanand",
        "password": CHOSEN,
    }
    values.update(overrides)
    return values


def start(client, **overrides):
    with override_settings(**DEMO):
        return client.post("/api/demo/signup/start", form(**overrides), "application/json")


def complete(client, challenge_id, code):
    with override_settings(**DEMO):
        return client.post(
            "/api/demo/signup/complete",
            {"challenge_id": challenge_id, "code": code},
            "application/json",
        )


def signed_up(client, otp_outbox, **overrides) -> User:
    challenge_id = start(client, **overrides).json()["challenge_id"]
    done = complete(client, challenge_id, otp_outbox[-1][1])
    assert done.status_code == 201, done.content
    return User.objects.get(user_id=done.json()["user_id"])


# --- Phone comparison ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "typed", ["+919800000777", "9800000777", "919800000777", "+91 98000-00777", " 98000 00777 "]
)
def test_phones_match_on_the_last_ten_digits(typed):
    assert phones_match(typed, ON_FILE)


@pytest.mark.parametrize("typed", ["9800000778", "800000777", "", "+91"])
def test_other_phones_do_not_match(typed):
    assert not phones_match(typed, ON_FILE)


# --- Start -----------------------------------------------------------------------------------


def test_a_match_sends_the_code_to_the_contact_on_file(app_db, client, make_licence, otp_outbox):
    make_licence(contact=ON_FILE)
    response = start(client, phone="98000 00777")
    assert response.status_code == 200
    assert set(response.json()) == {"challenge_id"}
    assert [contact for contact, _ in otp_outbox] == [ON_FILE]
    pending = DemoPendingSignup.objects.get()
    assert str(pending.challenge_public_id) == response.json()["challenge_id"]
    assert pending.gstin_index == crypto.blind_index("gstin", DEMO_GSTIN)


def test_the_gstin_is_normalised(app_db, client, make_licence, otp_outbox):
    make_licence(contact=ON_FILE)
    assert start(client, gstin=f" {DEMO_GSTIN.lower()} ").status_code == 200


def test_any_active_licence_of_the_gstin_can_prove_ownership(
    app_db, client, make_licence, otp_outbox
):
    make_licence(contact="+919800000111")
    make_licence(contact="+919800000222")
    assert start(client, phone="9800000222").status_code == 200
    assert otp_outbox[-1][0] == "+919800000222"


def _suspend(licence):
    with acting_as_system("test"):
        set_status(licence, LicenceStatus.SUSPENDED, by="test", reason="inspection")


@pytest.mark.parametrize("case", ["wrong_phone", "unknown_gstin", "signed_up", "suspended_only"])
def test_every_failure_looks_the_same(
    app_db, client, make_licence, make_licensee, otp_outbox, audit_actions, case
):
    licence = make_licence(contact=ON_FILE)
    overrides = {}
    if case == "wrong_phone":
        overrides["phone"] = "+919800000999"
    elif case == "unknown_gstin":
        overrides["gstin"] = BUYER_GSTIN
    elif case == "signed_up":
        make_licensee(licence)
    else:
        _suspend(licence)
    response = start(client, **overrides)
    assert response.status_code == 401
    assert response.json() == FAILED
    assert otp_outbox == []
    assert not DemoPendingSignup.objects.exists()
    assert audit_actions()[-1] == "signup.failed"


def test_a_suspended_licence_does_not_prove_ownership_even_with_an_active_one(
    app_db, client, make_licence, otp_outbox
):
    _suspend(make_licence(contact="+919800000111"))
    make_licence(contact="+919800000222")
    assert start(client, phone="9800000111").json() == FAILED
    assert start(client, phone="9800000222").status_code == 200


def test_an_email_already_in_use_fails_the_same_way(
    app_db, client, make_licence, make_user, otp_outbox
):
    make_licence(contact=ON_FILE)
    make_user(role=Role.HEAD_AUTHORITY, email="owner@sanand-traders.example")
    assert start(client).json() == FAILED
    assert otp_outbox == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("gstin", "NOT-A-GSTIN"),
        ("email", "not-an-email"),
        ("business_name", ""),
        ("business_name", "x" * 201),
        ("address", ""),
        ("address", "x" * 501),
        ("password", "short"),
        ("password", "password"),
        ("phone", "12345"),
    ],
)
def test_bad_fields_are_400_before_any_matching(
    app_db, client, make_licence, otp_outbox, audit_actions, field, value
):
    make_licence(contact=ON_FILE)
    response = start(client, **{field: value})
    assert response.status_code == 400
    assert field in response.json()
    assert otp_outbox == []
    assert "signup.failed" not in audit_actions()


def test_failures_and_codes_are_audited_by_blind_index_only(
    app_db, client, make_licence, otp_outbox, audit_actions
):
    make_licence(contact=ON_FILE)
    start(client, phone="9800000999")
    start(client)
    assert audit_actions()[-2:] == ["signup.failed", "signup.otp_sent"]
    with acting_as_system("test"):
        stored = str(list(AuditEvent.objects.values_list("payload", "subject_id")))
    assert crypto.blind_index("gstin", DEMO_GSTIN) in stored
    for secret in (DEMO_GSTIN, "9800000999", "9800000777", "sanand-traders", CHOSEN):
        assert secret.lower() not in stored.lower()


def test_start_is_rate_limited_with_enrolment(app_db, client):
    statuses = [start(client, gstin=BUYER_GSTIN).status_code for _ in range(11)]
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429


# --- Complete --------------------------------------------------------------------------------


def test_complete_links_every_licence_and_its_stock(
    app_db, client, catalogue, make_licence, otp_outbox, audit_actions
):
    first = make_licence(contact=ON_FILE)
    make_licence(contact="+919800000888", licence_type=catalogue.wholesale)
    with acting_as_system("test"):
        set_opening_balance(
            gstin_index=first.gstin_index,
            substance=catalogue.whisky,
            quantity=Decimal("380"),
            by="test",
        )
    user = signed_up(client, otp_outbox)
    assert user.role == Role.LICENSEE
    assert user.licensee_gstin_index == first.gstin_index
    assert user.get_contact() == ON_FILE
    assert user.get_email() == "owner@sanand-traders.example"
    assert user.get_address() == "12 Station Road, Sanand"
    assert user.must_change_password is False
    assert user.check_password(CHOSEN)
    assert audit_actions()[-1] == "signup.completed"
    assert not DemoPendingSignup.objects.exists()

    assert api_login(client, user, otp_outbox, password=CHOSEN).status_code == 200
    licences = client.get("/api/licences/mine").json()
    assert [card["licence_number"] for card in licences] == ["GJ/TEST/0001", "GJ/TEST/0002"]
    stock = client.get("/api/stock/mine").json()
    assert [(row["substance_code"], row["quantity"]) for row in stock] == [("WHISKY", "380.000")]


def test_the_account_uses_the_contact_of_the_licence_that_matched(
    app_db, client, make_licence, otp_outbox
):
    make_licence(contact="+919800000111")
    make_licence(contact="+919800000222")
    user = signed_up(client, otp_outbox, phone="9800000222")
    assert user.get_contact() == "+919800000222"


def test_the_password_is_stored_in_plain_text_nowhere(app_db, client, make_licence, otp_outbox):
    make_licence(contact=ON_FILE)
    challenge_id = start(client).json()["challenge_id"]
    pending = [str(value) for value in DemoPendingSignup.objects.values_list().get()]
    for secret in (CHOSEN, "owner@sanand-traders.example", "12 Station Road"):
        assert not any(secret.lower() in value.lower() for value in pending)
    complete(client, challenge_id, otp_outbox[-1][1])

    with acting_as_system("test"):
        users = [str(value) for value in User.objects.values_list()]
        audit = [str(value) for value in AuditEvent.objects.values_list()]
    credential = DemoCredential.objects.get()
    for value in [*users, *audit, *map(str, DemoCredential.objects.values_list().get())]:
        assert CHOSEN not in value
    assert credential.password() == CHOSEN


def test_a_wrong_code_creates_nothing(app_db, client, make_licence, otp_outbox):
    make_licence(contact=ON_FILE)
    challenge_id = start(client).json()["challenge_id"]
    wrong = "000000" if otp_outbox[-1][1] != "000000" else "111111"
    response = complete(client, challenge_id, wrong)
    assert response.status_code == 401
    assert response.json() == FAILED
    assert not User.objects.filter(role=Role.LICENSEE).exists()
    assert not DemoCredential.objects.exists()


def test_a_newer_start_replaces_the_pending_sign_up(app_db, client, make_licence, otp_outbox):
    make_licence(contact=ON_FILE)
    old = start(client).json()["challenge_id"]
    old_code = otp_outbox[-1][1]
    new = start(client, email="second@sanand-traders.example").json()["challenge_id"]
    assert DemoPendingSignup.objects.count() == 1
    assert complete(client, old, old_code).status_code == 401
    assert complete(client, new, otp_outbox[-1][1]).status_code == 201


def test_a_stale_pending_sign_up_is_ignored(app_db, client, make_licence, otp_outbox):
    make_licence(contact=ON_FILE)
    challenge_id = start(client).json()["challenge_id"]
    with connection.cursor() as cursor:  # as the owner: the app role may not UPDATE these rows
        cursor.execute("RESET ROLE")
        DemoPendingSignup.objects.update(
            created_at=DemoPendingSignup.objects.get().created_at - timedelta(minutes=6)
        )
        cursor.execute("SET ROLE gj_app")
    assert complete(client, challenge_id, otp_outbox[-1][1]).status_code == 401
    assert not User.objects.filter(role=Role.LICENSEE).exists()


def test_the_licence_suspended_before_the_code_is_entered_fails(
    app_db, client, make_licence, otp_outbox
):
    licence = make_licence(contact=ON_FILE)
    challenge_id = start(client).json()["challenge_id"]
    _suspend(licence)
    assert complete(client, challenge_id, otp_outbox[-1][1]).status_code == 401


def test_an_enrolment_code_cannot_complete_a_sign_up(app_db, client, make_licence, otp_outbox):
    make_licence(contact=ON_FILE)
    enrolment = client.post(
        "/api/enrolment/start",
        {"licence_number": "GJ/TEST/0001", "gstin": DEMO_GSTIN},
        "application/json",
    ).json()["challenge_id"]
    assert complete(client, enrolment, otp_outbox[-1][1]).status_code == 401


# --- Candidates ------------------------------------------------------------------------------


def test_candidates_list_licensed_gstins_without_an_account(
    app_db, client, make_licence, make_licensee, otp_outbox
):
    make_licence(contact=ON_FILE, holder_name="Sanand Test Traders")
    make_licence(contact="+919800000778")  # a second licence: still one candidate
    signed = make_licence(gstin=BUYER_GSTIN, holder_name="Bopal Buyers")
    make_licensee(signed)
    suspended = make_licence(gstin="99CCCCC2222C1Z5", holder_name="Closed Co")
    _suspend(suspended)
    with override_settings(**DEMO):
        response = client.get("/api/demo/signup/candidates")
    assert response.status_code == 200
    assert response.json() == [
        {"gstin": DEMO_GSTIN, "business_name": "Sanand Test Traders", "phone_on_file": ON_FILE}
    ]


# --- Demo mode only --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("post", "/api/demo/signup/start"),
        ("post", "/api/demo/signup/complete"),
        ("get", "/api/demo/signup/candidates"),
    ],
)
def test_everything_is_404_outside_demo_mode(app_db, client, make_licence, otp_outbox, method, url):
    make_licence(contact=ON_FILE)
    with override_settings(DEMO_MODE=False):
        response = getattr(client, method)(url, form(), "application/json")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not found."}
    assert otp_outbox == []


# --- DemoCredential: personas and password changes -------------------------------------------


def test_personas_read_the_password_from_demo_credential(app_db, client, make_user):
    changed = make_user(role=Role.HEAD_AUTHORITY, email="a@demo.gujarat.example")
    seeded = make_user(role=Role.HEAD_AUTHORITY, email="b@demo.gujarat.example")
    DemoPersona.objects.create(key="seller", user_id=changed.user_id)
    DemoPersona.objects.create(key="buyer", user_id=seeded.user_id)
    DemoCredential.store(changed.user_id, "a-changed-password-1")
    with override_settings(**DEMO):
        body = {entry["key"]: entry for entry in client.get("/api/demo/personas").json()}
    assert body["seller"]["password"] == "a-changed-password-1"
    assert body["buyer"]["password"] == "demo-password-2026"  # fallback: no row yet


def _change_password(client, new):
    return client.post(
        "/api/auth/password",
        {"current_password": TEST_PASSWORD, "new_password": new},
        "application/json",
    )


def test_a_password_change_updates_demo_credential_in_demo_mode(
    app_db, client, make_user, otp_outbox
):
    user = make_user(role=Role.HEAD_AUTHORITY)
    DemoCredential.store(user.user_id, TEST_PASSWORD)
    with override_settings(**DEMO):
        api_login(client, user, otp_outbox)
        assert _change_password(client, "a-fresh-head-pass-77").status_code == 200
    assert DemoCredential.objects.get(user_id=user.user_id).password() == "a-fresh-head-pass-77"


def test_a_password_change_writes_no_credential_outside_demo_mode(
    app_db, client, make_user, otp_outbox
):
    user = make_user(role=Role.HEAD_AUTHORITY)
    api_login(client, user, otp_outbox)
    assert _change_password(client, "a-fresh-head-pass-77").status_code == 200
    assert not DemoCredential.objects.exists()


# --- Privileges of the app role ---------------------------------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE demo_demopendingsignup SET business_name = 'x'",
        "TRUNCATE demo_demopendingsignup",
        "DELETE FROM demo_democredential",
        "TRUNCATE demo_democredential",
    ],
)
def test_demo_signup_tables_limit_the_app_role(app_db, sql):
    with pytest.raises(DatabaseError, match="permission denied"), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(sql)
