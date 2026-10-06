"""The demo CSV files (A6, A7): parties, officials and transactions, rebuilt from the database
after every relevant commit, in demo mode only. A failed export never fails the request.

A test runs in one database transaction, so an export scheduled during its setup would still be
waiting (and so cover every later change) when the test body starts. The `demo` fixture comes
last in each test's arguments, after the setup fixtures, and setup in a test body runs inside
its own executed capture block."""

import csv
import logging
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from core.db_context import acting_as_system, set_actor
from demo import csv_export
from demo.models import DemoCredential
from identity.models import User
from identity.roles import Role
from licensing.models import LicenceStatus
from licensing.service import set_status
from tests.conftest import (
    BUYER_GSTIN,
    DEMO_GSTIN,
    TEST_PASSWORD,
    TEST_TRANSPORT,
    _sign,
    api_login,
)
from transactions.service import start_transaction

pytestmark = pytest.mark.django_db

PARTY_COLUMNS = [
    "business_name",
    "gstin",
    "phone_on_file",
    "email",
    "password",
    "signed_up",
    "licence_numbers",
    "licence_types",
    "licence_statuses",
    "scopes",
    "talukas",
    "may_buy",
    "may_sell",
    "stock_limits",
    "per_transaction_limits",
    "valid_until",
    "current_stock",
]
OFFICIAL_COLUMNS = ["name_or_position", "login_role", "email", "password", "must_change_password"]
TRANSACTION_COLUMNS = [
    "reference",
    "created_at",
    "seller",
    "buyer",
    "substance",
    "quantity",
    "unit",
    "status",
    "approval_chain",
    "waiting_for",
]
UNSIGNED_GSTIN = "99DDDDD2222D1Z5"


@pytest.fixture
def demo(settings, tmp_path):
    settings.DEMO_MODE = True
    settings.DEMO_PASSWORD = "demo-password-2026"
    settings.DEMO_DATA_DIR = str(tmp_path)
    return tmp_path


def read(directory, name) -> list[dict]:
    with open(directory / name, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def header(directory, name) -> list[str]:
    with open(directory / name, newline="", encoding="utf-8") as handle:
        return next(csv.reader(handle))


def row(rows, **match) -> dict:
    found = [r for r in rows if all(r[k] == v for k, v in match.items())]
    assert len(found) == 1, (match, rows)
    return found[0]


def new_sale(trade, catalogue, qty="10"):
    set_actor(user_id=trade.seller.user_id, role=trade.seller.role)
    return start_transaction(
        seller=trade.seller,
        buyer_gstin=BUYER_GSTIN,
        substance=catalogue.whisky,
        quantity=Decimal(qty),
        transport=TEST_TRANSPORT,
    )


# --- The files -------------------------------------------------------------------------------


def test_the_export_writes_three_files_with_exact_headers(app_db, tmp_path):
    csv_export.export_all(tmp_path)
    assert header(tmp_path, "parties.csv") == PARTY_COLUMNS
    assert header(tmp_path, "officials.csv") == OFFICIAL_COLUMNS
    assert header(tmp_path, "transactions.csv") == TRANSACTION_COLUMNS
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "officials.csv",
        "parties.csv",
        "transactions.csv",
    ]  # no temporary file left behind


def test_the_export_creates_the_directory(app_db, tmp_path):
    csv_export.export_all(tmp_path / "new")
    assert (tmp_path / "new" / "parties.csv").exists()


