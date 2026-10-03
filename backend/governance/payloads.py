"""What each kind of rule change carries, checked when it is drafted and again when it is applied.

validate_payload returns the cleaned payload (quantities as strings, so they survive JSON
exactly) or raises ProposalInvalid with a list of plain-language reasons.
"""

from decimal import Decimal

from rest_framework import serializers

from catalogue.models import LicenceType, Substance, SubstanceClass
from governance.models import ProposalKind

ONE_SCOPE = "Choose either a substance or a substance class."
PER_TRANSACTION_ABOVE_STOCK = "The per-transaction limit can't be above the stock limit."


class ProposalInvalid(Exception):
    def __init__(self, reasons: list[str]):
        super().__init__("; ".join(reasons))
        self.reasons = reasons


def _quantity():
    return serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))


def _code():
    return serializers.CharField(max_length=32, required=False, allow_blank=True, default="")


def _check_scope(attrs: dict) -> dict:
    """Exactly one of substance_code / class_code, and it must exist. Drops the unused key."""
    substance_code = attrs.pop("substance_code")
    class_code = attrs.pop("class_code")
    if bool(substance_code) == bool(class_code):
        raise serializers.ValidationError(ONE_SCOPE)
    if substance_code:
        if not Substance.objects.filter(code=substance_code).exists():
            raise serializers.ValidationError(f"No substance has code {substance_code}.")
        return {**attrs, "substance_code": substance_code}
    if not SubstanceClass.objects.filter(code=class_code).exists():
        raise serializers.ValidationError(f"No substance class has code {class_code}.")
    return {**attrs, "class_code": class_code}


class NewLicenceTypePayload(serializers.Serializer):
    code = serializers.RegexField(r"^[A-Z][A-Z0-9_]{1,31}$")
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(
        max_length=500, required=False, allow_blank=True, default=""
    )

    def validate(self, attrs: dict) -> dict:
        code = attrs["code"]
        if LicenceType.objects.filter(code=code).exists():
            raise serializers.ValidationError(f"A licence type with code {code} already exists.")
        return attrs


class RuleVersionPayload(serializers.Serializer):
    licence_type_code = serializers.CharField(max_length=32)
    substance_code = _code()
    class_code = _code()
    may_buy = serializers.BooleanField()
    may_sell = serializers.BooleanField()
    may_transport = serializers.BooleanField()
    max_stock_qty = _quantity()
    max_per_transaction_qty = _quantity()
    validity_months = serializers.IntegerField(min_value=1, max_value=120)

    def validate(self, attrs: dict) -> dict:
        code = attrs["licence_type_code"]
        if not LicenceType.objects.filter(code=code).exists():
            raise serializers.ValidationError(f"No licence type has code {code}.")
        if attrs["max_per_transaction_qty"] > attrs["max_stock_qty"]:
            raise serializers.ValidationError(PER_TRANSACTION_ABOVE_STOCK)
        return _check_scope(attrs)


class ApprovalThresholdPayload(serializers.Serializer):
    substance_code = _code()
    class_code = _code()
    superintendent_above_qty = _quantity()

    def validate(self, attrs: dict) -> dict:
        return _check_scope(attrs)


PAYLOADS = {
    ProposalKind.NEW_LICENCE_TYPE: NewLicenceTypePayload,
    ProposalKind.RULE_VERSION: RuleVersionPayload,
    ProposalKind.APPROVAL_THRESHOLD: ApprovalThresholdPayload,
}


def _reasons(errors) -> list[str]:
    """Flatten serializer errors: whole-payload errors as they are, field errors with the field."""
    if isinstance(errors, list):
        return [str(message) for message in errors]
    reasons = []
    for field, messages in errors.items():
        prefix = "" if field == "non_field_errors" else f"{field}: "
        reasons += [f"{prefix}{message}" for message in _reasons(messages)]
    return reasons


def validate_payload(kind: str, payload) -> dict:
    serializer_class = PAYLOADS.get(kind)
    if serializer_class is None:
        raise ProposalInvalid(["Unknown kind of rule change."])
    serializer = serializer_class(data=payload)
    if not serializer.is_valid():
        raise ProposalInvalid(_reasons(serializer.errors))
    # Quantities become strings so the payload survives JSON exactly.
    return {
        key: str(value) if isinstance(value, Decimal) else value
        for key, value in serializer.validated_data.items()
    }
