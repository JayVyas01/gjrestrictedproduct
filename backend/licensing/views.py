"""HTTP endpoints for licensing. Thin: validate, call a service, respond."""

from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from catalogue.models import Substance
from identity.permissions import role_required
from identity.roles import Role
from licensing.enrolment import complete_enrolment, start_enrolment
from licensing.models import Licence
from licensing.serializers import (
    EnrolmentCompleteSerializer,
    EnrolmentStartSerializer,
    licence_card,
)

ENROLMENT_FAILED = (
    "We could not verify these details. "
    "Check the licence number and GSTIN exactly as printed on your licence."
)


def _failed() -> Response:
    return Response({"detail": ENROLMENT_FAILED}, status=status.HTTP_401_UNAUTHORIZED)


@method_decorator(csrf_protect, name="dispatch")
class EnrolmentStartView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "enrolment"

    def post(self, request):
        data = EnrolmentStartSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        challenge = start_enrolment(**data.validated_data)
        if challenge is None:
            return _failed()
        return Response({"challenge_id": str(challenge.public_id)})


@method_decorator(csrf_protect, name="dispatch")
class EnrolmentCompleteView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request):
        data = EnrolmentCompleteSerializer(data=request.data)
        data.is_valid(raise_exception=True)  # weak password -> 400 before the code is used
        user = complete_enrolment(
            challenge_id=str(data.validated_data["challenge_id"]),
            code=data.validated_data["code"],
            password=data.validated_data["password"],
        )
        if user is None:
            return _failed()
        return Response({"user_id": user.user_id}, status=status.HTTP_201_CREATED)


class MyLicencesView(APIView):
    permission_classes = [role_required(Role.LICENSEE)]

    def get(self, request):
        # Filtered here AND by row-level security (two independent checks).
        licences = (
            Licence.objects.select_related("licence_type", "substance", "substance_class")
            .filter(gstin_index=request.user.licensee_gstin_index)
            .order_by("id")
        )
        today = timezone.localdate()
        return Response([licence_card(licence, today) for licence in licences])


class SubstanceListView(APIView):
    def get(self, request):
        substances = Substance.objects.select_related("substance_class").order_by("name")
        return Response(
            [
                {
                    "code": s.code,
                    "name": s.name,
                    "substance_class": s.substance_class.name,
                    "unit": s.unit,
                }
                for s in substances
            ]
        )