def test_a_party_row_has_its_licences_stock_and_permissions(
    app_db, tmp_path, trade, catalogue, make_licence
):
    make_licence(
        holder_name="Sanand Spirits Pvt Ltd",
        contact="+919800000201",
        licence_type=catalogue.wholesale,
        substance=catalogue.rum,
        substance_class=None,
    )
    DemoCredential.store(trade.seller.user_id, "seller-pass-2026")
    csv_export.export_all(tmp_path)
    seller = row(read(tmp_path, "parties.csv"), gstin=DEMO_GSTIN)
    assert seller == {
        "business_name": "Sanand Spirits Pvt Ltd",
        "gstin": DEMO_GSTIN,
        "phone_on_file": "+919800000201",
        "email": "",
        "password": "seller-pass-2026",
        "signed_up": "yes",
        "licence_numbers": "GJ/TEST/0001; GJ/TEST/0003",
        "licence_types": "Retail; Wholesale",
        "licence_statuses": "ACTIVE; ACTIVE",
        "scopes": "Spirits; Rum",
        "talukas": "Sanand; Sanand",
        "may_buy": "yes; yes",
        "may_sell": "yes; yes",
        "stock_limits": "1000 L; 50000 L",
        "per_transaction_limits": "500 L; 10000 L",
        "valid_until": "2047-12-31; 2047-12-31",
        "current_stock": "Whisky 400 L",
    }


def test_a_licensed_business_without_an_account_is_listed_for_sign_up(
    app_db, tmp_path, make_licence
):
    make_licence(gstin=UNSIGNED_GSTIN, holder_name="Bavla Wines", contact="+919800000555")
    csv_export.export_all(tmp_path)
    unsigned = row(read(tmp_path, "parties.csv"), gstin=UNSIGNED_GSTIN)
    assert unsigned["business_name"] == "Bavla Wines"
    assert unsigned["phone_on_file"] == "+919800000555"
    assert unsigned["signed_up"] == "no"
    assert unsigned["password"] == ""
    assert unsigned["email"] == ""


def test_licence_statuses_show_suspensions_and_expired_validity(app_db, tmp_path, make_licence):
    today = timezone.localdate()
    make_licence(gstin=UNSIGNED_GSTIN, holder_name="Bavla Wines", contact="+919800000555")
    suspended = make_licence(gstin=UNSIGNED_GSTIN, contact="+919800000555")
    ended = {"starts_on": today - timedelta(days=30), "ends_on": today - timedelta(days=1)}
    make_licence(gstin=UNSIGNED_GSTIN, **ended)  # its only period ended yesterday
    make_licence(  # its only period has not started yet
        gstin=UNSIGNED_GSTIN, starts_on=today + timedelta(days=1), ends_on=today + timedelta(days=9)
    )
    with acting_as_system("test"):
        set_status(suspended, LicenceStatus.SUSPENDED, by="test", reason="inspection")
    csv_export.export_all(tmp_path)
    party = row(read(tmp_path, "parties.csv"), gstin=UNSIGNED_GSTIN)
    assert party["licence_statuses"] == "ACTIVE; SUSPENDED; EXPIRED; EXPIRED"


def test_officials_have_role_email_password_and_the_change_flag(app_db, tmp_path, trade, make_user):
    head = make_user(
        role=Role.HEAD_AUTHORITY, email="head.a@demo.gujarat.example", must_change_password=True
    )
    DemoCredential.store(head.user_id, "issued-pass-2026")
    DemoCredential.store(trade.officer.user_id, "officer-own-pass-1")
    csv_export.export_all(tmp_path)
    officials = read(tmp_path, "officials.csv")
    assert row(officials, email="head.a@demo.gujarat.example") == {
        "name_or_position": "Head Authority",
        "login_role": "HEAD_AUTHORITY",
        "email": "head.a@demo.gujarat.example",
        "password": "issued-pass-2026",
        "must_change_password": "yes",
    }
    officer = row(officials, email=trade.officer.get_email())
    assert officer["name_or_position"] == "Area Officer, Sanand"
    assert officer["login_role"] == "AREA_OFFICER"
    assert officer["password"] == "officer-own-pass-1"
    assert officer["must_change_password"] == "no"
    superintendent = row(officials, email=trade.superintendent.get_email())
    assert superintendent["login_role"] == "SUPERINTENDENT"
    assert superintendent["password"] == ""  # no DemoCredential row
    # Parties are not officials.
    assert len(officials) == 3


