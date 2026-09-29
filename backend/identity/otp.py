"""Issue and check one-time passcodes.

Codes are stored only as an HMAC keyed with a server secret, so a database leak does not
reveal them (a plain hash of a 6-digit code could be brute-forced instantly).
A challenge belongs either to a user (login, decisions) or to a subject that has
no account yet (enrolment). The caller must be inside a transaction (the request middleware
guarantees this).
"""

import hashlib
import hmac
import secrets
from collections.abc import Callable
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection
from django.utils import timezone

from identity.models import OtpChallenge, User
from identity.otp_delivery import get_sender

OTP_LENGTH = 6
OTP_TTL = timedelta(minutes=5)
OTP_MAX_ATTEMPTS = 5


def _hash_code(challenge: OtpChallenge, code: str) -> str:
    message = f"{challenge.public_id}:{code}".encode()
    return hmac.new(settings.OTP_HMAC_KEY.encode(), message, hashlib.sha256).hexdigest()


def _new_code() -> str:
    return f"{secrets.randbelow(10**OTP_LENGTH):0{OTP_LENGTH}d}"


def _create_and_send(challenge: OtpChallenge, contact: str) -> OtpChallenge:
    code = _new_code()
    challenge.code_hash = _hash_code(challenge, code)
    challenge.save()
    get_sender().send(contact, code)
    return challenge


def issue(user: User, purpose: str) -> OtpChallenge:
    # Lock the user row so concurrent issue() calls for the same user+purpose serialise:
    # without this, two transactions could both see the old challenge as open under
    # READ COMMITTED and each close-then-insert, leaving two open challenges.
    User.objects.select_for_update().get(pk=user.pk)
    now = timezone.now()
    OtpChallenge.objects.filter(user=user, purpose=purpose, closed_at__isnull=True).update(
        closed_at=now
    )
    challenge = OtpChallenge(user=user, purpose=purpose, expires_at=now + OTP_TTL)
    return _create_and_send(challenge, user.get_contact())


def issue_for_subject(*, subject: str, contact: str, purpose: str) -> OtpChallenge:
    if not subject:
        raise ValueError("subject is required")
    # Serialise per subject (there is no user row to lock), so a new code reliably cancels the old.
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [subject])
    now = timezone.now()
    OtpChallenge.objects.filter(subject=subject, purpose=purpose, closed_at__isnull=True).update(
        closed_at=now
    )
    challenge = OtpChallenge(subject=subject, purpose=purpose, expires_at=now + OTP_TTL)
    return _create_and_send(challenge, contact)


def _consume(
    *, challenge_id: str, purpose: str, code: str, usable: Callable[[OtpChallenge], bool]
) -> OtpChallenge | None:
    try:
        challenge = (
            OtpChallenge.objects.select_for_update(of=("self",))
            .select_related("user")
            .get(public_id=challenge_id, purpose=purpose, closed_at__isnull=True)
        )
    except (OtpChallenge.DoesNotExist, ValidationError):
        return None

    now = timezone.now()
    challenge.attempts += 1
    matches = hmac.compare_digest(challenge.code_hash, _hash_code(challenge, code))
    success = matches and now < challenge.expires_at and usable(challenge)
    if success or now >= challenge.expires_at or challenge.attempts >= OTP_MAX_ATTEMPTS:
        challenge.closed_at = now
    challenge.save(update_fields=["attempts", "closed_at"])
    return challenge if success else None


def verify(*, challenge_id: str, purpose: str, code: str) -> User | None:
    challenge = _consume(
        challenge_id=challenge_id,
        purpose=purpose,
        code=code,
        usable=lambda c: c.user is not None and c.user.is_active,
    )
    if challenge is None:
        return None
    # Re-read and lock the user so a lockout committing concurrently is not missed.
    return User.objects.select_for_update().get(pk=challenge.user_id)


def verify_subject(*, challenge_id: str, purpose: str, code: str) -> str | None:
    challenge = _consume(
        challenge_id=challenge_id, purpose=purpose, code=code, usable=lambda c: c.user is None
    )
    return challenge.subject if challenge else None
