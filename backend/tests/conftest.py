"""Shared test fixtures.

Use `app_db` (not `db`) for anything that exercises application behaviour, so the test runs
with the same restricted privileges as production. Use plain `db` only when a test must act as
the schema owner, for example to simulate an attacker tampering with the audit table.
Never use `transactional_db`: its TRUNCATE-based teardown is blocked by the audit trigger.
"""

from datetime import date, datetime, time
from decimal import Decimal
from itertools import count
from types import SimpleNamespace

import pytest
from django.db import connection, transaction
from django.utils import timezone

from audit.models import AuditEvent
from catalogue.models import LicenceType, LicenceTypeRule, Substance, SubstanceClass, Unit
from catalogue.service import add_rule_version, add_threshold_version
from core.db_context import SYSTEM_ROLE, acting_as_system, current_actor, set_actor
from identity.login import login_identity
from identity.models import User
from identity.otp_delivery import OutboxOtpSender
from identity.roles import Role
from licensing.service import record_licence
from oversight.service import set_review_period
from positions.models import Area, AreaLevel, Position
from positions.service import assign
from stock.service import set_opening_balance
from transactions.models import Transaction
from transactions.service import Transport, decide, request_decision_code, start_transaction

TEST_PASSWORD = "correct-horse-battery-9"
DEMO_GSTIN = "99AAAAA0000A1Z5"  # state code 99 does not exist: can never match a real business
BUYER_GSTIN = "99BBBBB1111B1Z5"
TEST_TRANSPORT = Transport(
    name="Ravi Transport Co",
    id_number="GJ-TR-4411",
    vehicle_number="GJ01AB1234",
    route="Sanand to Bopal",
)


@pytest.fixture
def app_db(db):
    # SET ROLE is undone automatically when the test transaction rolls back.
    with connection.cursor() as cursor:
        cursor.execute("SET ROLE gj_app")


_emails = count(1)


@pytest.fixture
def make_user(db):
    """An account. Officials get a unique sign-in email unless one is given."""

    def _make(
        role=Role.LICENSEE,
        password=TEST_PASSWORD,
        contact="+919800000001",
        email=None,
        must_change_password=False,
    ) -> User:
        if email is None:
            email = "" if role == Role.LICENSEE else f"user{next(_emails)}@test.example"
        return User.objects.create_user(
            role=role,
            password=password,
            contact=contact,
            email=email,
            must_change_password=must_change_password,
        )

    return _make


def login_body(user, password=TEST_PASSWORD) -> dict:
    """The sign-in request for `user`: its sign-in role and identifier (GSTIN or email)."""
    role, identifier = login_identity(user)
    assert role, f"{user.user_id} ({user.role}) has no way to sign in"
    return {"role": role, "identifier": identifier, "password": password}


def api_login(client, user, otp_outbox, password=TEST_PASSWORD):
    """Sign in through the real API (password, then the code); returns the verify response."""
    started = client.post(
        "/api/auth/login", login_body(user, password), content_type="application/json"
    )
    assert started.status_code == 200, started.content
    return client.post(
        "/api/auth/login/verify",
        {"challenge_id": started.json()["challenge_id"], "code": otp_outbox[-1][1]},
        content_type="application/json",
    )


@pytest.fixture
def audit_actions():
    """Return a function listing audit actions recorded so far in this test."""

    def _read() -> list[str]:
        with transaction.atomic():
            previous_user_id, previous_role = current_actor()
            try:
                set_actor(user_id="test", role=SYSTEM_ROLE)
                return list(AuditEvent.objects.order_by("id").values_list("action", flat=True))
            finally:
                set_actor(user_id=previous_user_id or "", role=previous_role or "")

    return _read


@pytest.fixture
def otp_outbox():
    OutboxOtpSender.outbox.clear()
    yield OutboxOtpSender.outbox
    OutboxOtpSender.outbox.clear()


def _permissions(**overrides):
    values = dict(
        may_buy=True,
        may_sell=True,
        may_transport=False,
        max_stock_qty=Decimal("1000"),
        max_per_transaction_qty=Decimal("500"),
        validity_months=12,
    )
    values.update(overrides)
    return values


