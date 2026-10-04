"""Licence-gated enrolment: only a business already on record can create an account.

The user proves control by entering the code sent to the contact ON FILE for the licence.
Nothing in the request can change where the code goes. Failures all look the same, so the
endpoint cannot be used to discover which licences or GSTINs exist.
"""

from audit.service import record
from core import crypto
from core.db_context import acting_as_system
from identity import otp
from identity.models import OtpChallenge, OtpPurpose, User
from identity.roles import Role
from licensing.models import Licence, LicenceStatus
from licensing.service import find_by_number

SUBJECT_PREFIX = "licence:"


def _already_enrolled(gstin_index: str) -> bool:
    return User.objects.filter(licensee_gstin_index=gstin_index).exists()


def start_enrolment(*, licence_number: str, gstin: str) -> OtpChallenge | None:
    with acting_as_system("enrolment"):
        licence = find_by_number(licence_number)
        matches = (
            licence is not None
            and licence.gstin_index == crypto.blind_index("gstin", gstin)
            and licence.status == LicenceStatus.ACTIVE
            and not _already_enrolled(licence.gstin_index)
        )
        if not matches:
            record(
                action="enrolment.failed",
                payload={"attempted_index": crypto.blind_index("licence_number", licence_number)},
            )
            return None
        contact = licence.contact()
        subject = SUBJECT_PREFIX + str(licence.id)
        licence_id = str(licence.id)
    challenge = otp.issue_for_subject(subject=subject, contact=contact, purpose=OtpPurpose.ENROL)
    # Audit after the external send: record() must be the last lock a request takes.
    with acting_as_system("enrolment"):
        record(
            action="enrolment.otp_sent",
            subject_type="licence",
            subject_id=licence_id,
            payload={"challenge_id": str(challenge.public_id)},
        )
    return challenge


def complete_enrolment(*, challenge_id: str, code: str, password: str) -> User | None:
    """Caller must validate the password BEFORE calling, so a weak one never uses up the code."""
    subject = otp.verify_subject(challenge_id=challenge_id, purpose=OtpPurpose.ENROL, code=code)
    if subject is None or not subject.startswith(SUBJECT_PREFIX):
        return None
    try:
        licence_id = int(subject.removeprefix(SUBJECT_PREFIX))
    except ValueError:
        return None
    with acting_as_system("enrolment"):
        licence = Licence.objects.filter(id=licence_id, status=LicenceStatus.ACTIVE).first()
        if licence is None or _already_enrolled(licence.gstin_index):
            return None
        contact = licence.contact()
        gstin_index = licence.gstin_index
    user = User.objects.create_user(
        role=Role.LICENSEE, password=password, contact=contact, licensee_gstin_index=gstin_index
    )
    record(
        action="enrolment.completed",
        actor=user.user_id,
        subject_type="user",
        subject_id=user.user_id,
    )
    return user
