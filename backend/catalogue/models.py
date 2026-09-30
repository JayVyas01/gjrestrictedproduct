"""What can be traded, under which licence types, with which permissions.

Maintained by the Licensing Authority. Rule versions are never edited: a change is a new
version, and licences keep a frozen copy of the version they were recorded under.
"""

from django.db import models


class Unit(models.TextChoices):
    LITRE = "L", "Litres"
    KILOGRAM = "KG", "Kilograms"


class SubstanceClass(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=100)

    def __str__(self) -> str:
        return self.name


class Substance(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=100)
    substance_class = models.ForeignKey(
        SubstanceClass, on_delete=models.PROTECT, related_name="substances"
    )
    unit = models.CharField(max_length=4, choices=Unit.choices)

    def __str__(self) -> str:
        return self.name


class LicenceType(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self) -> str:
        return self.name


class LicenceTypeRule(models.Model):
    """Which licence type may deal in which substance or class. Scope is exactly one of the two."""

    licence_type = models.ForeignKey(LicenceType, on_delete=models.PROTECT, related_name="rules")
    substance = models.ForeignKey(Substance, on_delete=models.PROTECT, null=True, blank=True)
    substance_class = models.ForeignKey(
        SubstanceClass, on_delete=models.PROTECT, null=True, blank=True
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(substance__isnull=False, substance_class__isnull=True)
                    | models.Q(substance__isnull=True, substance_class__isnull=False)
                ),
                name="rule_exactly_one_scope",
            ),
            models.UniqueConstraint(
                fields=["licence_type", "substance"],
                condition=models.Q(substance__isnull=False),
                name="one_rule_per_type_and_substance",
            ),
            models.UniqueConstraint(
                fields=["licence_type", "substance_class"],
                condition=models.Q(substance_class__isnull=False),
                name="one_rule_per_type_and_class",
            ),
        ]


class LicenceTypeRuleVersion(models.Model):
    rule = models.ForeignKey(LicenceTypeRule, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()
    may_buy = models.BooleanField()
    may_sell = models.BooleanField()
    may_transport = models.BooleanField()
    max_stock_qty = models.DecimalField(max_digits=12, decimal_places=3)
    max_per_transaction_qty = models.DecimalField(max_digits=12, decimal_places=3)
    validity_months = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["rule", "version"], name="unique_rule_version"),
            models.CheckConstraint(
                condition=models.Q(max_stock_qty__gt=0, max_per_transaction_qty__gt=0),
                name="rule_limits_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(validity_months__gt=0), name="rule_validity_positive"
            ),
        ]
