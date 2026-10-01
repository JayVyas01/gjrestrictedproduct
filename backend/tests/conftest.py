"""Shared test fixtures.

Use `app_db` (not `db`) for anything that exercises application behaviour, so the test runs
with the same restricted privileges as production. Use plain `db` only when a test must act as
the schema owner, for example to simulate an attacker tampering with the audit table.
Never use `transactional_db`: its TRUNCATE-based teardown is blocked by the audit trigger.
"""

from datetime import date
from decimal import Decimal
from itertools import count
from types import SimpleNamespace

import pytest
from django.db import connection, transaction

from audit.models import AuditEvent
from catalogue.models import LicenceType, LicenceTypeRule, Substance, SubstanceClass, Unit
from catalogue.service import add_rule_version
from core.db_context import SYSTEM_ROLE, acting_as_system, current_actor, set_actor
from identity.models import User
from identity.otp_delivery import OutboxOtpSender
from identity.roles import Role
from licensing.service import record_licence
from positions.models import Area, AreaLevel, Position
from positions.service import assign
from stock.service import set_opening_balance

TEST_PASSWORD = "correct-horse-battery-9"
DEMO_GSTIN = "99AAAAA0000A1Z5"  # state code 99 does not exist: can never match a real business
BUYER_GSTIN = "99BBBBB1111B1Z5"


@pytest.fixture
def app_db(db):
    # SET ROLE is undone automatically when the test transaction rolls back.
    with connection.cursor() as cursor:
        cursor.execute("SET ROLE gj_app")


@pytest.fixture
def make_user(db):
    def _make(role=Role.LICENSEE, password=TEST_PASSWORD, contact="+919800000001") -> User:
        return User.objects.create_user(role=role, password=password, contact=contact)

    return _make


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
        ends_on=date(2026, 12, 31),
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
