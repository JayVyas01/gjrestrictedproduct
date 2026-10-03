"""Alert list and acknowledgement. Row-level security limits the list to held positions."""

from django.db.models import Exists, OuterRef
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from alerts.models import AlertAcknowledgement, AuthorityAlert
from alerts.presenters import alert_view
from alerts.service import NotAllowed, acknowledge


class AlertListView(APIView):
    def get(self, request):
        acked = AlertAcknowledgement.objects.filter(alert=OuterRef("pk"))
        rows = (
            AuthorityAlert.objects.select_related("transaction__substance", "reason")
            .annotate(is_acked=Exists(acked))
            .order_by("is_acked", "-created_at")[:100]
        )
        views = [alert_view(a) for a in rows]
        return Response(
            {"unacknowledged": sum(not v["acknowledged"] for v in views), "alerts": views}
        )


class AcknowledgeView(APIView):
    def post(self, request, alert_id):
        try:
            acknowledge(
                alert_id=alert_id, user=request.user, note=str(request.data.get("note", ""))[:500]
            )
        except NotAllowed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        alert = AuthorityAlert.objects.select_related("transaction__substance", "reason").get(
            pk=alert_id
        )
        return Response(alert_view(alert))