def test_a_transaction_row_says_what_it_waits_for(app_db, tmp_path, trade, catalogue, otp_outbox):
    tx = new_sale(trade, catalogue)
    csv_export.export_all(tmp_path)
    waiting = row(read(tmp_path, "transactions.csv"), reference=tx.reference)
    assert waiting["seller"] == "Sanand Spirits Pvt Ltd"
    assert waiting["buyer"] == "Bopal Bar & Kitchen"
    assert waiting["substance"] == "Whisky"
    assert waiting["quantity"] == "10"
    assert waiting["unit"] == "L"
    assert waiting["status"] == "Waiting for the buyer"
    assert waiting["approval_chain"] == "Officer"
    assert waiting["waiting_for"] == "Buyer: Bopal Bar & Kitchen"
    assert len(waiting["created_at"]) == len("2026-10-07 14:05")

    _sign(trade.buyer, tx, "CONFIRM", otp_outbox)
    csv_export.export_all(tmp_path)
    confirmed = row(read(tmp_path, "transactions.csv"), reference=tx.reference)
    assert confirmed["status"] == "Waiting for the officer"
    assert confirmed["waiting_for"] == f"Area Officer, Sanand ({trade.officer.get_email()})"

    _sign(trade.officer, tx, "APPROVE", otp_outbox)
    csv_export.export_all(tmp_path)
    approved = row(read(tmp_path, "transactions.csv"), reference=tx.reference)
    assert approved["status"] == "Approved"
    assert approved["waiting_for"] == ""


# --- Kept in step after each commit ----------------------------------------------------------


def test_a_new_transaction_and_a_decision_update_the_files(
    app_db, trade, catalogue, otp_outbox, django_capture_on_commit_callbacks, demo
):
    with django_capture_on_commit_callbacks(execute=True):
        tx = new_sale(trade, catalogue)
    assert row(read(demo, "transactions.csv"), reference=tx.reference)["status"] == (
        "Waiting for the buyer"
    )
    with django_capture_on_commit_callbacks(execute=True):
        _sign(trade.buyer, tx, "CONFIRM", otp_outbox)
    assert row(read(demo, "transactions.csv"), reference=tx.reference)["status"] == (
        "Waiting for the officer"
    )
    with django_capture_on_commit_callbacks(execute=True):
        _sign(trade.officer, tx, "APPROVE", otp_outbox)
    assert row(read(demo, "parties.csv"), gstin=BUYER_GSTIN)["current_stock"] == "Whisky 10 L"


def test_a_sign_up_updates_the_files_with_the_business_name_given(
    app_db, client, make_licence, otp_outbox, django_capture_on_commit_callbacks, demo
):
    with django_capture_on_commit_callbacks(execute=True):
        make_licence(gstin=UNSIGNED_GSTIN, holder_name="Bavla Wines", contact="+919800000555")
    assert row(read(demo, "parties.csv"), gstin=UNSIGNED_GSTIN)["signed_up"] == "no"
    form = {
        "gstin": UNSIGNED_GSTIN,
        "phone": "9800000555",
        "email": "owner@bavla-wines.example",
        "business_name": "Bavla Wines and Spirits",
        "address": "1 Market Road, Bavla",
        "password": "bavla-own-pass-2026",
    }
    started = client.post("/api/demo/signup/start", form, "application/json")
    with django_capture_on_commit_callbacks(execute=True):
        done = client.post(
            "/api/demo/signup/complete",
            {"challenge_id": started.json()["challenge_id"], "code": otp_outbox[-1][1]},
            "application/json",
        )
    assert done.status_code == 201, done.content
    party = row(read(demo, "parties.csv"), gstin=UNSIGNED_GSTIN)
    assert party["signed_up"] == "yes"
    assert party["business_name"] == "Bavla Wines and Spirits"
    assert party["email"] == "owner@bavla-wines.example"
    assert party["password"] == "bavla-own-pass-2026"
    assert DemoCredential.objects.get(user_id=done.json()["user_id"]).business_name == (
        "Bavla Wines and Spirits"
    )


