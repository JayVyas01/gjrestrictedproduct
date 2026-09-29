from datetime import date
from decimal import Decimal

import pytest
from django.db import DatabaseError, connection, transaction

from catalogue.models import LicenceType
from catalogue.service import add_rule_version
from core.db_context import acting_as_system, set_actor
from identity.roles import Role
from licensing.models import (
    Licence,
    LicencePermissionsSnapshot,
    LicenceStatus,
    LicenceValidityPeriod,
)
from licensing.service import (
    InvalidLicenceData,
    LicenceNotPermitted,
    covers,
    current_permissions,
    find_by_number,
    record_renewal,
    set_status,
    trading_permitted,
)
from tests.conftest import DEMO_GSTIN, _permissions

pytestmark = pytest.mark.django_db


def test_recorded_licence_freezes_rule_permissions(app_db, make_licence):
    licence = make_licence()
    with acting_as_system("test"):
        snapshot = current_permissions(licence)
    assert (snapshot.may_buy, snapshot.may_sell) == (True, True)
    assert snapshot.max_per_transaction_qty == Decimal("500")


def test_rule_change_does_not_touch_existing_licence(app_db, catalogue, make_licence):
    licence = make_licence()
    add_rule_version(
        catalogue.retail_rule,
        created_by="test",
        **_permissions(max_per_transaction_qty=Decimal("50")),
    )
    with acting_as_system("test"):
        assert current_permissions(licence).max_per_transaction_qty == Decimal("500")


def test_renewal_takes_a_fresh_snapshot_of_the_latest_rule(
    app_db, catalogue, make_licence, audit_actions
):
    licence = make_licence()
    add_rule_version(
        catalogue.retail_rule,
        created_by="test",
        **_permissions(max_per_transaction_qty=Decimal("50")),
    )
    with acting_as_system("test"):
        record_renewal(
            licence, starts_on=date(2027, 1, 1), ends_on=date(2027, 12, 31), recorded_by="test"
        )
        assert current_permissions(licence).max_per_transaction_qty == Decimal("50")
    assert audit_actions() == ["licence.recorded", "licence.renewal_recorded"]


def test_licence_type_without_rule_cannot_be_recorded(app_db, make_licence):
    manufacturer = LicenceType.objects.create(code="MANUFACTURER", name="Manufacturer")
    with pytest.raises(LicenceNotPermitted):
        make_licence(licence_type=manufacturer)


def test_refused_licence_leaves_no_partial_record(app_db, make_licence):
    manufacturer = LicenceType.objects.create(code="MANUFACTURER", name="Manufacturer")
    with pytest.raises(LicenceNotPermitted):
        make_licence(licence_type=manufacturer)
    with acting_as_system("test"):
        assert Licence.objects.count() == 0


def test_malformed_gstin_is_rejected(app_db, make_licence):
    with pytest.raises(InvalidLicenceData, match="GSTIN"):
        make_licence(gstin="NOT-A-GSTIN")


def test_period_must_end_after_it_starts(app_db, make_licence):
    with pytest.raises(InvalidLicenceData, match="end"):
        make_licence(starts_on=date(2026, 6, 1), ends_on=date(2026, 5, 31))


def test_identifiers_are_encrypted_at_rest(app_db, make_licence):
    licence = make_licence()
    with acting_as_system("test"), connection.cursor() as cursor:
        cursor.execute(
            "SELECT number_encrypted, gstin_encrypted FROM licensing_licence WHERE id = %s",
            [licence.id],
        )
        number_raw, gstin_raw = cursor.fetchone()
    assert "GJ/TEST" not in number_raw
    assert DEMO_GSTIN not in gstin_raw


def test_find_by_number_is_exact_but_forgiving_about_case_and_spaces(app_db, make_licence):
    licence = make_licence()
    with acting_as_system("test"):
        assert find_by_number("  gj/test/0001 ") == licence
        assert find_by_number("GJ/TEST/000") is None
        assert find_by_number("GJ/TEST") is None


@pytest.mark.parametrize(
    ("on", "expected"),
    [
        (date(2025, 12, 31), False),
        (date(2026, 1, 1), True),
        (date(2026, 12, 31), True),
        (date(2027, 1, 1), False),
    ],
)
def test_trading_permitted_follows_validity_period(app_db, make_licence, on, expected):
    licence = make_licence()
    with acting_as_system("test"):
        assert trading_permitted(licence, on) is expected


