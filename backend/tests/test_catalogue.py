from decimal import Decimal

import pytest
from django.db import DatabaseError, IntegrityError, transaction

from catalogue.models import LicenceType, LicenceTypeRule, LicenceTypeRuleVersion
from catalogue.service import add_rule_version, resolve_rule
from tests.conftest import _permissions

pytestmark = pytest.mark.django_db


def test_class_rule_applies_to_every_substance_in_the_class(app_db, catalogue):
    for substance in (catalogue.whisky, catalogue.rum):
        version = resolve_rule(catalogue.retail, substance=substance)
        assert version.rule == catalogue.retail_rule


def test_substance_rule_overrides_class_rule(app_db, catalogue):
    rum_only = LicenceTypeRule.objects.create(
        licence_type=catalogue.retail, substance=catalogue.rum
    )
    add_rule_version(rum_only, created_by="test", **_permissions(may_sell=False))
    version = resolve_rule(catalogue.retail, substance=catalogue.rum)
    assert version.rule == rum_only
    assert version.may_sell is False
    assert resolve_rule(catalogue.retail, substance=catalogue.whisky).may_sell is True


def test_no_rule_means_not_permitted(app_db, catalogue):
    manufacturer = LicenceType.objects.create(code="MANUFACTURER", name="Manufacturer")
    assert resolve_rule(manufacturer, substance=catalogue.whisky) is None


def test_class_scope_resolves_class_rule(app_db, catalogue):
    assert (
        resolve_rule(catalogue.retail, substance_class=catalogue.spirits).rule
        == catalogue.retail_rule
    )


def test_latest_version_wins_and_versions_increment(app_db, catalogue):
    newer = add_rule_version(
        catalogue.retail_rule, created_by="test", **_permissions(max_stock_qty=Decimal("2000"))
    )
    assert newer.version == 2
    assert resolve_rule(catalogue.retail, substance=catalogue.whisky) == newer


def test_rule_needs_exactly_one_scope(app_db, catalogue):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            LicenceTypeRule.objects.create(
                licence_type=catalogue.retail,
                substance=catalogue.whisky,
                substance_class=catalogue.spirits,
            )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            LicenceTypeRule.objects.create(licence_type=catalogue.wholesale)


def test_rule_versions_cannot_be_edited(app_db, catalogue):
    with pytest.raises(DatabaseError, match="permission denied"):
        with transaction.atomic():
            LicenceTypeRuleVersion.objects.update(may_sell=False)


def test_limits_must_be_positive(app_db, catalogue):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            add_rule_version(
                catalogue.retail_rule, created_by="test", **_permissions(max_stock_qty=Decimal("0"))
            )
