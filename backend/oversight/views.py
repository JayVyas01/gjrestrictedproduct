"""Superintendent review endpoints. Thin: validate, call a service, present. A wrong code is
RETURNED as 401 (the attempt commits); refusals are returned as 403/400."""

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from identity.permissions import role_required
from identity.roles import Role
from oversight.models import OversightBatch
from oversight.presenters import batch_detail, batch_summary
from oversight.serializers import FlagSerializer, ReviewPeriodSerializer, SignOffSerializer
from oversight.service import (
    InvalidSetting,
    NotAllowed,
    flag_item,
    request_sign_off_code,
    review_settings_overview,
    set_review_period,
    sign_off,
)
from positions.models import Position
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


class ReviewSettingsView(APIView):
    permission_classes = [
        role_required(Role.LICENSING_AUTHORITY, Role.HEAD_AUTHORITY, Role.SOFTWARE_OWNER)
    ]

    def get(self, request):
        return Response(review_settings_overview(timezone.localdate()))


class ReviewSettingChangeView(APIView):
    permission_classes = [role_required(Role.LICENSING_AUTHORITY)]

    def put(self, request, position_id):
        data = ReviewPeriodSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        position = Position.objects.select_related("area").filter(pk=position_id).first()
        if position is None:
            return Response({"detail": "Position not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            set_review_period(
                position=position,
                days=data.validated_data["period_days"],
                starts_on=data.validated_data["starts_on"],
                by=request.user.user_id,
            )
        except InvalidSetting as exc:
            return Response(
                {"detail": "This review period can't be saved.", "reasons": exc.reasons},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        [row] = [
            r
            for r in review_settings_overview(timezone.localdate())
            if r["position_id"] == position.id
        ]
        return Response(row)
