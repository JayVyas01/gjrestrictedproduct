"""The read and filter APIs the web app needs (D3 B1-B4, B6) and the thresholds read."""

from decimal import Decimal

import pytest
from django.db import transaction
from django.test import Client

from audit.models import AuditEvent
from catalogue.service import add_threshold_version
from core.db_context import SYSTEM_ROLE, acting_as_system, set_actor
from identity.roles import Role
from positions.service import assign
from tests.conftest import BUYER_GSTIN, DEMO_GSTIN, TEST_PASSWORD
from tests.test_buyer_stock_limit import buyer_holds
from tests.test_transaction_api import login, post
from tests.test_transaction_decisions import act, new_tx
from transactions.models import Transaction
from transactions.serializers import TransactionFilterSerializer

pytestmark = pytest.mark.django_db
CHECK = {"buyer_gstin": BUYER_GSTIN, "substance_code": "WHISKY", "quantity": "150"}


def references(client, query):
    response = client.get(f"/api/transactions?{query}")
    assert response.status_code == 200
    return {row["reference"] for row in response.json()}


def last_audit():
    with transaction.atomic():
        set_actor(user_id="test", role=SYSTEM_ROLE)
        return AuditEvent.objects.order_by("-id").values("action", "payload").first()


def test_me_has_display_name_and_positions(app_db, client, org, trade, make_user, otp_outbox):
    login(client, trade.seller, otp_outbox)
    assert client.get("/api/auth/me").json() == {
        "user_id": trade.seller.user_id,
        "role": "LICENSEE",
        "display_name": "Sanand Spirits Pvt Ltd",
        "positions": [],
    }

    assign(org.district_officer, trade.officer, by="test")
    login(client, trade.officer, otp_outbox)
    me = client.get("/api/auth/me").json()
    assert me["display_name"] == "Area Officer, Sanand, District Officer, Ahmedabad"
    assert me["positions"] == [
        {"id": org.area_officer.id, "title": "Area Officer, Sanand", "level": "TALUKA"},
        {
            "id": org.district_officer.id,
            "title": "District Officer, Ahmedabad",
            "level": "DISTRICT",
        },
    ]

    login(client, trade.superintendent, otp_outbox)  # their position went to the officer
    me = client.get("/api/auth/me").json()
    assert (me["display_name"], me["positions"]) == ("Unassigned officer", [])

    authority = make_user(role=Role.LICENSING_AUTHORITY, contact="+919800000601")
    login(client, authority, otp_outbox)
    me = client.get("/api/auth/me").json()
    assert (me["display_name"], me["positions"]) == ("Licensing Authority", [])


def test_awaiting_me_filter_matches_home_count(
    app_db, client, catalogue, org, trade, threshold, otp_outbox
):
    recommended = new_tx(trade, catalogue, qty="250")
    act(trade.buyer, Role.LICENSEE, recommended, otp_outbox, "CONFIRM")
    act(trade.officer, Role.PERSONNEL, recommended, otp_outbox, "RECOMMEND")
    waiting = new_tx(trade, catalogue, qty="10")
    act(trade.buyer, Role.LICENSEE, waiting, otp_outbox, "CONFIRM")
    for_buyer = new_tx(trade, catalogue, qty="10")
    assign(org.district_officer, trade.officer, by="test")

    login(client, trade.officer, otp_outbox)
    home = client.get("/api/home").json()["counts"]["awaiting_your_decision"]
    assert references(client, "awaiting=me") == {recommended.reference, waiting.reference}
    assert home == 2

    login(client, trade.buyer, otp_outbox)
    home = client.get("/api/home").json()["counts"]["awaiting_your_decision"]
    assert references(client, "awaiting=me") == {for_buyer.reference}
    assert home == 1


