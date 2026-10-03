"""The counts each role's home screen shows. Everything is read under the caller's own
row-level security, so a count never includes rows the caller could not open."""

from datetime import date, timedelta

from django.db.models import Max

from alerts.models import AuthorityAlert
from identity.models import User
from identity.roles import Role
from licensing.models import Licence, LicenceStatus
from oversight.models import OversightBatch
from oversight.service import batch_status
from positions.models import AreaLevel, Position
from positions.service import positions_held
from transactions.models import Transaction, TransactionStatus
from transactions.service import awaiting_decision_for

IN_PROGRESS = (
    TransactionStatus.AWAITING_BUYER,
    TransactionStatus.AWAITING_OFFICER,
    TransactionStatus.AWAITING_SUPERINTENDENT,
)
EXPIRY_WINDOW = timedelta(days=30)


def home_counts(user: User, today: date) -> dict:
    if user.role == Role.LICENSEE:
        return _licensee(user)
    if user.role == Role.PERSONNEL:
        return _personnel(user, today)
    if user.role == Role.LICENSING_AUTHORITY:
        return _licensing_authority(today)
    return _head_authority()  # Head Authority and Software Owner


def _unacknowledged_alerts() -> int:
    return AuthorityAlert.objects.filter(acknowledgement__isnull=True).count()


def _licensee(user: User) -> dict:
    return {
        "awaiting_your_decision": awaiting_decision_for(user).count(),
        "sales_in_progress": Transaction.objects.filter(
            seller_gstin_index=user.licensee_gstin_index, status__in=IN_PROGRESS
        ).count(),
    }


def _personnel(user: User, today: date) -> dict:
    batches = OversightBatch.objects.filter(position__in=positions_held(user))
    statuses = [(batch_status(batch, today), batch.due_on()) for batch in batches]
    open_due = [due for status, due in statuses if status == "OPEN"]
    return {
        "awaiting_your_decision": awaiting_decision_for(user).count(),
        "unacknowledged_alerts": _unacknowledged_alerts(),
        "open_batches": len(open_due),
        "overdue_batches": sum(status == "OVERDUE" for status, _ in statuses),
        "next_due": min(open_due).isoformat() if open_due else None,
    }


def _licensing_authority(today: date) -> dict:
    expiring = (
        Licence.objects.filter(status=LicenceStatus.ACTIVE)
        .annotate(last_day=Max("validity_periods__ends_on"))
        .filter(last_day__gte=today, last_day__lte=today + EXPIRY_WINDOW)
    )
    without_period = Position.objects.filter(
        area__level=AreaLevel.DISTRICT, review_setting__isnull=True
    )
    return {
        "expiring_licences_30d": expiring.count(),
        "districts_without_review_period": without_period.count(),
    }


def _head_authority() -> dict:
    return {
        "unacknowledged_alerts": _unacknowledged_alerts(),
        "awaiting_superintendent": Transaction.objects.filter(
            status=TransactionStatus.AWAITING_SUPERINTENDENT
        ).count(),
    }
