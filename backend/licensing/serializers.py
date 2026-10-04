"""Input validation for licensing endpoints."""

from datetime import date

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from licensing.models import Licence
from licensing.service import current_period, current_permissions, trading_permitted


class EnrolmentStartSerializer(serializers.Serializer):
    licence_number = serializers.CharField(max_length=40)
    gstin = serializers.CharField(max_length=15)


class EnrolmentCompleteSerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    code = serializers.RegexField(r"^\d{6}$")
    password = serializers.CharField(max_length=128, trim_whitespace=False)

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value


def licence_card(licence: Licence, today: date) -> dict:
    """Everything the permissions card shows: the holder's own licences, and the permission
    fields of the authorities' licence register (`licensing.register`)."""
    permissions = current_permissions(licence)
    period = current_period(licence, today)
    return {
        "licence_number": licence.number(),
        "holder_name": licence.holder_name,
        "licence_type": licence.licence_type.name,
        "scope": licence.scope_name(),
        "unit": licence.substance.unit if licence.substance else None,
        "status": licence.status,
        "valid_from": period.starts_on.isoformat() if period else None,
        "valid_to": period.ends_on.isoformat() if period else None,
        "trading_permitted": trading_permitted(licence, today),
        "may_buy": permissions.may_buy,
        "may_sell": permissions.may_sell,
        "may_transport": permissions.may_transport,
        "max_stock_qty": str(permissions.max_stock_qty),
        "max_per_transaction_qty": str(permissions.max_per_transaction_qty),
    }
