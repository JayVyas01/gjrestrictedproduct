import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from identity.roles import Role
from positions.models import AreaLevel, PersonnelAssignment
from positions.service import assign, covering_position, current_holder, positions_held

pytestmark = pytest.mark.django_db


def test_covering_position_at_same_level(app_db, org):
    assert covering_position(org.sanand, AreaLevel.TALUKA) == org.area_officer


def test_covering_position_walks_up_the_hierarchy(app_db, org):
    assert covering_position(org.sanand, AreaLevel.DISTRICT) == org.district_officer


def test_covering_position_none_when_level_has_no_position(app_db, org):
    assert covering_position(org.sanand, AreaLevel.STATE) is None


def test_assign_makes_user_the_holder(app_db, org, make_user, audit_actions):
    officer = make_user(role=Role.PERSONNEL)
    assign(org.area_officer, officer, by="test")
    assert current_holder(org.area_officer) == officer
    assert positions_held(officer) == [org.area_officer]
    assert audit_actions() == ["position.assigned"]


def test_transfer_moves_the_position_immediately(app_db, org, make_user):
    old, new = make_user(role=Role.PERSONNEL), make_user(role=Role.PERSONNEL)
    assign(org.area_officer, old, by="test")
    assign(org.area_officer, new, by="test")
    assert current_holder(org.area_officer) == new
    assert positions_held(old) == []
    assert positions_held(new) == [org.area_officer]


def test_only_personnel_can_hold_positions(app_db, org, make_user):
    with pytest.raises(ValueError, match="Authorised Personnel"):
        assign(org.area_officer, make_user(role=Role.LICENSEE), by="test")


def test_vacant_position_has_no_holder(app_db, org):
    assert current_holder(org.district_officer) is None


def test_database_allows_one_active_holder_per_position(app_db, org, make_user):
    assign(org.area_officer, make_user(role=Role.PERSONNEL), by="test")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PersonnelAssignment.objects.create(
                position=org.area_officer,
                user=make_user(role=Role.PERSONNEL),
                started_at=timezone.now(),
            )
