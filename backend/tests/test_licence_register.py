"""The licence register for authorities: exact search, filters, detail, audit (D2d Task 4)."""

from datetime import date
from decimal import Decimal

import pytest
from django.db import transaction

from audit.models import AuditEvent
from core import crypto
from core.db_context import SYSTEM_ROLE, acting_as_system, set_actor
from identity.roles import Role
from licensing.service import set_status
from stock.service import set_opening_balance
from tests.conftest import BUYER_GSTIN, DEMO_GSTIN
from tests.test_transaction_api import login

pytestmark = pytest.mark.django_db

UNKNOWN_FILTER = {"detail": "Unknown filter value."}


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


def test_mine_still_routes_to_my_licences(app_db, client, make_user, otp_outbox):
    login(client, make_user(role=Role.HEAD_AUTHORITY), otp_outbox)
    assert client.get("/api/licences/mine").status_code == 403  # licensee-only view, not detail


def test_exact_search_by_number_and_gstin(app_db, client, make_licence, make_user, otp_outbox):
    first = make_licence()  # GJ/TEST/0001, DEMO_GSTIN
    make_licence(gstin=BUYER_GSTIN)  # GJ/TEST/0002
    login(client, make_user(role=Role.LICENSING_AUTHORITY), otp_outbox)

    body = client.get("/api/licences", {"number": "  gj/test/0001 "}).json()
    assert body["count"] == 1
    assert [row["id"] for row in body["results"]] == [first.id]

    body = client.get("/api/licences", {"gstin": DEMO_GSTIN.lower() + " "}).json()
    assert [row["id"] for row in body["results"]] == [first.id]

    assert client.get("/api/licences", {"number": "GJ/TEST/000"}).json()["count"] == 0
    assert client.get("/api/licences", {"gstin": DEMO_GSTIN[:10]}).json()["count"] == 0


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

    for bad in ({"page": "0"}, {"page": "x"}, {"status": "LOST"}, {"area": "x"}, {"area": 9999}):
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

    client.get("/api/licences", {"number": "GJ/TEST/0001"})
    client.get("/api/licences", {"gstin": DEMO_GSTIN})
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
