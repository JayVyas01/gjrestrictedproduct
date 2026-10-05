"""Demo-only endpoints. Anonymous (codes and personas are needed before sign-in), read-only,
and 404 unless DEMO_MODE, exactly as if they did not exist."""

from django.conf import settings
from django.http import Http404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from demo.dataset import PERSONAS
from demo.models import DemoInboxMessage, DemoPersona

INBOX_SIZE = 20


class DemoView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "demo"  # its own budget: inbox polling must not use up "lookup"

    def initial(self, request, *args, **kwargs):
        # Before authentication and throttling, so the 404 looks the same for every request.
        if not settings.DEMO_MODE:
            raise Http404
        super().initial(request, *args, **kwargs)


class InboxView(DemoView):
    def get(self, request):
        messages = DemoInboxMessage.objects.order_by("-created_at", "-id")[:INBOX_SIZE]
        return Response(
            [
                {
                    "display_name": message.display_name,
                    "contact_last4": message.contact_last4,
                    "code": message.code,
                    "created_at": message.created_at,
                }
                for message in messages
            ]
        )


class PersonasView(DemoView):
    def get(self, request):
        seeded = dict(DemoPersona.objects.values_list("key", "user_id"))
        return Response(
            [
                {
                    "key": persona.key,
                    "label": persona.label,
                    "description": persona.description,
                    "user_id": seeded[persona.key],
                    "password": settings.DEMO_PASSWORD,
                }
                for persona in PERSONAS
                if persona.key in seeded
            ]
        )
