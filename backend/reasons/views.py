"""Reason-code list for dropdowns."""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from reasons.models import ReasonKind
from reasons.service import active_reasons


class ReasonCodeListView(APIView):
    def get(self, request):
        kind = request.query_params.get("kind", "")
        if kind not in ReasonKind.values:
            return Response({"detail": "Unknown reason kind."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            [
                {"code": r.code, "label": r.label, "requires_text": r.requires_text}
                for r in active_reasons(kind)
            ]
        )
