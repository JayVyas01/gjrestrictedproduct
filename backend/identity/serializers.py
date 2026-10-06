"""Input validation for the login endpoints. Strict formats reject junk early."""

from rest_framework import serializers

from identity.roles import LoginRole


class LoginSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=LoginRole.choices)
    identifier = serializers.CharField(max_length=254)  # a GSTIN for PARTY, else an email
    password = serializers.CharField(max_length=128, trim_whitespace=False)


class OtpVerifySerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    code = serializers.RegexField(r"^\d{6}$")


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(max_length=128, trim_whitespace=False)
    new_password = serializers.CharField(max_length=128, trim_whitespace=False)