def test_gap_between_periods_is_not_permitted(app_db, make_licence):
    licence = make_licence()
    with acting_as_system("test"):
        record_renewal(
            licence, starts_on=date(2027, 3, 1), ends_on=date(2028, 2, 29), recorded_by="test"
        )
        assert trading_permitted(licence, date(2027, 2, 1)) is False
        assert trading_permitted(licence, date(2027, 3, 1)) is True


@pytest.mark.parametrize("status", [LicenceStatus.SUSPENDED, LicenceStatus.REVOKED])
def test_suspended_or_revoked_licence_cannot_trade(app_db, make_licence, status):
    licence = make_licence()
    with acting_as_system("test"):
        set_status(licence, status, by="test", reason="inspection")
        assert trading_permitted(licence, date(2026, 6, 1)) is False


def test_covers_substance_directly_or_through_its_class(app_db, catalogue, make_licence):
    class_licence = make_licence()
    whisky_licence = make_licence(substance=catalogue.whisky)
    assert covers(class_licence, catalogue.rum)
    assert covers(whisky_licence, catalogue.whisky)
    assert not covers(whisky_licence, catalogue.rum)


def test_holder_sees_only_their_own_licences(app_db, make_licence, make_user):
    mine = make_licence()
    make_licence(gstin="99BBBBB1111B1Z5")
    holder = make_user(role=Role.LICENSEE)
    holder.licensee_gstin_index = mine.gstin_index
    holder.save(update_fields=["licensee_gstin_index"])
    with transaction.atomic():
        set_actor(user_id=holder.user_id, role=Role.LICENSEE)
        assert list(Licence.objects.all()) == [mine]
        assert LicenceValidityPeriod.objects.count() == 1


def test_anonymous_context_sees_no_licences(app_db, make_licence):
    make_licence()
    assert Licence.objects.count() == 0


def test_licensing_authority_sees_all_licences(app_db, make_licence):
    make_licence()
    make_licence(gstin="99BBBBB1111B1Z5")
    with transaction.atomic():
        set_actor(user_id="GJLAUSER0001", role=Role.LICENSING_AUTHORITY)
        assert Licence.objects.count() == 2


def test_licensee_cannot_record_a_licence(app_db, catalogue, org):
    with pytest.raises(DatabaseError):
        with transaction.atomic():
            set_actor(user_id="GJLICENSEE01", role=Role.LICENSEE)
            Licence.objects.create(
                number_encrypted="x",
                number_index="x" * 64,
                gstin_encrypted="x",
                gstin_index="y" * 64,
                holder_name="x",
                contact_encrypted="x",
                licence_type=catalogue.retail,
                substance_class=catalogue.spirits,
                area=org.sanand,
            )


def test_validity_periods_cannot_be_edited(app_db, make_licence):
    make_licence()
    with pytest.raises(DatabaseError, match="permission denied"):
        with transaction.atomic(), acting_as_system("test"):
            LicenceValidityPeriod.objects.update(ends_on=date(2099, 1, 1))


def test_acting_as_system_restores_previous_actor(app_db):
    from core.db_context import current_actor

    set_actor(user_id="GJLICENSEE01", role=Role.LICENSEE)
    with acting_as_system("test"):
        assert current_actor()[1] == "SYSTEM"
    assert current_actor() == ("GJLICENSEE01", "LICENSEE")


def test_periods_and_snapshots_blocked_even_for_table_owner(db, make_licence):
    licence = make_licence()
    with pytest.raises(DatabaseError, match="append-only"), transaction.atomic():
        LicenceValidityPeriod.objects.filter(licence=licence).update(ends_on=date(2099, 1, 1))
    with pytest.raises(DatabaseError, match="append-only"), transaction.atomic():
        LicencePermissionsSnapshot.objects.filter(licence=licence).update(may_sell=False)


def test_only_status_can_change_on_a_licence(app_db, make_licence):
    licence = make_licence()
    with pytest.raises(DatabaseError, match="permission denied"), transaction.atomic():
        set_actor(user_id="GJLAUSER0001", role=Role.LICENSING_AUTHORITY)
        Licence.objects.filter(pk=licence.pk).update(gstin_index="z" * 64)
    with transaction.atomic():
        set_actor(user_id="GJLAUSER0001", role=Role.LICENSING_AUTHORITY)
        set_status(licence, LicenceStatus.SUSPENDED, by="GJLAUSER0001", reason="inspection")
        assert Licence.objects.get(pk=licence.pk).status == LicenceStatus.SUSPENDED


def test_acting_as_system_does_not_mask_database_errors(app_db):
    with pytest.raises(DatabaseError, match="division by zero"), transaction.atomic():
        with acting_as_system("test"), connection.cursor() as cursor:
            cursor.execute("SELECT 1/0")
