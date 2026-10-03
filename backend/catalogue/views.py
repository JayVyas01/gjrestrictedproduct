"""Read-only catalogue endpoints for any logged-in user."""

from rest_framework.response import Response
from rest_framework.views import APIView

from catalogue.models import ApprovalThreshold
from catalogue.service import latest_threshold


def _threshold_row(threshold: ApprovalThreshold) -> dict:
    latest = latest_threshold(threshold)
    if threshold.substance is not None:
        scope, kind, unit = threshold.substance.name, "substance", threshold.substance.unit
    else:
        # A class shares one unit (CODEMAP convention), so any of its substances gives it.
        first = threshold.substance_class.substances.order_by("id").first()
        scope, kind, unit = threshold.substance_class.name, "class", first and first.unit
    return {
        "scope": scope,
        "scope_kind": kind,
        "superintendent_above_qty": str(latest.superintendent_above_qty),
        "unit": unit,
        "version": latest.version,
    }


class ApprovalThresholdListView(APIView):
    """The latest version of every approval threshold."""

    def get(self, request):
        thresholds = (
            ApprovalThreshold.objects.select_related("substance", "substance_class")
            .filter(versions__isnull=False)
            .distinct()
            .order_by("id")
        )
        return Response([_threshold_row(threshold) for threshold in thresholds])
