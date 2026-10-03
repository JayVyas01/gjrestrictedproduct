"""Alert list and acknowledgement. Row-level security limits the list to held positions."""

from django.db.models import Exists, OuterRef
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from alerts.models import AlertAcknowledgement, AuthorityAlert
from alerts.presenters import alert_view
from alerts.serializers import AcknowledgeSerializer
from alerts.service import AlreadyAcknowledged, NotAllowed, acknowledge

# Fixed messages: the view never echoes an exception's text (keeps CodeQL clean).
ALREADY_ACKNOWLEDGED = {"detail": "This alert is already acknowledged."}
NOT_HOLDER = {"detail": "Only the officer holding this position can acknowledge this alert."}


class AlertListView(APIView):
    def get(self, request):
        acked = AlertAcknowledgement.objects.filter(alert=OuterRef("pk"))
        rows = (
            AuthorityAlert.objects.select_related("transaction__substance", "reason")
            .annotate(is_acked=Exists(acked))
            .order_by("is_acked", "-created_at")[:100]
        )
        # Row-level security limits the count to the caller's positions; the list is capped.
        unacknowledged = AuthorityAlert.objects.filter(acknowledgement__isnull=True).count()
        return Response({"unacknowledged": unacknowledged, "alerts": [alert_view(a) for a in rows]})


class AcknowledgeView(APIView):
    def post(self, request, alert_id):
        data = AcknowledgeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            acknowledge(alert_id=alert_id, user=request.user, note=data.validated_data["note"])
        except AlreadyAcknowledged:
            return Response(ALREADY_ACKNOWLEDGED, status=status.HTTP_409_CONFLICT)
        except NotAllowed:
            return Response(NOT_HOLDER, status=status.HTTP_403_FORBIDDEN)
        alert = AuthorityAlert.objects.select_related("transaction__substance", "reason").get(
            pk=alert_id
        )
        return Response(alert_view(alert))