@pytest.fixture
def catalogue(db):
    spirits = SubstanceClass.objects.create(code="SPIRITS", name="Spirits")
    whisky = Substance.objects.create(
        code="WHISKY", name="Whisky", substance_class=spirits, unit=Unit.LITRE
    )
    rum = Substance.objects.create(code="RUM", name="Rum", substance_class=spirits, unit=Unit.LITRE)
    retail = LicenceType.objects.create(code="RETAIL", name="Retail")
    wholesale = LicenceType.objects.create(code="WHOLESALE", name="Wholesale")
    retail_rule = LicenceTypeRule.objects.create(licence_type=retail, substance_class=spirits)
    add_rule_version(retail_rule, created_by="test", **_permissions())
    wholesale_rule = LicenceTypeRule.objects.create(licence_type=wholesale, substance_class=spirits)
    add_rule_version(
        wholesale_rule,
        created_by="test",
        **_permissions(
            may_transport=True,
            max_stock_qty=Decimal("50000"),
            max_per_transaction_qty=Decimal("10000"),
        ),
    )
    return SimpleNamespace(
        spirits=spirits,
        whisky=whisky,
        rum=rum,
        retail=retail,
        wholesale=wholesale,
        retail_rule=retail_rule,
        wholesale_rule=wholesale_rule,
    )


@pytest.fixture
def org(db):
    state = Area.objects.create(code="GJ", name="Gujarat", level=AreaLevel.STATE)
    ahmedabad = Area.objects.create(
        code="GJ-AHD", name="Ahmedabad", level=AreaLevel.DISTRICT, parent=state
    )
    sanand = Area.objects.create(
        code="GJ-AHD-SND", name="Sanand", level=AreaLevel.TALUKA, parent=ahmedabad
    )
    area_officer = Position.objects.create(code="AO-SND", title="Area Officer, Sanand", area=sanand)
    district_officer = Position.objects.create(
        code="DO-AHD", title="District Officer, Ahmedabad", area=ahmedabad
    )
    return SimpleNamespace(
        state=state,
        ahmedabad=ahmedabad,
        sanand=sanand,
        area_officer=area_officer,
        district_officer=district_officer,
    )


@pytest.fixture
def make_licence(catalogue, org):
    numbers = count(1)

    def _make(
        *,
        gstin=DEMO_GSTIN,
        licence_type=None,
        substance=None,
        substance_class=None,
        starts_on=date(2026, 1, 1),
        ends_on=date(2047, 12, 31),  # far future so date-sensitive tests don't expire
        contact="+919800000101",
        holder_name="Sanand Test Traders",
        area=None,
    ):
        if substance is None and substance_class is None:
            substance_class = catalogue.spirits
        with acting_as_system("test"):
            return record_licence(
                number=f"GJ/TEST/{next(numbers):04d}",
                gstin=gstin,
                holder_name=holder_name,
                contact=contact,
                licence_type=licence_type or catalogue.retail,
                area=area or org.sanand,
                starts_on=starts_on,
                ends_on=ends_on,
                recorded_by="test",
                substance=substance,
                substance_class=substance_class,
            )

    return _make


@pytest.fixture
def make_licensee(db):
    """A LICENSEE account linked to the licence's business (as enrolment would create it)."""

    def _make(licence, contact="+919800000900") -> User:
        return User.objects.create_user(
            role=Role.LICENSEE,
            password=TEST_PASSWORD,
            contact=contact,
            licensee_gstin_index=licence.gstin_index,
        )

    return _make


@pytest.fixture
def make_member(make_user, make_licence, make_licensee, org):
    """An account of `role` that can sign in: a licensee whose business has a licence on record,
    or an officer holding the Sanand Area Officer position (replacing any holder)."""
    numbers = count(1)

    def _make(role, contact="+919800000001") -> User:
        if role == Role.LICENSEE:
            licence = make_licence(gstin=f"99CCCCC{next(numbers):04d}C1Z5", contact=contact)
            return make_licensee(licence, contact=contact)
        user = make_user(role=role, contact=contact)
        if role == Role.PERSONNEL:
            assign(org.area_officer, user, by="test")
        return user

    return _make


