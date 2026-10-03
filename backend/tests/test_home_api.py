"""GET /api/home: the counts each role's home screen shows, read under the caller's own RLS."""

from datetime import date

import pytest

from core.db_context import acting_as_system, set_actor
from core.home import home_counts
from identity.roles import Role
from licensing.models import LicenceStatus
from licensing.service import record_renewal, set_status
from oversight.service import create_due_batches, set_review_period
from positions.models import Area, AreaLevel, Position
from positions.service import assign
from tests.conftest import set_decided_on
from tests.test_buyer_stock_limit import buyer_holds
from tests.test_transaction_api import login
from tests.test_transaction_decisions import act, new_tx

pytestmark = pytest.mark.django_db


def counts_for(user, today):
    set_actor(user_id=user.user_id, role=user.role)
    return home_counts(user, today)


def test_home_needs_login(app_db, client):
    assert client.get("/api/home").status_code == 403


def test_licensee_counts(app_db, client, catalogue, trade, otp_outbox):
    buyer_holds(trade, catalogue)  # the 10 L sales would take the buyer over their limit
    new_tx(trade, catalogue, qty="10")  # still the buyer's decision (they can only reject)
    new_tx(trade, catalogue, qty="10")
    rejected = new_tx(trade, catalogue, qty="10")
    act(trade.buyer, Role.LICENSEE, rejected, otp_outbox, "REJECT")

    login(client, trade.buyer, otp_outbox)
    assert client.get("/api/home").json() == {
        "role": "LICENSEE",
        "counts": {"awaiting_your_decision": 2, "sales_in_progress": 0},
    }
    login(client, trade.seller, otp_outbox)
    assert client.get("/api/home").json() == {
        "role": "LICENSEE",
        "counts": {"awaiting_your_decision": 0, "sales_in_progress": 2},
    }


def test_sales_in_progress_counts_every_waiting_status(
    app_db, catalogue, trade, threshold, otp_outbox
):
    new_tx(trade, catalogue, qty="10")
    confirmed = new_tx(trade, catalogue, qty="10")
    act(trade.buyer, Role.LICENSEE, confirmed, otp_outbox, "CONFIRM")
    recommended = new_tx(trade, catalogue, qty="250")
    act(trade.buyer, Role.LICENSEE, recommended, otp_outbox, "CONFIRM")
    act(trade.officer, Role.PERSONNEL, recommended, otp_outbox, "RECOMMEND")
    rejected = new_tx(trade, catalogue, qty="10")
    act(trade.buyer, Role.LICENSEE, rejected, otp_outbox, "REJECT", reason_code="NOT_ORDERED")
    assert counts_for(trade.seller, date(2026, 10, 4))["sales_in_progress"] == 3


def test_personnel_awaiting_excludes_own_officer_decision(
    app_db, catalogue, org, trade, threshold, otp_outbox
):
    recommended = new_tx(trade, catalogue, qty="250")
    act(trade.buyer, Role.LICENSEE, recommended, otp_outbox, "CONFIRM")
    act(trade.officer, Role.PERSONNEL, recommended, otp_outbox, "RECOMMEND")
    waiting = new_tx(trade, catalogue, qty="10")
    act(trade.buyer, Role.LICENSEE, waiting, otp_outbox, "CONFIRM")
    today = date(2026, 10, 4)

    assert counts_for(trade.superintendent, today)["awaiting_your_decision"] == 1
    assert counts_for(trade.officer, today)["awaiting_your_decision"] == 1

    # The officer now also holds the district position, but made the officer decision on
    # `recommended`, so only `waiting` is theirs to decide (ruling C-R5).
    assign(org.district_officer, trade.officer, by="test")
    assert counts_for(trade.officer, today)["awaiting_your_decision"] == 1


def test_personnel_alerts_and_batches(app_db, client, trade, settle, review_setting, otp_outbox):
    approved = settle()
    set_decided_on(approved, date(2026, 6, 10))
    settle(buyer="REJECT", reason_code="NOT_ORDERED")  # one alert to each position
    with acting_as_system("test"):
        # 15-day periods from 1 June: due 15 July, 30 July and 14 August.
        create_due_batches(date(2026, 7, 20))

    assert counts_for(trade.superintendent, date(2026, 7, 20)) == {
        "awaiting_your_decision": 0,
        "unacknowledged_alerts": 1,
        "open_batches": 2,
        "overdue_batches": 1,
        "next_due": "2026-07-30",
    }
    officer = counts_for(trade.officer, date(2026, 7, 20))
    assert officer["unacknowledged_alerts"] == 1
    assert (officer["open_batches"], officer["overdue_batches"], officer["next_due"]) == (
        0,
        0,
        None,
    )

    login(client, trade.superintendent, otp_outbox)
    body = client.get("/api/home").json()
    assert body["role"] == "PERSONNEL"
    assert body["counts"]["overdue_batches"] == 3  # today (Oct 2026) is past every due date


def test_licensing_authority_counts(app_db, org, make_licence, make_user):
    today = date(2026, 10, 4)
    make_licence(ends_on=date(2026, 10, 20), contact="+919800000501")
    make_licence(ends_on=date(2026, 11, 3), contact="+919800000502")  # today + 30: counts
    make_licence(ends_on=date(2026, 11, 4), contact="+919800000503")  # one day too late
    make_licence(ends_on=date(2026, 10, 3), contact="+919800000504")  # already ended
    suspended = make_licence(ends_on=date(2026, 10, 20), contact="+919800000505")
    renewed = make_licence(ends_on=date(2026, 10, 20), contact="+919800000506")
    with acting_as_system("test"):
        set_status(suspended, LicenceStatus.SUSPENDED, by="test", reason="test")
        record_renewal(
            renewed, starts_on=date(2026, 10, 21), ends_on=date(2027, 10, 20), recorded_by="test"
        )
    vadodara = Area.objects.create(
        code="GJ-VAD", name="Vadodara", level=AreaLevel.DISTRICT, parent=org.state
    )
    Position.objects.create(code="DO-VAD", title="District Officer, Vadodara", area=vadodara)
    with acting_as_system("test"):
        set_review_period(position=org.district_officer, days=15, by="test")

    authority = make_user(role=Role.LICENSING_AUTHORITY, contact="+919800000601")
    assert counts_for(authority, today) == {
        "expiring_licences_30d": 2,
        "districts_without_review_period": 1,
    }


@pytest.mark.parametrize("role", [Role.HEAD_AUTHORITY, Role.SOFTWARE_OWNER])
def test_head_authority_and_owner_counts(
    app_db, client, catalogue, trade, threshold, settle, make_user, otp_outbox, role
):
    settle(buyer="REJECT", reason_code="NOT_ORDERED")  # two alerts
    settle("250", officer="RECOMMEND")  # waiting for the superintendent
    viewer = make_user(role=role, contact="+919800000701")
    login(client, viewer, otp_outbox)
    assert client.get("/api/home").json() == {
        "role": role,
        "counts": {"unacknowledged_alerts": 2, "awaiting_superintendent": 1},
    }
