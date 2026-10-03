from decimal import Decimal

import pytest
from django.db import DatabaseError, IntegrityError, transaction

from catalogue.models import ApprovalThreshold, ApprovalThresholdVersion
from catalogue.service import add_threshold_version, approval_chain_for, resolve_threshold
from core.db_context import acting_as_system
from transactions.models import ApprovalChain, Transaction

pytestmark = pytest.mark.django_db


def test_no_threshold_means_officer_chain(app_db, catalogue):
    assert resolve_threshold(catalogue.whisky) is None
    assert approval_chain_for(catalogue.whisky, Decimal("100000")) == "OFFICER"


def test_class_threshold_applies_to_its_substances(app_db, catalogue):
    add_threshold_version(
        substance_class=catalogue.spirits, superintendent_above_qty=Decimal("200"), created_by="t"
    )
    assert approval_chain_for(catalogue.whisky, Decimal("201")) == "OFFICER_THEN_SUPERINTENDENT"
    assert approval_chain_for(catalogue.whisky, Decimal("200")) == "OFFICER"
    assert approval_chain_for(catalogue.rum, Decimal("201")) == "OFFICER_THEN_SUPERINTENDENT"


def test_substance_threshold_beats_class(app_db, catalogue):
    add_threshold_version(
        substance=catalogue.whisky, superintendent_above_qty=Decimal("100"), created_by="t"
    )
    add_threshold_version(
        substance_class=catalogue.spirits, superintendent_above_qty=Decimal("500"), created_by="t"
    )
    assert approval_chain_for(catalogue.whisky, Decimal("150")) == "OFFICER_THEN_SUPERINTENDENT"
    assert approval_chain_for(catalogue.rum, Decimal("150")) == "OFFICER"


def test_latest_threshold_version_wins(app_db, catalogue):
    first = add_threshold_version(
        substance=catalogue.whisky, superintendent_above_qty=Decimal("100"), created_by="t"
    )
    second = add_threshold_version(
        substance=catalogue.whisky, superintendent_above_qty=Decimal("300"), created_by="t"
    )
    assert (first.version, second.version) == (1, 2)
    assert first.threshold_id == second.threshold_id
    assert resolve_threshold(catalogue.whisky) == second
    assert approval_chain_for(catalogue.whisky, Decimal("150")) == "OFFICER"


def test_threshold_needs_exactly_one_scope(app_db, catalogue):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ApprovalThreshold.objects.create(
                substance=catalogue.whisky, substance_class=catalogue.spirits
            )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ApprovalThreshold.objects.create()


def test_threshold_qty_must_be_positive(app_db, catalogue):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            add_threshold_version(
                substance=catalogue.whisky, superintendent_above_qty=Decimal("0"), created_by="t"
            )


def test_threshold_versions_cannot_be_edited_by_app_role(app_db, catalogue):
    add_threshold_version(
        substance=catalogue.whisky, superintendent_above_qty=Decimal("100"), created_by="t"
    )
    with pytest.raises(DatabaseError, match="permission denied"):
        with transaction.atomic():
            ApprovalThresholdVersion.objects.update(superintendent_above_qty=Decimal("1"))


def test_threshold_versions_are_append_only_even_for_owner(db, catalogue):
    add_threshold_version(
        substance=catalogue.whisky, superintendent_above_qty=Decimal("100"), created_by="t"
    )
    with pytest.raises(DatabaseError, match="append-only"):
        with transaction.atomic():
            ApprovalThresholdVersion.objects.update(superintendent_above_qty=Decimal("1"))


def test_approval_chain_cannot_be_updated_by_app_role(app_db, settle):
    tx = settle(officer=None)
    assert tx.approval_chain == ApprovalChain.OFFICER
    with pytest.raises(DatabaseError, match="permission denied"):
        with transaction.atomic(), acting_as_system("test"):
            Transaction.objects.filter(pk=tx.pk).update(
                approval_chain=ApprovalChain.OFFICER_THEN_SUPERINTENDENT
            )
