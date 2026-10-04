"""Review periods and batch creation (SYSTEM context).

Periods start at the setting's starts_on and run back to back. A batch is created only once
its period has fully ended (period_end < today) and lists every APPROVED transaction whose
superintendent position it is, decided (local date) within the period. Idempotent.
"""

from datetime import date, timedelta

from django.db import connection
from django.utils import timezone

from alerts.service import raise_flag_alert
from audit.service import record
from core.db_context import acting_as_system
from identity import otp
from identity.models import OtpChallenge, OtpPurpose, User
from oversight.models import (
    REVIEW_PERIODS,
    BatchFlag,
    BatchItem,
    BatchSignOff,
    OversightBatch,
    SuperintendentSetting,
)
from positions.models import AreaLevel, Position
from positions.service import positions_held
from reasons.models import ReasonKind
from reasons.service import resolve_reason
from transactions.models import DecisionStep, Transaction, TransactionStatus
from transactions.service import final_approval


class InvalidSetting(Exception):
    def __init__(self, reasons: list[str]):
        super().__init__("; ".join(reasons))
        self.reasons = reasons


def _next_start(position: Position, fallback: date) -> date:
    last = position.batches.order_by("-period_end").first()
    return last.period_end + timedelta(days=1) if last else fallback


def _earliest_approval(position: Position) -> date | None:
    first = (
        Transaction.objects.filter(
            superintendent_position=position, status=TransactionStatus.APPROVED
        )
        .order_by("decided_at")
        .values_list("decided_at", flat=True)
        .first()
    )
    return timezone.localtime(first).date() if first else None


def _resolve_start(position: Position, starts_on: date | None) -> date:
    """The start date of the new period, so that no approved transaction is ever skipped.

    With batches: the day after the last batch (an explicit date must equal it). Without batches:
    an explicit date may not be later than the existing setting's start or, for a new setting,
    the earliest approval for this position (today if none); that date is also the default.
    """
    existing = SuperintendentSetting.objects.filter(position=position).first()
    last = position.batches.order_by("-period_end").first()
    if last:
        required = last.period_end + timedelta(days=1)
        if starts_on is not None and starts_on != required:
            raise InvalidSetting([f"The new period must start on {required.isoformat()}."])
        return required
    if existing:
        latest_allowed = existing.starts_on
    else:
        latest_allowed = _earliest_approval(position) or timezone.localdate()
    if starts_on is not None and starts_on > latest_allowed:
        raise InvalidSetting(
            [
                f"The new period cannot start after {latest_allowed.isoformat()}, "
                "or transactions in between would never be reviewed."
            ]
        )
    return starts_on or latest_allowed


