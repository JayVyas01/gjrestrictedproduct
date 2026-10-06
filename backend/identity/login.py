"""First login step: find the account for the chosen role, check the password, enforce
lockout, then send an OTP.

A party signs in with its GSTIN and officials with their email (owner decisions A1/A2,
2026-10-06); `user_id` stays the internal key. Every outcome looks the same to the caller
except success, so the API cannot be used to discover which identifiers exist, or which
role an account has. Re-requesting codes with a known-correct password is
also capped (R10): otherwise a valid password would grant unlimited OTP guesses across
many challenges instead of the usual per-challenge attempt limit. The password is always
checked, even for locked or inactive accounts (R11), so response time cannot be used to
tell whether an account exists.
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.utils import timezone

from audit.service import record
from core import crypto
from core.db_context import acting_as_system
from identity import otp
from identity.models import OtpChallenge, OtpPurpose, User, email_index
from identity.roles import ACCOUNT_ROLE, LoginRole, Role
from licensing.models import Licence
from positions.models import AreaLevel
from positions.service import positions_held

LOCKOUT_THRESHOLD = 5
LOCKOUT_DURATION = timedelta(minutes=15)
# Owner decision (2026-10-05): presenters switch personas often, so demo mode (localhost
# only, enforced by the DEMO_MODE guard) allows 30 code requests per 15 minutes.
# Wrong passwords still lock after LOCKOUT_THRESHOLD in every mode.
DEMO_CODE_REQUEST_LIMIT = 30


def code_request_limit() -> int:
    return DEMO_CODE_REQUEST_LIMIT if settings.DEMO_MODE else LOCKOUT_THRESHOLD


# Which current position lets an officer sign in under each officer role.
POSITION_LEVEL = {
    LoginRole.AREA_OFFICER: AreaLevel.TALUKA,
    LoginRole.SUPERINTENDENT: AreaLevel.DISTRICT,
}


def _account_for(role: str, identifier: str) -> User | None:
    """The account `identifier` names under the sign-in `role`, or None. An account of another
    role, or an officer without a current position at the right level, counts as unknown."""
    if role not in ACCOUNT_ROLE:
        return None
    if role == LoginRole.PARTY:
        # Normalised as licensing does (strip, upper), then matched by blind index.
        lookup = {"licensee_gstin_index": crypto.blind_index("gstin", identifier.strip().upper())}
    else:
        if not identifier.strip():
            return None
        lookup = {"email_index": email_index(identifier)}
    user = (
        User.objects.select_for_update()
        .filter(role=ACCOUNT_ROLE[LoginRole(role)], **lookup)
        .first()
    )
    if user is not None and role in POSITION_LEVEL:
        levels = {position.area.level for position in positions_held(user)}
        if POSITION_LEVEL[LoginRole(role)] not in levels:
            return None
    return user


def login_identity(user: User) -> tuple[str, str]:
    """(sign-in role, identifier) for an account; ("", "") when it cannot sign in, such as an
    officer without a position or a licensee whose business has no licence on record. A user
    holding both an Area Officer and a Superintendent position gets the Area Officer role.
    Used by the demo persona list and the tests."""
    if user.role == Role.LICENSEE:
        with acting_as_system("login_identity"):
            licence = (
                Licence.objects.filter(gstin_index=user.licensee_gstin_index).order_by("id").first()
            )
            return (LoginRole.PARTY.value, licence.gstin()) if licence else ("", "")
    if user.role == Role.PERSONNEL:
        levels = {position.area.level for position in positions_held(user)}
        for role, level in POSITION_LEVEL.items():
            if level in levels:
                return role.value, user.get_email()
        return "", ""
    return LoginRole(user.role).value, user.get_email()


def start_login(role: str, identifier: str, password: str) -> OtpChallenge | None:
    user = _account_for(role, identifier)
    if user is None:
        make_password(password)  # spend the same time as a real check
        record(
            action="login.failed",
            reason="unknown identifier",
            payload={"attempted_index": crypto.blind_index("login_attempt", identifier or "-")},
        )
        return None

    now = timezone.now()
    # Always check the password, even for a locked or inactive account, so that a
    # branch taken before hashing never leaks (via timing) whether the account exists.
    password_ok = user.check_password(password)

    if user.locked_until and user.locked_until > now:
        record(action="login.blocked_locked", subject_type="user", subject_id=user.user_id)
        return None

    if not user.is_active or not password_ok:
        _register_failure(user, now)
        return None

    user.failed_login_count = 0
    user.save(update_fields=["failed_login_count"])

    if _too_many_codes(user, now):
        _lock_for_too_many_codes(user, now)
        return None

    return otp.issue(user, OtpPurpose.LOGIN)


def _close_open_login_challenges(user: User, now) -> None:
    # A lock must invalidate any code already sent, or the lock is cosmetic (R11).
    OtpChallenge.objects.filter(user=user, purpose=OtpPurpose.LOGIN, closed_at__isnull=True).update(
        closed_at=now
    )


def _register_failure(user: User, now) -> None:
    user.failed_login_count += 1
    if user.failed_login_count >= LOCKOUT_THRESHOLD:
        user.failed_login_count = 0
        user.locked_until = now + LOCKOUT_DURATION
        _close_open_login_challenges(user, now)
        record(action="login.locked", subject_type="user", subject_id=user.user_id)
    user.save(update_fields=["failed_login_count", "locked_until"])
    record(action="login.failed", subject_type="user", subject_id=user.user_id)


def _too_many_codes(user: User, now) -> bool:
    recent = OtpChallenge.objects.filter(
        user=user, purpose=OtpPurpose.LOGIN, created_at__gte=now - LOCKOUT_DURATION
    ).count()
    return recent >= code_request_limit()


def _lock_for_too_many_codes(user: User, now) -> None:
    user.locked_until = now + LOCKOUT_DURATION
    user.failed_login_count = 0
    _close_open_login_challenges(user, now)
    record(action="login.locked", subject_type="user", subject_id=user.user_id)
    user.save(update_fields=["locked_until", "failed_login_count"])
