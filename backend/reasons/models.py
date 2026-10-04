"""Reason codes for rejections and flags, kept in a table so admins can add new ones
without a code change. "OTHER" exists for every kind and needs a free-text comment."""

from django.db import models


class ReasonKind(models.TextChoices):
    OFFICER_REJECTION = "OFFICER_REJECTION", "Officer rejection"
    BUYER_REJECTION = "BUYER_REJECTION", "Buyer rejection"
    SUPERINTENDENT_FLAG = "SUPERINTENDENT_FLAG", "Superintendent flag"


class ReasonCode(models.Model):
    kind = models.CharField(max_length=24, choices=ReasonKind.choices)
    code = models.CharField(max_length=40)
    label = models.CharField(max_length=200)
    requires_text = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["kind", "code"], name="unique_reason_per_kind"),
            models.CheckConstraint(
                condition=models.Q(kind__in=ReasonKind.values), name="reason_kind_valid"
            ),
        ]

    def __str__(self) -> str:
        return self.label
