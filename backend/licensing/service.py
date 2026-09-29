"""Record licences issued by the existing process, and answer "may this licence trade?".

Writes need a Licensing Authority or SYSTEM context (row-level security enforces this).
"""

import re
from datetime import date

from django.db import transaction

from audit.service import record
from catalogue.models import LicenceType, Substance, SubstanceClass
from catalogue.service import resolve_rule
from core import crypto
from licensing.models import (
    Licence,
    LicencePermissionsSnapshot,
    LicenceStatus,
    LicenceValidityPeriod,
)
from positions.models import Area

GSTIN_PATTERN = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


class LicenceNotPermitted(Exception):
    """No licence type rule allows this licence type for this substance or class."""


class InvalidLicenceData(Exception):
    pass


def _check_period(starts_on: date, ends_on: date) -> None:
    if ends_on < starts_on:
        raise InvalidLicenceData("The validity period must end on or after its start date")


def _snapshot(licence: Licence) -> LicencePermissionsSnapshot:
    version = resolve_rule(
        licence.licence_type, substance=licence.substance, substance_class=licence.substance_class
    )
    if version is None:
        raise LicenceNotPermitted(
            f"{licence.licence_type.name} licences are not permitted for {licence.scope_name()}"
        )
    return LicencePermissionsSnapshot.objects.create(
        licence=licence,
        rule_version=version,
        may_buy=version.may_buy,
        may_sell=version.may_sell,
        may_transport=version.may_transport,
        max_stock_qty=version.max_stock_qty,
        max_per_transaction_qty=version.max_per_transaction_qty,
    )


def record_licence(
    *,
    number: str,
    gstin: str,
    holder_name: str,
    contact: str,
    licence_type: LicenceType,
    area: Area,
    starts_on: date,
    ends_on: date,
    recorded_by: str,
    substance: Substance | None = None,
    substance_class: SubstanceClass | None = None,
) -> Licence:
    gstin = gstin.strip().upper()
    if not GSTIN_PATTERN.match(gstin):
        raise InvalidLicenceData("The GSTIN is not in the valid 15-character format")
    _check_period(starts_on, ends_on)
    with transaction.atomic():  # licence, snapshot and period exist together or not at all
        return _create_licence(
            number=number,
            gstin=gstin,
            holder_name=holder_name,
            contact=contact,
            licence_type=licence_type,
            area=area,
            starts_on=starts_on,
            ends_on=ends_on,
            recorded_by=recorded_by,
            substance=substance,
            substance_class=substance_class,
        )


def _create_licence(
    *,
    number,
    gstin,
    holder_name,
    contact,
    licence_type,
    area,
    starts_on,
    ends_on,
    recorded_by,
    substance,
    substance_class,
) -> Licence:
    licence = Licence.objects.create(
        number_encrypted=crypto.encrypt(number.strip()),
        number_index=crypto.blind_index("licence_number", number),
        gstin_encrypted=crypto.encrypt(gstin),
        gstin_index=crypto.blind_index("gstin", gstin),
        holder_name=holder_name,
        contact_encrypted=crypto.encrypt(contact),
        licence_type=licence_type,
        substance=substance,
        substance_class=substance_class,
        area=area,
    )
    _snapshot(licence)
    LicenceValidityPeriod.objects.create(
        licence=licence, starts_on=starts_on, ends_on=ends_on, recorded_by=recorded_by
    )
    record(
        action="licence.recorded",
        actor=recorded_by,
        subject_type="licence",
        subject_id=str(licence.id),
    )
    return licence


def record_renewal(
    licence: Licence, *, starts_on: date, ends_on: date, recorded_by: str
) -> LicenceValidityPeriod:
    _check_period(starts_on, ends_on)
    with transaction.atomic():
        _snapshot(licence)
        period = LicenceValidityPeriod.objects.create(
            licence=licence, starts_on=starts_on, ends_on=ends_on, recorded_by=recorded_by
        )
        record(
            action="licence.renewal_recorded",
            actor=recorded_by,
            subject_type="licence",
            subject_id=str(licence.id),
            payload={"starts_on": starts_on.isoformat(), "ends_on": ends_on.isoformat()},
        )
    return period


def set_status(licence: Licence, status: str, *, by: str, reason: str) -> None:
    licence.status = status
    licence.save(update_fields=["status"])
    record(
        action="licence.status_changed",
        actor=by,
        subject_type="licence",
        subject_id=str(licence.id),
        reason=reason,
        payload={"status": str(status)},
    )


def current_permissions(licence: Licence) -> LicencePermissionsSnapshot:
    return licence.permission_snapshots.order_by("-id").first()


def current_period(licence: Licence, on: date) -> LicenceValidityPeriod | None:
    """The period covering `on`, or else the most recent one (for display)."""
    periods = licence.validity_periods.order_by("-starts_on")
    return periods.filter(starts_on__lte=on, ends_on__gte=on).first() or periods.first()


def trading_permitted(licence: Licence, on: date) -> bool:
    if licence.status != LicenceStatus.ACTIVE:
        return False
    return licence.validity_periods.filter(starts_on__lte=on, ends_on__gte=on).exists()


def covers(licence: Licence, substance: Substance) -> bool:
    if licence.substance_id is not None:
        return licence.substance_id == substance.id
    return licence.substance_class_id == substance.substance_class_id


def find_by_number(number: str) -> Licence | None:
    """Exact match only (case and surrounding spaces ignored). No partial search exists."""
    return (
        Licence.objects.select_related("licence_type", "substance", "substance_class", "area")
        .filter(number_index=crypto.blind_index("licence_number", number))
        .first()
    )