def test_a_password_change_updates_the_files(
    app_db, client, make_user, otp_outbox, django_capture_on_commit_callbacks, demo
):
    with django_capture_on_commit_callbacks(execute=True):
        head = make_user(role=Role.HEAD_AUTHORITY, must_change_password=True)
        DemoCredential.store(head.user_id, TEST_PASSWORD)
        api_login(client, head, otp_outbox)
    assert row(read(demo, "officials.csv"), email=head.get_email())["must_change_password"] == (
        "yes"
    )
    with django_capture_on_commit_callbacks(execute=True):
        changed = client.post(
            "/api/auth/password",
            {"current_password": TEST_PASSWORD, "new_password": "a-fresh-head-pass-77"},
            "application/json",
        )
    assert changed.status_code == 200
    official = row(read(demo, "officials.csv"), email=head.get_email())
    assert official["password"] == "a-fresh-head-pass-77"
    assert official["must_change_password"] == "no"


def test_many_changes_in_one_transaction_export_once(
    app_db, trade, catalogue, make_user, django_capture_on_commit_callbacks, demo
):
    with django_capture_on_commit_callbacks() as callbacks:
        new_sale(trade, catalogue)
        new_sale(trade, catalogue)
        DemoCredential.store(make_user(role=Role.HEAD_AUTHORITY).user_id, "x-pass-2026-long")
    exports = [cb for cb in callbacks if isinstance(cb, csv_export.ExportAfterCommit)]
    assert len(exports) == 1


def test_nothing_is_written_outside_demo_mode(
    app_db, settings, tmp_path, trade, catalogue, django_capture_on_commit_callbacks
):
    settings.DEMO_DATA_DIR = str(tmp_path)
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        new_sale(trade, catalogue)
    assert not [cb for cb in callbacks if isinstance(cb, csv_export.ExportAfterCommit)]
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(CommandError, match="demo mode"):
        call_command("export_demo_csv", "--dir", str(tmp_path))
    assert list(tmp_path.iterdir()) == []


def test_a_failed_export_does_not_fail_the_request_and_is_retried(
    app_db,
    client,
    make_user,
    otp_outbox,
    monkeypatch,
    caplog,
    django_capture_on_commit_callbacks,
    demo,
):
    with django_capture_on_commit_callbacks(execute=True):
        head = make_user(role=Role.HEAD_AUTHORITY)
        api_login(client, head, otp_outbox)
    assert row(read(demo, "officials.csv"), email=head.get_email())["password"] == ""

    def broken(directory):
        raise OSError("disk full")

    monkeypatch.setattr(csv_export, "export_all", broken)
    with (
        caplog.at_level(logging.ERROR, logger="demo.csv"),
        django_capture_on_commit_callbacks(execute=True),
    ):
        changed = client.post(
            "/api/auth/password",
            {"current_password": TEST_PASSWORD, "new_password": "a-fresh-head-pass-77"},
            "application/json",
        )
    assert changed.status_code == 200
    assert "Demo CSV export failed" in caplog.text
    assert row(read(demo, "officials.csv"), email=head.get_email())["password"] == ""

    monkeypatch.undo()
    with django_capture_on_commit_callbacks(execute=True):
        DemoCredential.store(head.user_id, "a-fresh-head-pass-77")
    assert row(read(demo, "officials.csv"), email=head.get_email())["password"] == (
        "a-fresh-head-pass-77"
    )


def test_the_command_writes_the_files(app_db, tmp_path, make_licence, demo):
    make_licence(gstin=UNSIGNED_GSTIN, holder_name="Bavla Wines")
    target = tmp_path / "elsewhere"
    call_command("export_demo_csv", "--dir", str(target))
    assert row(read(target, "parties.csv"), gstin=UNSIGNED_GSTIN)["signed_up"] == "no"
    call_command("export_demo_csv")  # default: settings.DEMO_DATA_DIR
    assert (demo / "parties.csv").exists()


def test_the_export_reads_everything_as_system_whoever_is_signed_in(
    app_db, tmp_path, trade, make_licence
):
    make_licence(gstin=UNSIGNED_GSTIN, holder_name="Bavla Wines")
    set_actor(user_id=trade.seller.user_id, role=trade.seller.role)  # RLS: own business only
    csv_export.export_all(tmp_path)
    assert len(read(tmp_path, "parties.csv")) == 3
    with acting_as_system("test"):
        assert User.objects.filter(role=Role.PERSONNEL).count() == len(
            read(tmp_path, "officials.csv")
        )
