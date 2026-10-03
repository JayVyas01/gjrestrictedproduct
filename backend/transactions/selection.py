"""Pick the licence a business uses for a given substance and action.

Eligible: covers the substance, trading is permitted on the day, and the frozen permissions for
that substance allow the action. Preference: a licence scoped to that exact substance, then the
earliest recorded. Call inside a context that can read the business's licences (SYSTEM).
"""

from datetime import date

from catalogue.models import Substance
from licensing.models import Licence, LicenceStatus
from licensing.service import covers, current_permissions, trading_permitted


def _allows(licence: Licence, substance: Substance, action: str) -> bool:
    permissions = current_permissions(licence, substance)
    if permissions is None:
        return False
    return permissions.may_sell if action == "sell" else permissions.may_buy


def licence_eligible(licence: Licence, substance: Substance, action: str, on: date) -> bool:
    """True if the licence covers the substance, may trade on the day and allows the action."""
    return (
        covers(licence, substance)
        and trading_permitted(licence, on)
        and _allows(licence, substance, action)
    )


def select_licence(gstin_index: str, substance: Substance, action: str, on: date) -> Licence | None:
    candidates = Licence.objects.filter(
        gstin_index=gstin_index, status=LicenceStatus.ACTIVE
    ).order_by("id")
    eligible = [
        licence for licence in candidates if licence_eligible(licence, substance, action, on)
    ]
    eligible.sort(key=lambda licence: (licence.substance_id is None, licence.id))
    return eligible[0] if eligible else None
