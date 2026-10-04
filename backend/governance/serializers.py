"""Input validation for the rule-change API. Payload and justification rules live in
governance.payloads and governance.service (refused there with a list of reasons, 422)."""

from rest_framework import serializers

from governance.models import ProposalKind, ProposalStatus
from governance.service import APPROVE, NOTE_REQUIRED, REJECT


class DraftSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=ProposalKind.choices)
    payload = serializers.JSONField()
    justification = serializers.CharField(required=False, default="", allow_blank=True)


class DecideSerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    code = serializers.RegexField(r"^\d{6}$")
    outcome = serializers.ChoiceField(choices=[APPROVE, REJECT])
    note = serializers.CharField(max_length=500, required=False, default="", allow_blank=True)

    def validate(self, attrs: dict) -> dict:
        # Checked here, before the code is spent, so the officer can add a note and retry.
        if attrs["outcome"] == REJECT and len(attrs["note"]) < 10:
            raise serializers.ValidationError({"note": [NOTE_REQUIRED]})
        return attrs


class ProposalFilterSerializer(serializers.Serializer):
    """List filter. Blank means no filter; any other unknown value is refused."""

    status = serializers.ChoiceField(
        choices=ProposalStatus.choices, required=False, default="", allow_blank=True
    )
