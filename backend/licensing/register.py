"""The licence register for authorities (B7): exact search, filters, detail.

Runs under the caller's own row-level security (Licensing Authority, Head Authority and
Software Owner read all licences). Searches and detail views are audited by blind index or
licence id only: the raw number or GSTIN never reaches the audit log. Never returns the
contact or any stock figure.
"""

from django.utils import timezone

from audit.service import record
from core import crypto
from identity.models import User
from licensing.models import Licence
from licensing.serializers import licence_card

PAGE_SIZE = 25
PERMISSION_FIELDS = (
    "may_buy",
    "may_sell",
    "may_transport",
    "max_stock_qty",
    "max_per_transaction_qty",
)


def _licences():
    return Licence.objects.select_related(
        "licence_type", "substance", "substance_class", "area"
    ).prefetch_related("validity_periods")


def _periods(licence: Licence) -> list:
    return sorted(licence.validity_periods.all(), key=lambda p: (p.starts_on, p.ends_on))


def _row(licence: Licence) -> dict:
    periods = _periods(licence)
    return {
        "id": licence.id,
        "licence_number": licence.number(),
        "holder_name": licence.holder_name,
        "licence_type": licence.licence_type.name,
        "scope": licence.scope_name(),
        "area": licence.area.name,
        "status": licence.status,
        "valid_to": periods[-1].ends_on.isoformat() if periods else None,
    }


def search(
    user: User, *, number=None, gstin=None, status=None, area_id=None, page=1
) -> tuple[list[dict], int]:
    """One page of licences (25 per page, oldest first) and the total matching count."""
    licences = _licences().order_by("id")
    indexes = {}
    if number is not None:
        indexes["number_index"] = crypto.blind_index("licence_number", number)
        licences = licences.filter(number_index=indexes["number_index"])
    if gstin is not None:
        indexes["gstin_index"] = crypto.blind_index("gstin", gstin)
        licences = licences.filter(gstin_index=indexes["gstin_index"])
    if status is not None:
        licences = licences.filter(status=status)
    if area_id is not None:
        licences = licences.filter(area_id=area_id)
    total = licences.count()
    start = (page - 1) * PAGE_SIZE
    rows = [_row(licence) for licence in licences[start : start + PAGE_SIZE]]
    if indexes:
        record(
            action="licence.register_search",
            actor=user.user_id,
            payload={**indexes, "results": total},
        )
    return rows, total


def detail(user: User, licence_id: int) -> dict | None:
    licence = _licences().filter(pk=licence_id).first()
    if licence is None:
        return None
    card = licence_card(licence, timezone.localdate())
    result = {
        **_row(licence),
        "gstin": licence.gstin(),
        "periods": [
            {"starts_on": p.starts_on.isoformat(), "ends_on": p.ends_on.isoformat()}
            for p in _periods(licence)
        ],
        "permissions": {field: card[field] for field in PERMISSION_FIELDS},
    }
    record(
        action="licence.viewed",
        actor=user.user_id,
        subject_type="licence",
        subject_id=str(licence.id),
    )
    return result
