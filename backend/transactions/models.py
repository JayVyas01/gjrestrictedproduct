"""A seller-initiated transaction and the append-only decisions taken on it.

Only SYSTEM writes (services, after checking who may act). Only status and decided_at ever
change on a transaction. Transporter identifiers are encrypted. The designated officer and
superintendent POSITIONS are fixed at creation; whoever holds them acts.
"""

import secrets

from django.db import models

from catalogue.models import Substance
from core import crypto
from identity.models import USER_ID_ALPHABET
from licensing.models import Licence
from positions.models import Position
from reasons.models import ReasonCode


def generate_reference() -> str:
    return "TX" + "".join(secrets.choice(USER_ID_ALPHABET) for _ in range(10))


class TransactionStatus(models.TextChoices):
    AWAITING_BUYER = "AWAITING_BUYER", "Waiting for the buyer"
    AWAITING_OFFICER = "AWAITING_OFFICER", "Waiting for the officer"
    APPROVED = "APPROVED", "Approved"
    REJECTED_BY_BUYER = "REJECTED_BY_BUYER", "Rejected by the buyer"
    REJECTED_BY_OFFICER = "REJECTED_BY_OFFICER", "Rejected by the officer"
    CANCELLED = "CANCELLED", "Cancelled by the seller"


class DecisionStep(models.TextChoices):
    BUYER = "BUYER", "Buyer"
    OFFICER = "OFFICER", "Officer"
    SELLER = "SELLER", "Seller"


class DecisionOutcome(models.TextChoices):
    CONFIRM = "CONFIRM", "Confirmed"
    APPROVE = "APPROVE", "Approved"
    REJECT = "REJECT", "Rejected"
    CANCEL = "CANCEL", "Cancelled"


class Transaction(models.Model):
    reference = models.CharField(
        max_length=12, unique=True, default=generate_reference, editable=False
    )
    seller_licence = models.ForeignKey(Licence, on_delete=models.PROTECT, related_name="sales")
    buyer_licence = models.ForeignKey(Licence, on_delete=models.PROTECT, related_name="purchases")
    seller_gstin_index = models.CharField(max_length=64)
    buyer_gstin_index = models.CharField(max_length=64)
    substance = models.ForeignKey(Substance, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit = models.CharField(max_length=4)
    transporter_name_encrypted = models.TextField()
    transporter_id_encrypted = models.TextField()
    vehicle_number_encrypted = models.TextField()
    route = models.CharField(max_length=300)
    designated_position = models.ForeignKey(Position, on_delete=models.PROTECT, related_name="+")
    superintendent_position = models.ForeignKey(
        Position, on_delete=models.PROTECT, related_name="+"
    )
    status = models.CharField(
        max_length=24, choices=TransactionStatus.choices, default=TransactionStatus.AWAITING_BUYER
    )
    created_by = models.CharField(max_length=12)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="transaction_quantity_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=TransactionStatus.values),
                name="transaction_status_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(seller_gstin_index=models.F("buyer_gstin_index")),
                name="transaction_not_self",
            ),
        ]

    def transporter_name(self) -> str:
        return crypto.decrypt(self.transporter_name_encrypted)

    def transporter_id(self) -> str:
        return crypto.decrypt(self.transporter_id_encrypted)

    def vehicle_number(self) -> str:
        return crypto.decrypt(self.vehicle_number_encrypted)


class TransactionDecision(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.PROTECT, related_name="decisions")
    step = models.CharField(max_length=8, choices=DecisionStep.choices)
    outcome = models.CharField(max_length=8, choices=DecisionOutcome.choices)
    actor_user_id = models.CharField(max_length=12)
    position = models.ForeignKey(
        Position, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    reason = models.ForeignKey(ReasonCode, on_delete=models.PROTECT, null=True, blank=True)
    comment = models.TextField(blank=True)
    otp_verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
