"""Issue and check one-time passcodes.

Codes are stored only as an HMAC keyed with a server secret, so a database leak does not
reveal them (a plain hash of a 6-digit code could be brute-forced instantly).
The caller must be inside a transaction (the request middleware guarantees this).
"""

import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from identity.models import OtpChallenge, User
from identity.otp_delivery import get_sender

OTP_LENGTH = 6
OTP_TTL = timedelta(minutes=5)
OTP_MAX_ATTEMPTS = 5


def _hash_code(challenge: OtpChallenge, code: str) -> str:
    message = f"{challenge.public_id}:{code}".encode()
    return hmac.new(settings.OTP_HMAC_KEY.encode(), message, hashlib.sha256).hexdigest()


def issue(user: User, purpose: str) -> OtpChallenge:
    # Lock the user row so concurrent issue() calls for the same user+purpose serialise:
    # without this, two transactions could both see the old challenge as open under
    # READ COMMITTED and each close-then-insert, leaving two open challenges.
    User.objects.select_for_update().get(pk=user.pk)
    now = timezone.now()
    OtpChallenge.objects.filter(user=user, purpose=purpose, closed_at__isnull=True).update(
        closed_at=now
    )
    code = f"{secrets.randbelow(10**OTP_LENGTH):0{OTP_LENGTH}d}"
    challenge = OtpChallenge(user=user, purpose=purpose, expires_at=now + OTP_TTL)
    challenge.code_hash = _hash_code(challenge, code)
    challenge.save()
    get_sender().send(user.get_contact(), code)
    return challenge


def verify(*, challenge_id: str, purpose: str, code: str) -> User | None:
    try:
        challenge = (
            OtpChallenge.objects.select_for_update()
            .select_related("user")
            .get(public_id=challenge_id, purpose=purpose, closed_at__isnull=True)
        )
    except (OtpChallenge.DoesNotExist, ValidationError):
        return None

    now = timezone.now()
    challenge.attempts += 1
    matches = hmac.compare_digest(challenge.code_hash, _hash_code(challenge, code))
    success = matches and now < challenge.expires_at and challenge.user.is_active
    if success or now >= challenge.expires_at or challenge.attempts >= OTP_MAX_ATTEMPTS:
        challenge.closed_at = now
    challenge.save(update_fields=["attempts", "closed_at"])
    return challenge.user if success else None
