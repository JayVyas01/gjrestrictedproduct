"""Input validation for the demo sign-up endpoints. Every field is checked here, so a bad value
is a 400 on that field before any matching (which then fails only with the one 401)."""

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from demo.signup import normalise_gstin
from licensing.service import GSTIN_PATTERN


class SignupStartSerializer(serializers.Serializer):
    gstin = serializers.CharField(max_length=20)
    # At least 10 digits; spaces, dashes and a leading "+" allowed (compared on digits only).
    phone = serializers.RegexField(r"^\+?[\d\s-]{10,20}$", max_length=20)
    email = serializers.EmailField(max_length=254)
    business_name = serializers.CharField(min_length=1, max_length=200)
    address = serializers.CharField(min_length=1, max_length=500)
    password = serializers.CharField(max_length=128, trim_whitespace=False)

    def validate_gstin(self, value: str) -> str:
        gstin = normalise_gstin(value)
        if not GSTIN_PATTERN.match(gstin):
            raise serializers.ValidationError("Enter a valid 15-character GSTIN.")
        return gstin

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value


class SignupCompleteSerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    code = serializers.RegexField(r"^\d{6}$")
