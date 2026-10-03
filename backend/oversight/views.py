"""Superintendent review endpoints. Thin: validate, call a service, present. A wrong code is
RETURNED as 401 (the attempt commits); refusals are returned as 403/400."""

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from oversight.models import OversightBatch
from oversight.presenters import batch_detail, batch_summary
from oversight.serializers import FlagSerializer, SignOffSerializer
from oversight.service import NotAllowed, flag_item, request_sign_off_code, sign_off
from reasons.service import InvalidReason

WRONG_CODE = {"detail": "The code is wrong or has expired. Request a new code."}


def _visible(batch_id: int) -> OversightBatch | None:
    return OversightBatch.objects.select_related("position").filter(pk=batch_id).first()


def _detail(batch_id: int, user) -> Response:
    return Response(batch_detail(_visible(batch_id), timezone.localdate(), user))


class BatchListView(APIView):
    def get(self, request):
        today = timezone.localdate()
        rows = OversightBatch.objects.select_related("position").order_by("-period_start", "-id")
        return Response([batch_summary(b, today) for b in rows])


class BatchDetailView(APIView):
    def get(self, request, batch_id):
        if _visible(batch_id) is None:
            return Response({"detail": "Batch not found."}, status=status.HTTP_404_NOT_FOUND)
        return _detail(batch_id, request.user)


class FlagView(APIView):
    def post(self, request, batch_id):
        data = FlagSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            flag_item(batch_id=batch_id, user=request.user, **data.validated_data)
        except NotAllowed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except InvalidReason as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return _detail(batch_id, request.user)


class SignOffCodeView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request, batch_id):
        try:
            challenge = request_sign_off_code(batch_id=batch_id, user=request.user)
        except NotAllowed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response({"challenge_id": str(challenge.public_id)})


class SignOffView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request, batch_id):
        data = SignOffSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            signed = sign_off(
                batch_id=batch_id,
                user=request.user,
                challenge_id=str(data.validated_data["challenge_id"]),
                code=data.validated_data["code"],
            )
        except NotAllowed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        if signed is None:
            return Response(WRONG_CODE, status=status.HTTP_401_UNAUTHORIZED)
        return _detail(batch_id, request.user)
