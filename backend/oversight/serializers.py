"""Input validation for oversight endpoints."""

from rest_framework import serializers


class FlagSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=12)
    reason_code = serializers.CharField(max_length=40)
    comment = serializers.CharField(max_length=500, required=False, default="", allow_blank=True)


class SignOffSerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    code = serializers.RegexField(r"^\d{6}$")


class ReviewPeriodSerializer(serializers.Serializer):
    period_days = serializers.IntegerField()
    starts_on = serializers.DateField(required=False, allow_null=True, default=None)
