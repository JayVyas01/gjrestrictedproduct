"""HTTP endpoints for licensing. Thin: validate, call a service, respond."""

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from licensing.enrolment import complete_enrolment, start_enrolment
from licensing.serializers import EnrolmentCompleteSerializer, EnrolmentStartSerializer

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
