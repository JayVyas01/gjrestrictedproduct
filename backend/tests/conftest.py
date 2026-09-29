"""Shared test fixtures.

Use `app_db` (not `db`) for anything that exercises application behaviour, so the test runs
with the same restricted privileges as production. Use plain `db` only when a test must act as
the schema owner, for example to simulate an attacker tampering with the audit table.
Never use `transactional_db`: its TRUNCATE-based teardown is blocked by the audit trigger.
"""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.db import connection, transaction

from audit.models import AuditEvent
from catalogue.models import LicenceType, LicenceTypeRule, Substance, SubstanceClass, Unit
from catalogue.service import add_rule_version
from core.db_context import SYSTEM_ROLE, current_actor, set_actor
from identity.models import User
from identity.otp_delivery import OutboxOtpSender
from identity.roles import Role

TEST_PASSWORD = "correct-horse-battery-9"


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
