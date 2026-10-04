"""Catalogue reads for any logged-in user: licence types with their latest rules, and classes."""

from decimal import Decimal

import pytest

from catalogue.models import LicenceType, LicenceTypeRule, SubstanceClass
from catalogue.service import add_rule_version
from tests.test_transaction_api import login

pytestmark = pytest.mark.django_db


def test_licence_types_show_latest_rule_versions(app_db, client, catalogue, trade, otp_outbox):
    add_rule_version(
        catalogue.retail_rule,
        created_by="test",
        may_buy=True,
        may_sell=False,
        may_transport=False,
        max_stock_qty=Decimal("2000"),
        max_per_transaction_qty=Decimal("300"),
        validity_months=24,
    )
    rum_rule = LicenceTypeRule.objects.create(
        licence_type=catalogue.retail, substance=catalogue.rum
    )
    LicenceTypeRule.objects.create(licence_type=catalogue.wholesale, substance=catalogue.rum)
    add_rule_version(
        rum_rule,
        created_by="test",
        may_buy=True,
        may_sell=True,
        may_transport=True,
        max_stock_qty=Decimal("100"),
        max_per_transaction_qty=Decimal("10"),
        validity_months=6,
    )
    LicenceType.objects.create(code="BEER_BAR", name="Beer bar", description="On-premises beer")

    assert client.get("/api/catalogue/licence-types").status_code == 403
    login(client, trade.seller, otp_outbox)
    types = client.get("/api/catalogue/licence-types").json()
    assert [t["code"] for t in types] == ["BEER_BAR", "RETAIL", "WHOLESALE"]
    assert types[0] == {
        "code": "BEER_BAR",
        "name": "Beer bar",
        "description": "On-premises beer",
        "rules": [],
    }
    assert types[1]["rules"] == [
        {
            "scope": "Spirits",
            "scope_code": "SPIRITS",
            "scope_kind": "class",
            "unit": "L",
            "version": 2,
            "may_buy": True,
            "may_sell": False,
            "may_transport": False,
            "max_stock_qty": "2000.000",
            "max_per_transaction_qty": "300.000",
            "validity_months": 24,
        },
        {
            "scope": "Rum",
            "scope_code": "RUM",
            "scope_kind": "substance",
            "unit": "L",
            "version": 1,
            "may_buy": True,
            "may_sell": True,
            "may_transport": True,
            "max_stock_qty": "100.000",
            "max_per_transaction_qty": "10.000",
            "validity_months": 6,
        },
    ]
    # A rule with no version yet is not shown.
    assert [r["scope_code"] for r in types[2]["rules"]] == ["SPIRITS"]


def test_classes(app_db, client, catalogue, trade, otp_outbox):
    SubstanceClass.objects.create(code="BEER", name="Beer")  # no substances yet: unit unknown
    assert client.get("/api/catalogue/classes").status_code == 403
    login(client, trade.officer, otp_outbox)
    assert client.get("/api/catalogue/classes").json() == [
        {"code": "BEER", "name": "Beer", "unit": None},
        {"code": "SPIRITS", "name": "Spirits", "unit": "L"},
    ]
