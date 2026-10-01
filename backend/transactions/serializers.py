"""Input validation for the transaction API. Messages say what to fix."""

from decimal import Decimal

from rest_framework import serializers

from catalogue.models import Substance


class BuyerLookupSerializer(serializers.Serializer):
    gstin = serializers.CharField(max_length=20)


class NewTransactionSerializer(serializers.Serializer):
    buyer_gstin = serializers.CharField(max_length=20)
    substance_code = serializers.SlugRelatedField(
        slug_field="code", queryset=Substance.objects.all(), source="substance"
    )
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))
    transporter_name = serializers.CharField(max_length=120)
    transporter_id_number = serializers.CharField(max_length=40)
    vehicle_number = serializers.RegexField(
        r"^[A-Za-z]{2}\s?\d{1,2}\s?[A-Za-z]{0,3}\s?\d{4}$",
        max_length=16,
        error_messages={"invalid": "Enter the vehicle number like GJ01AB1234."},
    )
    route = serializers.CharField(max_length=300)


class DecideSerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    code = serializers.RegexField(r"^\d{6}$")
    outcome = serializers.ChoiceField(choices=["CONFIRM", "APPROVE", "REJECT"])
    reason_code = serializers.CharField(max_length=40, required=False, default="")
    comment = serializers.CharField(max_length=500, required=False, default="", allow_blank=True)
