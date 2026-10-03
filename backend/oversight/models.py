"""Periodic superintendent oversight: review-period settings, batches of approved transactions,
flags and sign-offs. Batches, items, flags and sign-offs are append-only; the setting is
configuration (changed only through set_review_period, which audits every change)."""

from datetime import date, timedelta

from django.db import models

from positions.models import Position
from reasons.models import ReasonCode
from transactions.models import Transaction

REVIEW_PERIODS = (15, 30, 60)
SIGN_OFF_DAYS = 30


class SuperintendentSetting(models.Model):
    position = models.OneToOneField(
        Position, on_delete=models.PROTECT, related_name="review_setting"
    )
    period_days = models.PositiveSmallIntegerField()
    starts_on = models.DateField()
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(period_days__in=REVIEW_PERIODS), name="review_period_valid"
            ),
        ]


class OversightBatch(models.Model):
    position = models.ForeignKey(Position, on_delete=models.PROTECT, related_name="batches")
    period_start = models.DateField()
    period_end = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["position", "period_start"], name="one_batch_per_period"
            ),
            models.CheckConstraint(
                condition=models.Q(period_end__gte=models.F("period_start")),
                name="batch_period_ordered",
            ),
        ]

    def due_on(self) -> date:
        return self.period_end + timedelta(days=SIGN_OFF_DAYS)


class BatchItem(models.Model):
    batch = models.ForeignKey(OversightBatch, on_delete=models.PROTECT, related_name="items")
    transaction = models.ForeignKey(Transaction, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "transaction"], name="one_item_per_transaction"
            )
        ]


class BatchFlag(models.Model):
    item = models.OneToOneField(BatchItem, on_delete=models.PROTECT, related_name="flag")
    reason = models.ForeignKey(ReasonCode, on_delete=models.PROTECT)
    comment = models.TextField(blank=True)
    flagged_by = models.CharField(max_length=12)
    position = models.ForeignKey(Position, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)


class BatchSignOff(models.Model):
    batch = models.OneToOneField(OversightBatch, on_delete=models.PROTECT, related_name="sign_off")
    signed_by = models.CharField(max_length=12)
    position = models.ForeignKey(Position, on_delete=models.PROTECT, related_name="+")
    otp_verified_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
