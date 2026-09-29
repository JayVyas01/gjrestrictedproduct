"""Licence records, as issued by the authority's existing licensing process.

This platform records licences; it does not issue them. Validity periods and permission
snapshots are append-only: a renewal adds a period and a fresh snapshot.
"""

from django.db import models

from catalogue.models import LicenceType, LicenceTypeRuleVersion, Substance, SubstanceClass
from core import crypto
from positions.models import Area


class LicenceStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    SUSPENDED = "SUSPENDED", "Suspended"
    REVOKED = "REVOKED", "Revoked"


class Licence(models.Model):
    number_encrypted = models.TextField()
    number_index = models.CharField(max_length=64, unique=True)
    gstin_encrypted = models.TextField()
    gstin_index = models.CharField(max_length=64, db_index=True)
    holder_name = models.CharField(max_length=200)
    contact_encrypted = models.TextField()
    licence_type = models.ForeignKey(LicenceType, on_delete=models.PROTECT)
    substance = models.ForeignKey(Substance, on_delete=models.PROTECT, null=True, blank=True)
    substance_class = models.ForeignKey(
        SubstanceClass, on_delete=models.PROTECT, null=True, blank=True
    )
    area = models.ForeignKey(Area, on_delete=models.PROTECT)
    status = models.CharField(
        max_length=16, choices=LicenceStatus.choices, default=LicenceStatus.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(substance__isnull=False, substance_class__isnull=True)
                    | models.Q(substance__isnull=True, substance_class__isnull=False)
                ),
                name="licence_exactly_one_scope",
            ),
        ]

    def number(self) -> str:
        return crypto.decrypt(self.number_encrypted)

    def gstin(self) -> str:
        return crypto.decrypt(self.gstin_encrypted)

    def contact(self) -> str:
        return crypto.decrypt(self.contact_encrypted)

    def scope_name(self) -> str:
        return (self.substance or self.substance_class).name


class LicenceValidityPeriod(models.Model):
    licence = models.ForeignKey(Licence, on_delete=models.PROTECT, related_name="validity_periods")
    starts_on = models.DateField()
    ends_on = models.DateField()
    recorded_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_on__gte=models.F("starts_on")),
                name="period_ends_after_start",
            ),
        ]


class LicencePermissionsSnapshot(models.Model):
    """Frozen copy of the rule version in force when the licence (or a renewal) was recorded."""

    licence = models.ForeignKey(
        Licence, on_delete=models.PROTECT, related_name="permission_snapshots"
    )
    rule_version = models.ForeignKey(LicenceTypeRuleVersion, on_delete=models.PROTECT)
    may_buy = models.BooleanField()
    may_sell = models.BooleanField()
    may_transport = models.BooleanField()
    max_stock_qty = models.DecimalField(max_digits=12, decimal_places=3)
    max_per_transaction_qty = models.DecimalField(max_digits=12, decimal_places=3)
    taken_at = models.DateTimeField(auto_now_add=True)
