"""Party self sign-up, demo mode only (A4, A5): GSTIN, then the phone on file as proof.

A GSTIN is public, so typing one must never be enough to claim a business. Like enrolment
(`licensing/enrolment.py`), the code goes to the contact ON FILE of an ACTIVE licence for that
GSTIN, never to anything the request supplies; the phone the request gives only has to match
that contact. Every failure looks the same, so the form cannot tell which GSTINs exist, are
signed up, or which phone is on file. Audit events carry the GSTIN's blind index, never the raw
GSTIN, phone or email.

The account gets every licence of the GSTIN (and so all its stock), because licences and stock
are linked by `licensee_gstin_index`.

Phones are compared on digits only (spaces, "+" and dashes ignored), on their last 10 digits,
so "+91 98000 00777", "919800000777" and "9800000777" all match "+919800000777".

The views check DEMO_MODE (404 otherwise); this module assumes it.
"""

import re
from datetime import datetime

from django.contrib.auth.hashers import make_password
from django.utils import timezone

from audit.service import record
from core import crypto
from core.db_context import acting_as_system
from demo.models import DemoCredential, DemoPendingSignup
from identity import otp
from identity.models import OtpChallenge, OtpPurpose, User, email_index
from identity.roles import Role
from licensing.models import Licence, LicenceStatus

SUBJECT_PREFIX = "gstin:"
PHONE_DIGITS = 10
SYSTEM_REASON = "demo_signup"


def _phone_digits(phone: str) -> str:
    return re.sub(r"\D", "", phone)


def phones_match(typed: str, on_file: str) -> bool:
    """True when both have at least 10 digits and their last 10 digits are equal."""
    typed_digits, file_digits = _phone_digits(typed), _phone_digits(on_file)
    if len(typed_digits) < PHONE_DIGITS or len(file_digits) < PHONE_DIGITS:
        return False
    return typed_digits[-PHONE_DIGITS:] == file_digits[-PHONE_DIGITS:]


def normalise_gstin(gstin: str) -> str:
    return gstin.strip().upper()


def _active_licences(gstin_index: str):
    return Licence.objects.filter(gstin_index=gstin_index, status=LicenceStatus.ACTIVE).order_by(
        "id"
    )


def _taken(*, gstin_index: str, email: str) -> bool:
    """A GSTIN or email that already has an account (one account per GSTIN, per email)."""
    return (
        User.objects.filter(licensee_gstin_index=gstin_index).exists()
        or User.objects.filter(email_index=email_index(email)).exists()
    )


def _stale_before(now: datetime) -> datetime:
    return now - otp.OTP_TTL


def start_signup(
    *, gstin: str, phone: str, email: str, business_name: str, address: str, password: str
) -> OtpChallenge | None:
    """Caller must validate every field (and the password) first. None = no match."""
    gstin_index = crypto.blind_index("gstin", normalise_gstin(gstin))
    with acting_as_system(SYSTEM_REASON):
        matched = None
        if not _taken(gstin_index=gstin_index, email=email):
            matched = next(
                (
                    lic
                    for lic in _active_licences(gstin_index)
                    if phones_match(phone, lic.contact())
                ),
                None,
            )
        if matched is None:
            record(action="signup.failed", payload={"attempted_index": gstin_index})
            return None
        contact = matched.contact()
    challenge = otp.issue_for_subject(
        subject=SUBJECT_PREFIX + gstin_index, contact=contact, purpose=OtpPurpose.ENROL
    )
    # A newer code closed the older challenge; drop its pending row, and any stale ones.
    DemoPendingSignup.objects.filter(gstin_index=gstin_index).delete()
    DemoPendingSignup.objects.filter(created_at__lt=_stale_before(timezone.now())).delete()
    DemoPendingSignup.objects.create(
        challenge_public_id=challenge.public_id,
        gstin_index=gstin_index,
        licence_id=matched.id,
        email_encrypted=crypto.encrypt(email.strip().lower()),
        business_name=business_name,
        address_encrypted=crypto.encrypt(address.strip()),
        password_hash=make_password(password),
        password_encrypted=crypto.encrypt(password),
    )
    # Audit after the external send: record() must be the last lock a request takes.
    with acting_as_system(SYSTEM_REASON):
        record(
            action="signup.otp_sent",
            payload={"attempted_index": gstin_index, "challenge_id": str(challenge.public_id)},
        )
    return challenge


def complete_signup(*, challenge_id: str, code: str) -> User | None:
    subject = otp.verify_subject(challenge_id=challenge_id, purpose=OtpPurpose.ENROL, code=code)
    if subject is None or not subject.startswith(SUBJECT_PREFIX):
        return None
    pending = DemoPendingSignup.objects.filter(
        challenge_public_id=challenge_id,
        gstin_index=subject.removeprefix(SUBJECT_PREFIX),
        created_at__gte=_stale_before(timezone.now()),
    ).first()
    if pending is None:
        return None
    email = crypto.decrypt(pending.email_encrypted)
    with acting_as_system(SYSTEM_REASON):
        licence = _active_licences(pending.gstin_index).filter(id=pending.licence_id).first()
        if licence is None or _taken(gstin_index=pending.gstin_index, email=email):
            return None
        contact = licence.contact()
    user = User.objects.create_user(
        role=Role.LICENSEE,
        password=None,
        contact=contact,
        licensee_gstin_index=pending.gstin_index,
        email=email,
        address=crypto.decrypt(pending.address_encrypted),
    )
    user.password = pending.password_hash  # hashed at start; the plain text is never re-read
    user.save(update_fields=["password"])
    DemoCredential.objects.create(
        user_id=user.user_id, password_encrypted=pending.password_encrypted
    )
    pending.delete()
    record(
        action="signup.completed",
        actor=user.user_id,
        subject_type="user",
        subject_id=user.user_id,
    )
    return user


def candidates() -> list[dict]:
    """Licensed GSTINs with no account yet, for testers to pick one. Demo only; read as SYSTEM.

    The phone on file and holder name are those of the GSTIN's first ACTIVE licence.
    """
    with acting_as_system(SYSTEM_REASON):
        signed_up = set(
            User.objects.exclude(licensee_gstin_index="").values_list(
                "licensee_gstin_index", flat=True
            )
        )
        first_active: dict[str, Licence] = {}
        for licence in Licence.objects.filter(status=LicenceStatus.ACTIVE).order_by("id"):
            if licence.gstin_index not in signed_up:
                first_active.setdefault(licence.gstin_index, licence)
        rows = [
            {
                "gstin": licence.gstin(),
                "business_name": licence.holder_name,
                "phone_on_file": licence.contact(),
            }
            for licence in first_active.values()
        ]
    return sorted(rows, key=lambda row: (row["business_name"], row["gstin"]))