def test_side_filter(app_db, client, catalogue, trade, otp_outbox):
    tx = new_tx(trade, catalogue, qty="10")
    login(client, trade.seller, otp_outbox)
    assert references(client, "side=sales") == {tx.reference}
    assert references(client, "side=purchases") == set()
    assert references(client, "side=sales&awaiting=me") == set()
    login(client, trade.buyer, otp_outbox)
    assert references(client, "side=sales") == set()
    assert references(client, "side=purchases") == {tx.reference}
    assert references(client, "side=purchases&awaiting=me") == {tx.reference}


def test_list_rows_carry_the_approval_chain(
    app_db, client, catalogue, trade, threshold, otp_outbox
):
    """The officer's queue shows each row's chain without opening it."""
    small = new_tx(trade, catalogue, qty="10")
    large = new_tx(trade, catalogue, qty="250")
    login(client, trade.seller, otp_outbox)
    rows = {row["reference"]: row for row in client.get("/api/transactions").json()}
    assert rows[small.reference]["approval_chain"] == "OFFICER"
    assert rows[small.reference]["approval_chain_label"] == "Officer"
    assert rows[large.reference]["approval_chain"] == "OFFICER_THEN_SUPERINTENDENT"
    assert rows[large.reference]["approval_chain_label"] == "Officer, then superintendent"


def test_blank_filter_means_no_filter(app_db, client, catalogue, trade, otp_outbox):
    sale = new_tx(trade, catalogue, qty="10")
    act(trade.buyer, Role.LICENSEE, sale, otp_outbox, "CONFIRM")
    waiting = new_tx(trade, catalogue, qty="10")
    login(client, trade.buyer, otp_outbox)
    assert references(client, "side=&awaiting=me") == {waiting.reference}
    assert references(client, "side=&awaiting=&approved_by=") == {
        sale.reference,
        waiting.reference,
    }


def test_filter_serializer_accepts_blanks_from_any_source():
    """Blank means no filter even when the data is not a query string (e.g. a plain dict)."""
    filters = TransactionFilterSerializer(data={"side": "", "awaiting": "me", "approved_by": ""})
    assert filters.is_valid(), filters.errors
    assert filters.validated_data == {"side": "", "awaiting": "me", "approved_by": ""}


def test_approved_by_superintendent_filter(
    app_db, client, catalogue, trade, threshold, settle, make_user, otp_outbox
):
    final = settle("250", officer="RECOMMEND", superintendent="APPROVE")
    settle("10")  # approved by the officer alone
    settle("100", officer="REJECT", reason_code="QUANTITY_MISMATCH")
    head = make_user(role=Role.HEAD_AUTHORITY, contact="+919800000701")
    login(client, head, otp_outbox)
    assert references(client, "approved_by=superintendent") == {final.reference}
    login(client, trade.seller, otp_outbox)
    assert references(client, "approved_by=superintendent&side=sales") == {final.reference}
    assert references(client, "approved_by=superintendent&side=purchases") == set()


@pytest.mark.parametrize(
    "query", ["awaiting=you", "side=both", "approved_by=officer", "awaiting=ME"]
)
def test_unknown_filter_is_400(app_db, client, trade, otp_outbox, query):
    login(client, trade.seller, otp_outbox)
    response = client.get(f"/api/transactions?{query}")
    assert response.status_code == 400
    assert response.json() == {"detail": "Unknown filter value."}


def test_check_endpoint_ok_and_chain(app_db, client, trade, threshold, otp_outbox):
    login(client, trade.seller, otp_outbox)
    assert post(client, "/api/transactions/check", CHECK).json() == {
        "ok": True,
        "reasons": [],
        "approval_chain": "OFFICER",
    }
    above = post(client, "/api/transactions/check", {**CHECK, "quantity": "250"})
    assert above.status_code == 200
    assert above.json()["approval_chain"] == "OFFICER_THEN_SUPERINTENDENT"


