"""Raise and acknowledge authority alerts.

raise_* run inside the caller's SYSTEM block (decision or flag), before its audit record().
acknowledge checks in plain Python that the user currently holds the addressed position.
"""

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from alerts.models import AlertAcknowledgement, AlertKind, AuthorityAlert
from audit.service import record
from core.db_context import acting_as_system
from identity.models import User
from positions.models import Position
from positions.service import positions_held
from reasons.models import ReasonCode
from transactions.models import Transaction, TransactionStatus

PATTERN_WINDOW = timedelta(days=30)


class NotAllowed(Exception):
    pass


class AlreadyAcknowledged(NotAllowed):
    pass


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def pattern_text(count: int) -> str:
    return f"{ordinal(count)} buyer rejection for this seller in the last 30 days"


def _recent_rejections(tx: Transaction) -> int:
    """Buyer rejections of this seller in the window. A STOCK_LIMIT rejection (the buyer's own
    limit) says nothing about the seller and is not counted."""
    return (
        Transaction.objects.filter(
            seller_gstin_index=tx.seller_gstin_index,
            status=TransactionStatus.REJECTED_BY_BUYER,
            decided_at__gte=timezone.now() - PATTERN_WINDOW,
        )
        .exclude(decisions__step="BUYER", decisions__reason__code="STOCK_LIMIT")
        .count()
    )


def raise_buyer_rejection_alerts(
    tx: Transaction, reason: ReasonCode, comment: str
) -> list[AuthorityAlert]:
    count = _recent_rejections(tx)
    return [
        AuthorityAlert.objects.create(
            kind=AlertKind.BUYER_REJECTION,
            position=position,
            transaction=tx,
            reason=reason,
            comment=comment,
            pattern_count=count,
        )
        for position in (tx.designated_position, tx.superintendent_position)
    ]


def raise_flag_alert(
    *, tx: Transaction, position: Position, reason: ReasonCode, comment: str
) -> AuthorityAlert:
    return AuthorityAlert.objects.create(
        kind=AlertKind.SUPERINTENDENT_FLAG,
        position=position,
        transaction=tx,
        reason=reason,
        comment=comment,
    )


def _already_acknowledged(alert: AuthorityAlert) -> bool:
    return AlertAcknowledgement.objects.filter(alert=alert).exists()


def acknowledge(*, alert_id: int, user: User, note: str = "") -> AlertAcknowledgement:
    alert = AuthorityAlert.objects.select_related("position").filter(pk=alert_id).first()
    if alert is None or alert.position not in positions_held(user):
        raise NotAllowed("Only the officer holding this position can acknowledge this alert.")
    with acting_as_system("acknowledge_alert"):
        if _already_acknowledged(alert):
            raise AlreadyAcknowledged("This alert is already acknowledged.")
        try:
            with transaction.atomic():
                ack = AlertAcknowledgement.objects.create(
                    alert=alert, user_id=user.user_id, note=note.strip()
                )
        except IntegrityError:
            raise AlreadyAcknowledged("This alert is already acknowledged.") from None
        record(
            action="alert.acknowledged",
            actor=user.user_id,
            subject_type="alert",
            subject_id=str(alert.id),
        )
    return ack
