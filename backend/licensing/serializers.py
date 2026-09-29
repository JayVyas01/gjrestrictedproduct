"""Input validation for licensing endpoints."""

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers


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
