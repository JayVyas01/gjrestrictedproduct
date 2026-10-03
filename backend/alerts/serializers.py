"""Input validation for the alert endpoints."""

from rest_framework import serializers


class AcknowledgeSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
