"""Review periods and batch creation (SYSTEM context).

Periods start at the setting's starts_on and run back to back. A batch is created only once
its period has fully ended (period_end < today) and lists every APPROVED transaction whose
superintendent position it is, decided (local date) within the period. Idempotent.
"""

from datetime import date, timedelta

from django.utils import timezone

from audit.service import record
from core.db_context import acting_as_system
from oversight.models import REVIEW_PERIODS, BatchItem, OversightBatch, SuperintendentSetting
from positions.models import AreaLevel, Position
from transactions.models import Transaction, TransactionStatus


class InvalidSetting(Exception):
    pass


def _next_start(position: Position, fallback: date) -> date:
    last = position.batches.order_by("-period_end").first()
    return last.period_end + timedelta(days=1) if last else fallback


def _resolve_start(position: Position, starts_on: date | None) -> date:
    """The start date of the new period, so that no approved transaction is ever skipped.

    With batches: the day after the last batch (an explicit date must equal it). Without batches:
    the existing setting's start (an explicit date may not be later), or today for a new setting.
    """
    existing = SuperintendentSetting.objects.filter(position=position).first()
    last = position.batches.order_by("-period_end").first()
    if last:
        required = last.period_end + timedelta(days=1)
        if starts_on is not None and starts_on != required:
            raise InvalidSetting(f"The new period must start on {required.isoformat()}.")
        return required
    latest_allowed = existing.starts_on if existing else timezone.localdate()
    if existing and starts_on is not None and starts_on > latest_allowed:
        raise InvalidSetting(
            f"The new period cannot start after {latest_allowed.isoformat()}, "
            "or transactions in between would never be reviewed."
        )
    return starts_on or latest_allowed


def set_review_period(
    *, position: Position, days: int, by: str, starts_on: date | None = None
) -> SuperintendentSetting:
    if days not in REVIEW_PERIODS:
        raise InvalidSetting("The review period must be 15, 30 or 60 days.")
    if position.area.level != AreaLevel.DISTRICT:
        raise InvalidSetting(
            "Review periods can only be set for a district superintendent position."
        )
    # Lookups and write run as SYSTEM so the caller's row-level security cannot hide batches.
    with acting_as_system("set_review_period"):
        start = _resolve_start(position, starts_on)
        setting, _ = SuperintendentSetting.objects.update_or_create(
            position=position, defaults={"period_days": days, "starts_on": start, "updated_by": by}
        )
        record(
            action="oversight.review_period_set",
            actor=by,
            subject_type="position",
            subject_id=position.code,
            payload={"period_days": days, "starts_on": start.isoformat()},
        )
    return setting


def _make_batch(position: Position, start: date, end: date) -> OversightBatch:
    batch = OversightBatch.objects.create(position=position, period_start=start, period_end=end)
    approved = Transaction.objects.filter(
        superintendent_position=position,
        status=TransactionStatus.APPROVED,
        decided_at__date__gte=start,
        decided_at__date__lte=end,
    ).order_by("id")
    BatchItem.objects.bulk_create([BatchItem(batch=batch, transaction=tx) for tx in approved])
    record(
        action="oversight.batch_created",
        actor="create_due_batches",
        subject_type="batch",
        subject_id=str(batch.id),
        payload={"items": len(approved)},
    )
    return batch


def create_due_batches(today: date) -> list[OversightBatch]:
    created = []
    for setting in SuperintendentSetting.objects.select_related("position").order_by("id"):
        start = max(_next_start(setting.position, setting.starts_on), setting.starts_on)
        while (end := start + timedelta(days=setting.period_days - 1)) < today:
            created.append(_make_batch(setting.position, start, end))
            start = end + timedelta(days=1)
    return created
