"""Liveness endpoint for the load balancer, and the home-screen counts.

Every request runs in a DB transaction (DbContextMiddleware), so health also shows the
database is reachable.
"""

from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET
from rest_framework.response import Response
from rest_framework.views import APIView

from core.home import home_counts


@require_GET
def health(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


class HomeView(APIView):
    """Any logged-in user: their role and the counts their home screen shows."""

    def get(self, request):
        counts = home_counts(request.user, timezone.localdate())
        return Response({"role": request.user.role, "counts": counts})
