"""HTTP endpoints for login and logout. Thin: validate, call a service, respond."""

from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from audit.service import record
from core.db_context import set_actor
from identity import otp
from identity.login import start_login
from identity.models import OtpPurpose
from identity.roles import Role
from identity.serializers import LoginSerializer, OtpVerifySerializer, PasswordChangeSerializer
from licensing.models import Licence
from positions.service import positions_held


def _invalid() -> Response:
    return Response({"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_protect, name="dispatch")
class LoginStartView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        data = LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        challenge = start_login(
            data.validated_data["role"],
            data.validated_data["identifier"],
            data.validated_data["password"],
        )
        if challenge is None:
            return _invalid()
        return Response({"challenge_id": str(challenge.public_id)})


@method_decorator(csrf_protect, name="dispatch")
class LoginVerifyView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request):
        data = OtpVerifySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = otp.verify(
            challenge_id=str(data.validated_data["challenge_id"]),
            purpose=OtpPurpose.LOGIN,
            code=data.validated_data["code"],
        )
        if user is None or (user.locked_until and user.locked_until > timezone.now()):
            # A code verified after the account was locked (e.g. by a burst of failed
            # attempts on another challenge) must not complete the login (R11).
            record(action="login.otp_failed")
            return _invalid()
        login(request, user)  # also rotates the session key (prevents session fixation)
        set_actor(user_id=user.user_id, role=user.role)
        record(action="login.succeeded", actor=user.user_id)
        return Response(
            {
                "user_id": user.user_id,
                "role": user.role,
                "must_change_password": user.must_change_password,
            }
        )


class LogoutView(APIView):
    def post(self, request):
        record(action="logout", actor=request.user.user_id)
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    def get(self, request):
        user = request.user
        positions = sorted(positions_held(user), key=lambda position: position.id)
        return Response(
            {
                "user_id": user.user_id,
                "role": user.role,
                "display_name": display_name(user, positions),
                "must_change_password": user.must_change_password,
                "positions": [
                    {"id": p.id, "title": p.title, "level": p.area.level} for p in positions
                ],
            }
        )


class PasswordChangeView(APIView):
    """Choose a new password; required first for a password the system issued (A3). The
    session is kept (its auth hash is updated), so the user stays signed in."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        data = PasswordChangeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(data.validated_data["current_password"]):
            return Response(
                {"current_password": ["Your current password is not correct."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        new_password = data.validated_data["new_password"]
        if new_password == data.validated_data["current_password"]:
            return Response(
                {"new_password": ["Choose a password different from your current one."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            validate_password(new_password, user)
        except ValidationError as exc:
            return Response({"new_password": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(new_password)
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        update_session_auth_hash(request, user)
        record(
            action="auth.password_changed",
            actor=user.user_id,
            subject_type="user",
            subject_id=user.user_id,
        )
        return Response({"must_change_password": False})


def display_name(user, positions) -> str:
    """The name the app shows for an account. Also used by the demo SMS inbox (as SYSTEM)."""
    if user.role == Role.LICENSEE:
        # Read under the caller's RLS; for the licensee themselves that limits it to their
        # business, and as SYSTEM the GSTIN filter does.
        licence = (
            Licence.objects.filter(gstin_index=user.licensee_gstin_index).order_by("id").first()
        )
        return licence.holder_name if licence else user.get_role_display()
    if user.role == Role.PERSONNEL:
        return ", ".join(p.title for p in positions) or "Unassigned officer"
    return user.get_role_display()
