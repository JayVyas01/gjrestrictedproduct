"""The licence register for authorities: exact search, filters, detail, audit (D2d Task 4).
The exact search moved to a POST body in D3 Task 9, so no number or GSTIN is in a URL."""

from datetime import date
from decimal import Decimal

import pytest
from django.db import transaction
from django.test import Client

from audit.models import AuditEvent
from core import crypto
from core.db_context import SYSTEM_ROLE, acting_as_system, set_actor
from identity.roles import Role
from licensing.service import set_status
from licensing.views import LicenceSearchView
from stock.service import set_opening_balance
from tests.conftest import BUYER_GSTIN, DEMO_GSTIN, TEST_PASSWORD
from tests.test_transaction_api import login, post

pytestmark = pytest.mark.django_db

UNKNOWN_FILTER = {"detail": "Unknown filter value."}
SEARCH = "/api/licences/search"


def search(client, **body):
    return post(client, SEARCH, body)


def events(action):
    with transaction.atomic():
        set_actor(user_id="test", role=SYSTEM_ROLE)
        return list(
            AuditEvent.objects.filter(action=action)
            .order_by("id")
            .values("actor", "subject_type", "subject_id", "payload")
        )


@pytest.mark.parametrize(
    "role,allowed",
    [
        (Role.LICENSING_AUTHORITY, True),
        (Role.HEAD_AUTHORITY, True),
        (Role.SOFTWARE_OWNER, True),
        (Role.LICENSEE, False),
        (Role.PERSONNEL, False),
    ],
)
def test_only_authorities_can_use_register(
    app_db, client, make_licence, make_user, otp_outbox, role, allowed
):
    licence = make_licence()
    login(client, make_user(role=role), otp_outbox)
    expected = 200 if allowed else 403
    assert client.get("/api/licences").status_code == expected
    assert client.get(f"/api/licences/{licence.id}").status_code == expected
    assert search(client, number="GJ/TEST/0001").status_code == expected


def test_mine_still_routes_to_my_licences(app_db, client, make_user, otp_outbox):
    login(client, make_user(role=Role.HEAD_AUTHORITY), otp_outbox)
    assert client.get("/api/licences/mine").status_code == 403  # licensee-only view, not detail


def test_exact_search_by_number_and_gstin(app_db, client, make_licence, make_user, otp_outbox):
    first = make_licence()  # GJ/TEST/0001, DEMO_GSTIN
    make_licence(gstin=BUYER_GSTIN)  # GJ/TEST/0002
    login(client, make_user(role=Role.LICENSING_AUTHORITY), otp_outbox)

    body = search(client, number="  gj/test/0001 ").json()
    assert body["count"] == 1 and body["page"] == 1 and body["page_size"] == 25
    assert [row["id"] for row in body["results"]] == [first.id]

    body = search(client, gstin=DEMO_GSTIN.lower() + " ").json()
    assert [row["id"] for row in body["results"]] == [first.id]

    assert search(client, number="GJ/TEST/000").json()["count"] == 0
    assert search(client, gstin=DEMO_GSTIN[:10]).json()["count"] == 0
    # The filters combine with the exact match.
    assert search(client, number="GJ/TEST/0001", status="SUSPENDED").json()["count"] == 0
    # A blank search is the plain listing.
    assert search(client, number="", gstin="").json()["count"] == 2


def test_search_values_are_never_taken_from_the_url(
    app_db, client, make_licence, make_user, otp_outbox
):
    """A licence number or GSTIN in a URL ends up in server and proxy logs: GET refuses them."""
    make_licence()
    login(client, make_user(role=Role.LICENSING_AUTHORITY), otp_outbox)
    for params in ({"number": "GJ/TEST/0001"}, {"gstin": DEMO_GSTIN}, {"number": ""}):
        response = client.get("/api/licences", params)
        assert response.status_code == 400 and response.json() == UNKNOWN_FILTER
    assert events("licence.register_search") == []


def test_search_checks_its_filters(app_db, client, org, make_licence, make_user, otp_outbox):
    make_licence()
    login(client, make_user(role=Role.LICENSING_AUTHORITY), otp_outbox)
    for bad in (
        {"page": 0},
        {"page": "x"},
        {"page": None},
        {"status": "LOST"},
        {"area": "x"},
        {"area": 9999},
    ):
        response = search(client, **bad)
        assert response.status_code == 400 and response.json() == UNKNOWN_FILTER, bad
    too_long = search(client, number="X" * 41)
    assert too_long.status_code == 400 and "number" in too_long.json()
    assert search(client, area=org.sanand.id, page=1).json()["count"] == 1


