import pytest
from django.db import IntegrityError, transaction

from core.db_context import acting_as_system
from identity.models import User
from identity.roles import Role
from licensing.models import LicenceStatus
from licensing.service import set_status
from tests.conftest import DEMO_GSTIN

pytestmark = pytest.mark.django_db

STRONG = "a-strong-licensee-pass-7"
FAILED = {
    "detail": "We could not verify these details. "
    "Check the licence number and GSTIN exactly as printed on your licence."
}


def start(client, number, gstin=DEMO_GSTIN, **extra):
    return client.post(
        "/api/enrolment/start",
        {"licence_number": number, "gstin": gstin, **extra},
        content_type="application/json",
    )


def complete(client, challenge_id, code, password=STRONG):
    return client.post(
        "/api/enrolment/complete",
        {"challenge_id": challenge_id, "code": code, "password": password},
        content_type="application/json",
    )


def test_enrolment_creates_a_licensee_linked_to_the_gstin(app_db, client, make_licence, otp_outbox):
    licence = make_licence(contact="+919800000777")
    first = start(client, "GJ/TEST/0001")
    assert first.status_code == 200
    assert otp_outbox[-1][0] == "+919800000777"

    second = complete(client, first.json()["challenge_id"], otp_outbox[-1][1])
    assert second.status_code == 201
    user = User.objects.get(user_id=second.json()["user_id"])
    assert user.role == Role.LICENSEE
    assert user.licensee_gstin_index == licence.gstin_index
    assert user.get_contact() == "+919800000777"


def test_otp_always_goes_to_contact_on_file(app_db, client, make_licence, otp_outbox):
    make_licence(contact="+919800000777")
    start(client, "GJ/TEST/0001", contact="+919999999999")
    assert otp_outbox[-1][0] == "+919800000777"


def test_wrong_gstin_and_unknown_licence_look_identical(app_db, client, make_licence, otp_outbox):
    make_licence()
    wrong_gstin = start(client, "GJ/TEST/0001", gstin="99ZZZZZ9999Z1Z5")
    unknown = start(client, "GJ/NOPE/9999")
    assert wrong_gstin.status_code == unknown.status_code == 401
    assert wrong_gstin.json() == unknown.json() == FAILED
    assert otp_outbox == []


def test_suspended_licence_cannot_enrol(app_db, client, make_licence, otp_outbox):
    licence = make_licence()
    with acting_as_system("test"):
        set_status(licence, LicenceStatus.SUSPENDED, by="test", reason="inspection")
    assert start(client, "GJ/TEST/0001").json() == FAILED


def test_gstin_already_enrolled_cannot_enrol_again(app_db, client, make_licence, otp_outbox):
    make_licence()
    first = start(client, "GJ/TEST/0001")
    complete(client, first.json()["challenge_id"], otp_outbox[-1][1])
    assert start(client, "GJ/TEST/0001").json() == FAILED


def test_weak_password_is_rejected_without_using_up_the_otp(
    app_db, client, make_licence, otp_outbox
):
    make_licence()
    challenge_id = start(client, "GJ/TEST/0001").json()["challenge_id"]
    code = otp_outbox[-1][1]
    weak = complete(client, challenge_id, code, password="short")
    assert weak.status_code == 400
    assert "password" in weak.json()
    assert complete(client, challenge_id, code).status_code == 201


def test_wrong_code_does_not_enrol(app_db, client, make_licence, otp_outbox):
    make_licence()
    challenge_id = start(client, "GJ/TEST/0001").json()["challenge_id"]
    code = otp_outbox[-1][1]
    wrong = "000000" if code != "000000" else "111111"
    assert complete(client, challenge_id, wrong).status_code == 401
    assert not User.objects.filter(role=Role.LICENSEE).exists()


def test_enrolment_is_rate_limited(app_db, client):
    statuses = [start(client, "GJ/NOPE/9999").status_code for _ in range(11)]
    assert statuses[10] == 429


def test_enrolment_is_audited(app_db, client, make_licence, otp_outbox, audit_actions):
    make_licence()
    start(client, "GJ/NOPE/9999")
    first = start(client, "GJ/TEST/0001")
    complete(client, first.json()["challenge_id"], otp_outbox[-1][1])
    assert audit_actions()[-3:] == ["enrolment.failed", "enrolment.otp_sent", "enrolment.completed"]


def test_enrolment_uses_the_contact_of_the_licence_that_received_the_code(
    app_db, client, make_licence, otp_outbox
):
    make_licence(contact="+919800000111")
    second = make_licence(contact="+919800000222")
    first = start(client, "GJ/TEST/0002")
    assert otp_outbox[-1][0] == "+919800000222"
    done = complete(client, first.json()["challenge_id"], otp_outbox[-1][1])
    assert done.status_code == 201
    assert User.objects.get(user_id=done.json()["user_id"]).get_contact() == second.contact()


def test_database_allows_one_account_per_gstin(app_db, make_user):
    User.objects.create_user(
        role=Role.LICENSEE,
        password="x-strong-pass-9",
        contact="+919800000001",
        licensee_gstin_index="abc",
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create_user(
            role=Role.LICENSEE,
            password="x-strong-pass-9",
            contact="+919800000002",
            licensee_gstin_index="abc",
        )
