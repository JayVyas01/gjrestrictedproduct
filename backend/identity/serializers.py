"""Input validation for the login endpoints. Strict formats reject junk early."""

from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    user_id = serializers.CharField(max_length=12)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


class OtpVerifySerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    code = serializers.RegexField(r"^\d{6}$")