def test_search_needs_csrf_and_uses_the_lookup_throttle(app_db, make_user, otp_outbox):
    assert LicenceSearchView.throttle_scope == "lookup"
    authority = make_user(role=Role.LICENSING_AUTHORITY)
    c = Client(enforce_csrf_checks=True)
    token = c.get("/api/auth/csrf").cookies["csrftoken"].value
    headers = {"HTTP_X_CSRFTOKEN": token}
    first = c.post(
        "/api/auth/login",
        {"user_id": authority.user_id, "password": TEST_PASSWORD},
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
    body = {"number": "GJ/TEST/0001"}
    assert c.post(SEARCH, body, content_type="application/json").status_code == 403
    allowed = c.post(SEARCH, body, content_type="application/json", HTTP_X_CSRFTOKEN=token)
    assert allowed.status_code == 200


def test_filters_and_pagination(app_db, client, org, make_licence, make_user, otp_outbox):
    made = [make_licence() for _ in range(26)]
    in_district = make_licence(area=org.ahmedabad)
    with acting_as_system("test"):
        set_status(made[0], "SUSPENDED", by="test", reason="test")
    login(client, make_user(role=Role.HEAD_AUTHORITY), otp_outbox)

    first = client.get("/api/licences").json()
    assert first["count"] == 27 and first["page"] == 1 and first["page_size"] == 25
    assert len(first["results"]) == 25
    row = first["results"][0]
    assert set(row) == {
        "id",
        "licence_number",
        "holder_name",
        "licence_type",
        "scope",
        "area",
        "status",
        "valid_to",
    }
    assert row["licence_number"] == "GJ/TEST/0001"
    assert row["area"] == "Sanand" and row["valid_to"] == "2047-12-31"

    second = client.get("/api/licences", {"page": 2}).json()
    assert [r["id"] for r in second["results"]] == [made[25].id, in_district.id]
    beyond = client.get("/api/licences", {"page": 9}).json()
    assert beyond["count"] == 27 and beyond["results"] == []

    suspended = client.get("/api/licences", {"status": "SUSPENDED"}).json()
    assert [r["id"] for r in suspended["results"]] == [made[0].id]
    district = client.get("/api/licences", {"area": org.ahmedabad.id}).json()
    assert [r["id"] for r in district["results"]] == [in_district.id]

    for bad in (
        {"page": "0"},
        {"page": "x"},
        {"page": str(10**6 + 1)},
        {"page": "9" * 30},
        {"status": "LOST"},
        {"area": "x"},
        {"area": 9999},
    ):
        response = client.get("/api/licences", bad)
        assert response.status_code == 400 and response.json() == UNKNOWN_FILTER
    assert events("licence.register_search") == []  # unfiltered listing is not audited


def test_detail_has_periods_and_permissions_but_no_contact_or_stock(
    app_db, client, catalogue, make_licence, make_user, otp_outbox
):
    licence = make_licence(contact="+919876543210", starts_on=date(2026, 1, 1))
    with acting_as_system("test"):
        set_opening_balance(
            gstin_index=licence.gstin_index,
            substance=catalogue.whisky,
            quantity=Decimal("777.125"),
            by="test",
        )
    login(client, make_user(role=Role.SOFTWARE_OWNER), otp_outbox)

    response = client.get(f"/api/licences/{licence.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["gstin"] == DEMO_GSTIN
    assert body["periods"] == [{"starts_on": "2026-01-01", "ends_on": "2047-12-31"}]
    assert body["permissions"] == {
        "may_buy": True,
        "may_sell": True,
        "may_transport": False,
        "max_stock_qty": "1000.000",
        "max_per_transaction_qty": "500.000",
        # What the permissions card needs as well: the unit and the current period.
        "unit": None,
        "trading_permitted": True,
        "valid_from": "2026-01-01",
        "valid_to": "2047-12-31",
    }
    raw = response.content.decode()
    assert "9876543210" not in raw and "777" not in raw and "contact" not in raw

    missing = client.get("/api/licences/999999")
    assert missing.status_code == 404


def test_search_and_view_are_audited_by_blind_index_only(
    app_db, client, make_licence, make_user, otp_outbox
):
    licence = make_licence()
    authority = make_user(role=Role.LICENSING_AUTHORITY)
    login(client, authority, otp_outbox)

    search(client, number="GJ/TEST/0001")
    search(client, gstin=DEMO_GSTIN)
    client.get(f"/api/licences/{licence.id}")

    searches = events("licence.register_search")
    assert [e["payload"] for e in searches] == [
        {"number_index": crypto.blind_index("licence_number", "GJ/TEST/0001"), "results": 1},
        {"gstin_index": crypto.blind_index("gstin", DEMO_GSTIN), "results": 1},
    ]
    assert all(e["actor"] == authority.user_id for e in searches)
    viewed = events("licence.viewed")
    assert viewed == [
        {
            "actor": authority.user_id,
            "subject_type": "licence",
            "subject_id": str(licence.id),
            "payload": {},
        }
    ]
    with transaction.atomic():
        set_actor(user_id="test", role=SYSTEM_ROLE)
        text = str(list(AuditEvent.objects.values_list("payload", "subject_id", "reason")))
    assert "GJ/TEST/0001" not in text and DEMO_GSTIN not in text