@pytest.fixture
def trade(catalogue, org, make_licence, make_licensee, make_user):
    """A seller and a buyer (Retail/Spirits licences in Sanand), the Area Officer for Sanand,
    the District superintendent, and 400 L of whisky in the seller's stock."""
    seller_licence = make_licence(holder_name="Sanand Spirits Pvt Ltd", contact="+919800000201")
    buyer_licence = make_licence(
        gstin=BUYER_GSTIN, holder_name="Bopal Bar & Kitchen", contact="+919800000202"
    )
    officer = make_user(role=Role.PERSONNEL, contact="+919800000301")
    superintendent = make_user(role=Role.PERSONNEL, contact="+919800000302")
    assign(org.area_officer, officer, by="test")
    assign(org.district_officer, superintendent, by="test")
    with acting_as_system("test"):
        set_opening_balance(
            gstin_index=seller_licence.gstin_index,
            substance=catalogue.whisky,
            quantity=Decimal("400"),
            by="test",
        )
    return SimpleNamespace(
        seller_licence=seller_licence,
        buyer_licence=buyer_licence,
        seller=make_licensee(seller_licence, contact="+919800000201"),
        buyer=make_licensee(buyer_licence, contact="+919800000202"),
        officer=officer,
        superintendent=superintendent,
    )


def _sign(user, tx, outcome, otp_outbox, reason_code="", comment=""):
    set_actor(user_id=user.user_id, role=user.role)
    challenge = request_decision_code(reference=tx.reference, user=user)
    return decide(
        reference=tx.reference,
        user=user,
        challenge_id=str(challenge.public_id),
        code=otp_outbox[-1][1],
        outcome=outcome,
        reason_code=reason_code,
        comment=comment,
    )


@pytest.fixture
def review_setting(org):
    with acting_as_system("test"):
        return set_review_period(
            position=org.district_officer, days=15, by="test", starts_on=date(2026, 6, 1)
        )


@pytest.fixture
def threshold(catalogue):
    """Spirits above 200 need the superintendent's final approval."""
    with acting_as_system("test"):
        return add_threshold_version(
            substance_class=catalogue.spirits,
            superintendent_above_qty=Decimal("200"),
            created_by="test",
        )


@pytest.fixture
def settle(trade, catalogue, otp_outbox):
    """Drive a transaction through the real services (seller starts, buyer then officer decide,
    then the superintendent when the officer recommended and `superintendent` is given)."""

    def _settle(
        qty="10",
        *,
        buyer="CONFIRM",
        officer="APPROVE",
        superintendent=None,
        reason_code="",
        comment="",
    ):
        set_actor(user_id=trade.seller.user_id, role=trade.seller.role)
        tx = start_transaction(
            seller=trade.seller,
            buyer_gstin=BUYER_GSTIN,
            substance=catalogue.whisky,
            quantity=Decimal(qty),
            transport=TEST_TRANSPORT,
        )
        tx = _sign(
            trade.buyer,
            tx,
            buyer,
            otp_outbox,
            reason_code=reason_code if buyer == "REJECT" else "",
            comment=comment if buyer == "REJECT" else "",
        )
        if buyer == "CONFIRM" and officer:
            tx = _sign(
                trade.officer,
                tx,
                officer,
                otp_outbox,
                reason_code=reason_code if officer == "REJECT" else "",
                comment=comment if officer == "REJECT" else "",
            )
        if officer == "RECOMMEND" and superintendent:
            tx = _sign(
                trade.superintendent,
                tx,
                superintendent,
                otp_outbox,
                reason_code=reason_code if superintendent == "REJECT" else "",
                comment=comment if superintendent == "REJECT" else "",
            )
        return tx

    return _settle


def set_decided_on(tx, day):
    """Move a settled transaction's decision time to noon (local) on `day` - for period tests."""
    moment = timezone.make_aware(datetime.combine(day, time(12, 0)))
    with acting_as_system("test"):
        Transaction.objects.filter(pk=tx.pk).update(decided_at=moment)
