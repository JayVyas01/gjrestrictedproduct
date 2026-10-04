"""Review-settings API (B8): authorities read every district position's review period; only the
Licensing Authority changes it (D2d Task 5)."""

from datetime import date

import pytest
from django.db import transaction
from django.test import Client

from audit.models import AuditEvent
from core.db_context import SYSTEM_ROLE, acting_as_system, set_actor
from identity.roles import Role
from oversight.models import SuperintendentSetting
from oversight.service import create_due_batches, review_settings_overview
from positions.models import Area, AreaLevel, Position
from tests.conftest import TEST_PASSWORD
from tests.test_transaction_api import login

pytestmark = pytest.mark.django_db

URL = "/api/oversight/review-settings"


def put(client, position_id, body):
    return client.put(f"{URL}/{position_id}", body, content_type="application/json")


@pytest.fixture
def surat(org):
    area = Area.objects.create(
        code="GJ-SRT", name="Surat", level=AreaLevel.DISTRICT, parent=org.state
    )
    return Position.objects.create(code="DO-SRT", title="District Officer, Surat", area=area)


def test_overview_lists_every_district_position(
    app_db, client, org, surat, review_setting, make_user, otp_outbox
):
    with acting_as_system("test"):
        create_due_batches(date(2026, 6, 16))  # one batch: 1-15 June
    with acting_as_system("test"):
        rows = review_settings_overview(date(2026, 6, 20))
    assert rows == [
        {
            "position_id": org.district_officer.id,
            "title": "District Officer, Ahmedabad",
            "area": "Ahmedabad",
            "period_days": 15,
            "starts_on": date(2026, 6, 1),
            "current_period_end": date(2026, 6, 30),
            "last_batch_end": date(2026, 6, 15),
        },
        {
            "position_id": surat.id,
            "title": "District Officer, Surat",
            "area": "Surat",
            "period_days": None,
            "starts_on": None,
            "current_period_end": None,
            "last_batch_end": None,
        },
    ]  # the taluka (Area Officer) position is not listed
    with acting_as_system("test"):
        [before_start, _] = review_settings_overview(date(2026, 5, 31))
    assert before_start["current_period_end"] is None

    # The Licensing Authority cannot read batches under RLS, but still sees the dates.
    login(client, make_user(role=Role.LICENSING_AUTHORITY), otp_outbox)
    [ahmedabad, _] = client.get(URL).json()
    assert ahmedabad["last_batch_end"] == "2026-06-15"
    assert ahmedabad["starts_on"] == "2026-06-01"


@pytest.mark.parametrize(
    "role,may_read,may_change",
    [
        (Role.LICENSING_AUTHORITY, True, True),
        (Role.HEAD_AUTHORITY, True, False),
        (Role.SOFTWARE_OWNER, True, False),
        (Role.PERSONNEL, False, False),
        (Role.LICENSEE, False, False),
    ],
)
def test_only_licensing_authority_can_change(
    app_db, client, org, make_user, otp_outbox, role, may_read, may_change
):
    login(client, make_user(role=role), otp_outbox)
    assert client.get(URL).status_code == (200 if may_read else 403)
    response = put(client, org.district_officer.id, {"period_days": 30})
    assert response.status_code == (200 if may_change else 403)
    assert SuperintendentSetting.objects.exists() is may_change


def test_change_is_saved_and_audited(app_db, client, org, review_setting, make_user, otp_outbox):
    la = make_user(role=Role.LICENSING_AUTHORITY)
    login(client, la, otp_outbox)
    response = put(client, org.district_officer.id, {"period_days": 30, "starts_on": "2026-05-01"})
    assert response.status_code == 200
    body = response.json()
    assert body["position_id"] == org.district_officer.id
    assert body["period_days"] == 30 and body["starts_on"] == "2026-05-01"
    setting = SuperintendentSetting.objects.get(position=org.district_officer)
    assert (setting.period_days, setting.starts_on) == (30, date(2026, 5, 1))
    with transaction.atomic():
        set_actor(user_id="test", role=SYSTEM_ROLE)
        event = AuditEvent.objects.filter(action="oversight.review_period_set").latest("id")
    assert event.actor == la.user_id
    assert event.payload == {"period_days": 30, "starts_on": "2026-05-01"}


@pytest.mark.parametrize(
    "position,body,reason",
    [
        ("district_officer", {"period_days": 20}, "The review period must be 15, 30 or 60 days."),
        (
            "area_officer",
            {"period_days": 15},
            "Review periods can only be set for a district superintendent position.",
        ),
        (
            "district_officer",
            {"period_days": 15, "starts_on": "2026-07-01"},
            "The new period cannot start after 2026-06-01, "
            "or transactions in between would never be reviewed.",
        ),
    ],
)
def test_invalid_period_is_422_with_reasons(
    app_db, client, org, review_setting, make_user, otp_outbox, position, body, reason
):
    login(client, make_user(role=Role.LICENSING_AUTHORITY), otp_outbox)
    response = put(client, getattr(org, position).id, body)
    assert response.status_code == 422
    assert response.json() == {"detail": "This review period can't be saved.", "reasons": [reason]}
    setting = SuperintendentSetting.objects.get(position=org.district_officer)
    assert (setting.period_days, setting.starts_on) == (15, date(2026, 6, 1))


def test_bad_types_are_400(app_db, client, org, make_user, otp_outbox):
    login(client, make_user(role=Role.LICENSING_AUTHORITY), otp_outbox)
    assert put(client, org.district_officer.id, {"period_days": "soon"}).status_code == 400
    assert put(client, org.district_officer.id, {}).status_code == 400
    bad_date = {"period_days": 15, "starts_on": "next week"}
    assert put(client, org.district_officer.id, bad_date).status_code == 400


def test_unknown_position_is_404(app_db, client, make_user, otp_outbox):
    login(client, make_user(role=Role.LICENSING_AUTHORITY), otp_outbox)
    response = put(client, 999999, {"period_days": 15})
    assert response.status_code == 404
    assert response.json() == {"detail": "Position not found."}


def test_change_requires_csrf(app_db, org, make_user, otp_outbox):
    la = make_user(role=Role.LICENSING_AUTHORITY)
    c = Client(enforce_csrf_checks=True)
    token = c.get("/api/auth/csrf").cookies["csrftoken"].value
    first = c.post(
        "/api/auth/login",
        {"user_id": la.user_id, "password": TEST_PASSWORD},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    c.post(
        "/api/auth/login/verify",
        {"challenge_id": first.json()["challenge_id"], "code": otp_outbox[-1][1]},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    token = c.cookies["csrftoken"].value
    assert put(c, org.district_officer.id, {"period_days": 15}).status_code == 403
    assert not SuperintendentSetting.objects.exists()
    saved = c.put(
        f"{URL}/{org.district_officer.id}",
        {"period_days": 15},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert saved.status_code == 200
