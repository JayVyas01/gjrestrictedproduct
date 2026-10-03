"""In-app alerts for authorities, addressed to POSITIONS (whoever holds the position sees it).

Raised when a buyer rejects a transaction (to the designated officer and the superintendent)
and when a superintendent flags an approved transaction (to the approving officer's position).
Alerts and acknowledgements are append-only.
"""

from django.db import models

from positions.models import Position
from reasons.models import ReasonCode
from transactions.models import Transaction


class AlertKind(models.TextChoices):
    BUYER_REJECTION = "BUYER_REJECTION", "Buyer rejected a transaction"
    SUPERINTENDENT_FLAG = "SUPERINTENDENT_FLAG", "Superintendent flagged a transaction"


class AuthorityAlert(models.Model):
    kind = models.CharField(max_length=24, choices=AlertKind.choices)
    position = models.ForeignKey(Position, on_delete=models.PROTECT, related_name="+")
    transaction = models.ForeignKey(Transaction, on_delete=models.PROTECT, related_name="alerts")
    reason = models.ForeignKey(ReasonCode, on_delete=models.PROTECT)
    comment = models.TextField(blank=True)
    pattern_count = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(kind__in=AlertKind.values), name="alert_kind_valid"
            ),
        ]


class AlertAcknowledgement(models.Model):
    alert = models.OneToOneField(
        AuthorityAlert, on_delete=models.PROTECT, related_name="acknowledgement"
    )
    user_id = models.CharField(max_length=12)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