def _lock_batch_job() -> None:
    """Serialise batch creation and review-period changes (job-level advisory lock)."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext('oversight-batches'))")


def set_review_period(
    *, position: Position, days: int, by: str, starts_on: date | None = None
) -> SuperintendentSetting:
    if days not in REVIEW_PERIODS:
        raise InvalidSetting(["The review period must be 15, 30 or 60 days."])
    if position.area.level != AreaLevel.DISTRICT:
        raise InvalidSetting(
            ["Review periods can only be set for a district superintendent position."]
        )
    # Lookups and write run as SYSTEM so the caller's row-level security cannot hide batches.
    with acting_as_system("set_review_period"):
        _lock_batch_job()
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


def _current_period_end(setting: SuperintendentSetting | None, today: date) -> date | None:
    """The last day of the period containing today (None before the first period starts)."""
    if setting is None or setting.starts_on > today:
        return None
    periods_done = (today - setting.starts_on).days // setting.period_days
    return setting.starts_on + timedelta(days=(periods_done + 1) * setting.period_days - 1)


def review_settings_overview(today: date) -> list[dict]:
    """Every district superintendent position with its review period and batch dates."""
    # Runs as SYSTEM: the Licensing Authority manages review periods but cannot read batches
    # under row-level security. Only dates leave this block, never batch contents.
    with acting_as_system("review_settings_overview"):
        rows = []
        positions = Position.objects.filter(area__level=AreaLevel.DISTRICT).select_related(
            "area", "review_setting"
        )
        for position in positions.order_by("id"):
            setting = getattr(position, "review_setting", None)
            last = position.batches.order_by("-period_end").first()
            rows.append(
                {
                    "position_id": position.id,
                    "title": position.title,
                    "area": position.area.name,
                    "period_days": setting.period_days if setting else None,
                    "starts_on": setting.starts_on if setting else None,
                    "current_period_end": _current_period_end(setting, today),
                    "last_batch_end": last.period_end if last else None,
                }
            )
    return rows


def _make_batch(position: Position, start: date, end: date) -> tuple[OversightBatch, int]:
    batch = OversightBatch.objects.create(position=position, period_start=start, period_end=end)
    approved = Transaction.objects.filter(
        superintendent_position=position,
        status=TransactionStatus.APPROVED,
        decided_at__date__gte=start,
        decided_at__date__lte=end,
    ).order_by("id")
    items = BatchItem.objects.bulk_create(
        [BatchItem(batch=batch, transaction=tx) for tx in approved]
    )
    return batch, len(items)


def create_due_batches(today: date) -> list[OversightBatch]:
    # lock order: job lock → batch/item inserts → audit
    _lock_batch_job()
    created = []
    for setting in SuperintendentSetting.objects.select_related("position").order_by("id"):
        start = max(_next_start(setting.position, setting.starts_on), setting.starts_on)
        while (end := start + timedelta(days=setting.period_days - 1)) < today:
            created.append(_make_batch(setting.position, start, end))
            start = end + timedelta(days=1)
    for batch, item_count in created:
        record(
            action="oversight.batch_created",
            actor="create_due_batches",
            subject_type="batch",
            subject_id=str(batch.id),
            payload={"items": item_count},
        )
    return [batch for batch, _ in created]


class NotAllowed(Exception):
    pass


ALREADY_SIGNED = "This batch is already signed off."
OWN_APPROVAL = "You approved this transaction; the Head Authority reviews it."


def batch_status(batch: OversightBatch, today: date) -> str:
    if BatchSignOff.objects.filter(batch=batch).exists():
        return "SIGNED"
    return "OVERDUE" if today > batch.due_on() else "OPEN"


def _own_open_batch(batch_id: int, user: User) -> OversightBatch:
    batch = OversightBatch.objects.select_related("position").filter(pk=batch_id).first()
    if batch is None or batch.position not in positions_held(user):
        raise NotAllowed("Only the superintendent holding this position can review this batch.")
    if BatchSignOff.objects.filter(batch=batch).exists():
        raise NotAllowed(ALREADY_SIGNED)
    return batch


def _lock_batch(batch: OversightBatch) -> None:
    """Batches are append-only (no row lock possible), so serialise flag/sign-off per batch."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))", [f"oversight-batch:{batch.id}"]
        )


def flag_item(
    *, batch_id: int, reference: str, user: User, reason_code: str, comment: str
) -> BatchFlag:
    batch = _own_open_batch(batch_id, user)
    item = (
        batch.items.select_related("transaction").filter(transaction__reference=reference).first()
    )
    if item is None:
        raise NotAllowed("That transaction is not in this batch.")
    approval = final_approval(item.transaction)
    if approval.step == DecisionStep.SUPERINTENDENT:
        raise NotAllowed(OWN_APPROVAL)
    reason = resolve_reason(ReasonKind.SUPERINTENDENT_FLAG, reason_code, comment)
    with acting_as_system("flag_transaction"):
        _lock_batch(batch)
        if BatchSignOff.objects.filter(batch=batch).exists():
            raise NotAllowed(ALREADY_SIGNED)
        if BatchFlag.objects.filter(item=item).exists():
            raise NotAllowed("This transaction is already flagged in this batch.")
        flag = BatchFlag.objects.create(
            item=item,
            reason=reason,
            comment=comment.strip(),
            flagged_by=user.user_id,
            position=batch.position,
        )
        raise_flag_alert(
            tx=item.transaction, position=approval.position, reason=reason, comment=comment.strip()
        )
        record(
            action="oversight.transaction_flagged",
            actor=user.user_id,
            subject_type="transaction",
            subject_id=item.transaction.reference,
            payload={"batch_id": batch.id},
        )
    return flag


def request_sign_off_code(*, batch_id: int, user: User) -> OtpChallenge:
    _own_open_batch(batch_id, user)
    return otp.issue(user, OtpPurpose.DECISION)


def sign_off(*, batch_id: int, user: User, challenge_id: str, code: str) -> BatchSignOff | None:
    batch = _own_open_batch(batch_id, user)
    signer = otp.verify(challenge_id=challenge_id, purpose=OtpPurpose.DECISION, code=code)
    if signer is None:
        return None  # wrong or expired code: the attempt counts, nothing else changes
    if signer.pk != user.pk:
        raise NotAllowed("This code belongs to someone else.")
    with acting_as_system("sign_off_batch"):
        _lock_batch(batch)
        if BatchSignOff.objects.filter(batch=batch).exists():
            raise NotAllowed(ALREADY_SIGNED)
        signed = BatchSignOff.objects.create(
            batch=batch,
            signed_by=user.user_id,
            position=batch.position,
            otp_verified_at=timezone.now(),
        )
        record(
            action="oversight.batch_signed",
            actor=user.user_id,
            subject_type="batch",
            subject_id=str(batch.id),
        )
    return signed
