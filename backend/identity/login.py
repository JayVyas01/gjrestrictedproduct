"""First login step: check the password, enforce lockout, then send an OTP.

Every outcome looks the same to the caller except success, so the API cannot be used
to discover which user IDs exist. Re-requesting codes with a known-correct password is
also capped (R10): otherwise a valid password would grant unlimited OTP guesses across
many challenges instead of the usual per-challenge attempt limit.
"""

from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.utils import timezone

from audit.service import record
from identity import otp
from identity.models import OtpChallenge, OtpPurpose, User

LOCKOUT_THRESHOLD = 5
LOCKOUT_DURATION = timedelta(minutes=15)


def start_login(user_id: str, password: str) -> OtpChallenge | None:
    user = User.objects.select_for_update().filter(user_id=user_id.strip().upper()).first()
    if user is None:
        make_password(password)  # spend the same time as a real check
        record(action="login.failed", reason="unknown user id", payload={"attempted": user_id[:32]})
        return None

    now = timezone.now()
    if user.locked_until and user.locked_until > now:
        record(action="login.blocked_locked", subject_type="user", subject_id=user.user_id)
        return None

    if not user.is_active or not user.check_password(password):
        _register_failure(user, now)
        return None

    user.failed_login_count = 0
    user.save(update_fields=["failed_login_count"])

    if _too_many_codes(user, now):
        _lock_for_too_many_codes(user, now)
        return None

    return otp.issue(user, OtpPurpose.LOGIN)


def _register_failure(user: User, now) -> None:
    user.failed_login_count += 1
    if user.failed_login_count >= LOCKOUT_THRESHOLD:
        user.failed_login_count = 0
        user.locked_until = now + LOCKOUT_DURATION
        record(action="login.locked", subject_type="user", subject_id=user.user_id)
    user.save(update_fields=["failed_login_count", "locked_until"])
    record(action="login.failed", subject_type="user", subject_id=user.user_id)


def _too_many_codes(user: User, now) -> bool:
    recent = OtpChallenge.objects.filter(
        user=user, purpose=OtpPurpose.LOGIN, created_at__gte=now - LOCKOUT_DURATION
    ).count()
    return recent >= LOCKOUT_THRESHOLD


def _lock_for_too_many_codes(user: User, now) -> None:
    user.locked_until = now + LOCKOUT_DURATION
    user.failed_login_count = 0
    record(action="login.locked", subject_type="user", subject_id=user.user_id)
    user.save(update_fields=["locked_until", "failed_login_count"])
