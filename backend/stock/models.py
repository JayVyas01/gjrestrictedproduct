"""How much of each substance a licensed business holds (demo: seeded, moved on approval).

Balances are per business (GSTIN blind index) per substance and never negative. Every change
writes an append-only StockMovement, so the balance history can always be reconstructed.
"""

from django.db import models

from catalogue.models import Substance


class StockBalance(models.Model):
    gstin_index = models.CharField(max_length=64)
    substance = models.ForeignKey(Substance, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["gstin_index", "substance"], name="one_balance_per_business_and_substance"
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0), name="stock_never_negative"
            ),
        ]


class MovementReason(models.TextChoices):
    OPENING = "OPENING", "Opening balance"
    TRANSACTION = "TRANSACTION", "Approved transaction"


class StockMovement(models.Model):
    gstin_index = models.CharField(max_length=64)
    substance = models.ForeignKey(Substance, on_delete=models.PROTECT)
    delta = models.DecimalField(max_digits=14, decimal_places=3)
    balance_after = models.DecimalField(max_digits=14, decimal_places=3)
    reason = models.CharField(max_length=16, choices=MovementReason.choices)
    transaction_reference = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
