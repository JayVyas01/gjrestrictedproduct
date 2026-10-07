"""`status_for_you`: the status wording for the viewer (owner decision A8, 2026-10-06)."""

import pytest

from identity.roles import Role
from tests.test_transaction_api import login
from tests.test_transaction_decisions import new_tx

pytestmark = pytest.mark.django_db


def _seen(client, user, tx, otp_outbox):
    login(client, user, otp_outbox)
    detail = client.get(f"/api/transactions/{tx.reference}").json()
    [row] = [r for r in client.get("/api/transactions").json() if r["reference"] == tx.reference]
    assert row["status_for_you"] == detail["status_for_you"]  # the list says the same
    assert row["awaiting_you"] == detail["can_decide"]
    assert detail["awaiting_you"] == (detail["status_for_you"] == "Requires your approval")
    return detail["status_for_you"]


@pytest.fixture
def head(make_user):
    return make_user(role=Role.HEAD_AUTHORITY, contact="+919800000602")


def test_awaiting_buyer(app_db, client, catalogue, trade, otp_outbox, head):
    tx = new_tx(trade, catalogue, qty="10")
    assert _seen(client, trade.buyer, tx, otp_outbox) == "Requires your approval"
    assert _seen(client, trade.seller, tx, otp_outbox) == "Requires buyer approval"
    assert _seen(client, trade.officer, tx, otp_outbox) == "Waiting for the buyer"
    assert _seen(client, head, tx, otp_outbox) == "Waiting for the buyer"


def test_awaiting_officer(app_db, client, trade, settle, otp_outbox, head):
    tx = settle(officer=None)
    assert _seen(client, trade.officer, tx, otp_outbox) == "Requires your approval"
    assert _seen(client, trade.seller, tx, otp_outbox) == "Requires officer approval"
    assert _seen(client, trade.buyer, tx, otp_outbox) == "Requires officer approval"
    assert _seen(client, trade.superintendent, tx, otp_outbox) == "Waiting for the officer"
    assert _seen(client, head, tx, otp_outbox) == "Waiting for the officer"


def test_awaiting_superintendent(app_db, client, trade, threshold, settle, otp_outbox, head):
    tx = settle("250", officer="RECOMMEND")
    assert _seen(client, trade.superintendent, tx, otp_outbox) == "Requires your approval"
    assert _seen(client, trade.seller, tx, otp_outbox) == "Requires superintendent approval"
    assert _seen(client, trade.buyer, tx, otp_outbox) == "Requires superintendent approval"
    assert _seen(client, trade.officer, tx, otp_outbox) == "Waiting for the superintendent"
    assert _seen(client, head, tx, otp_outbox) == "Waiting for the superintendent"


def test_settled_keeps_the_label(app_db, client, trade, settle, otp_outbox):
    tx = settle()
    for user in (trade.seller, trade.buyer, trade.officer):
        assert _seen(client, user, tx, otp_outbox) == "Approved"