def test_check_endpoint_reasons_and_no_writes(app_db, client, trade, otp_outbox):
    login(client, trade.seller, otp_outbox)
    refused = post(client, "/api/transactions/check", {**CHECK, "quantity": "600"}).json()
    assert refused["ok"] is False and refused["approval_chain"] is None
    assert (
        "Quantity 600 L exceeds your licence's per-transaction limit of 500 L."
        in (refused["reasons"])
    )
    audit = last_audit()
    assert audit["action"] == "transaction.checked"
    assert set(audit["payload"]) == {"gstin_index", "ok"} and audit["payload"]["ok"] is False
    assert BUYER_GSTIN not in str(audit)

    own = post(client, "/api/transactions/check", {**CHECK, "buyer_gstin": DEMO_GSTIN}).json()
    assert own == {
        "ok": False,
        "reasons": ["You cannot sell to your own business."],
        "approval_chain": None,
    }
    assert last_audit()["action"] == "transaction.checked"

    post(client, "/api/transactions/check", CHECK)
    assert last_audit()["payload"]["ok"] is True
    with acting_as_system("test"):
        assert not Transaction.objects.exists()


def test_check_endpoint_hides_buyer_stock(app_db, client, catalogue, trade, otp_outbox):
    buyer_holds(trade, catalogue)  # a 10 L sale would take the buyer over their 1000 L limit
    login(client, trade.seller, otp_outbox)
    response = post(client, "/api/transactions/check", {**CHECK, "quantity": "10"})
    assert response.json() == {"ok": True, "reasons": [], "approval_chain": "OFFICER"}


def test_check_requires_licensee_and_csrf(app_db, client, trade, otp_outbox):
    login(client, trade.officer, otp_outbox)
    assert post(client, "/api/transactions/check", CHECK).status_code == 403

    c = Client(enforce_csrf_checks=True)
    token = c.get("/api/auth/csrf").cookies["csrftoken"].value
    first = c.post(
        "/api/auth/login",
        {"user_id": trade.seller.user_id, "password": TEST_PASSWORD},
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
    assert post(c, "/api/transactions/check", CHECK).status_code == 403
    checked = c.post(
        "/api/transactions/check", CHECK, content_type="application/json", HTTP_X_CSRFTOKEN=token
    )
    assert checked.status_code == 200


def test_thresholds_api(app_db, client, catalogue, trade, threshold, otp_outbox):
    with acting_as_system("test"):
        for qty in ("100", "150"):
            add_threshold_version(
                substance=catalogue.whisky, superintendent_above_qty=Decimal(qty), created_by="t"
            )
    assert client.get("/api/catalogue/approval-thresholds").status_code == 403
    login(client, trade.seller, otp_outbox)
    assert client.get("/api/catalogue/approval-thresholds").json() == [
        {
            "scope": "Spirits",
            "scope_kind": "class",
            "superintendent_above_qty": "200.000",
            "unit": "L",
            "version": 1,
        },
        {
            "scope": "Whisky",
            "scope_kind": "substance",
            "superintendent_above_qty": "150.000",
            "unit": "L",
            "version": 2,
        },
    ]


def _officer_alert(client, trade, settle, otp_outbox):
    settle(buyer="REJECT", reason_code="NOT_ORDERED")
    login(client, trade.officer, otp_outbox)
    return client.get("/api/alerts").json()["alerts"][0]["id"]


def test_acknowledge_twice_is_409_with_message(app_db, client, trade, settle, otp_outbox):
    alert_id = _officer_alert(client, trade, settle, otp_outbox)
    url = f"/api/alerts/{alert_id}/acknowledge"
    assert post(client, url).status_code == 200
    again = post(client, url)
    assert again.status_code == 409
    assert again.json() == {"detail": "This alert is already acknowledged."}


def test_acknowledge_not_holder_is_403_with_message(app_db, client, trade, settle, otp_outbox):
    alert_id = _officer_alert(client, trade, settle, otp_outbox)
    login(client, trade.superintendent, otp_outbox)
    refused = post(client, f"/api/alerts/{alert_id}/acknowledge")
    assert refused.status_code == 403
    assert refused.json() == {
        "detail": "Only the officer holding this position can acknowledge this alert."
    }
