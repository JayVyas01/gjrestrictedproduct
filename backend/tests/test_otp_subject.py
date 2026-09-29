import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from identity import otp
from identity.models import OtpChallenge, OtpPurpose

pytestmark = pytest.mark.django_db

SUBJECT = "licence:1"


def test_subject_code_goes_to_the_given_contact(app_db, otp_outbox):
    otp.issue_for_subject(subject=SUBJECT, contact="+919800000555", purpose=OtpPurpose.ENROL)
    assert otp_outbox[-1][0] == "+919800000555"


def test_verify_subject_returns_subject_once(app_db, otp_outbox):
    challenge = otp.issue_for_subject(
        subject=SUBJECT, contact="+919800000555", purpose=OtpPurpose.ENROL
    )
    args = dict(
        challenge_id=str(challenge.public_id), purpose=OtpPurpose.ENROL, code=otp_outbox[-1][1]
    )
    assert otp.verify_subject(**args) == SUBJECT
    assert otp.verify_subject(**args) is None


def test_user_verify_rejects_subject_challenge(app_db, otp_outbox):
    challenge = otp.issue_for_subject(
        subject=SUBJECT, contact="+919800000555", purpose=OtpPurpose.ENROL
    )
    code = otp_outbox[-1][1]
    assert (
        otp.verify(challenge_id=str(challenge.public_id), purpose=OtpPurpose.ENROL, code=code)
        is None
    )


def test_subject_verify_rejects_user_challenge(app_db, make_user, otp_outbox):
    challenge = otp.issue(make_user(), OtpPurpose.LOGIN)
    code = otp_outbox[-1][1]
    assert (
        otp.verify_subject(
            challenge_id=str(challenge.public_id), purpose=OtpPurpose.LOGIN, code=code
        )
        is None
    )


def test_new_subject_challenge_supersedes_old(app_db, otp_outbox):
    first = otp.issue_for_subject(
        subject=SUBJECT, contact="+919800000555", purpose=OtpPurpose.ENROL
    )
    first_code = otp_outbox[-1][1]
    otp.issue_for_subject(subject=SUBJECT, contact="+919800000555", purpose=OtpPurpose.ENROL)
    assert (
        otp.verify_subject(
            challenge_id=str(first.public_id), purpose=OtpPurpose.ENROL, code=first_code
        )
        is None
    )


def test_database_requires_exactly_one_of_user_or_subject(app_db, make_user):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            OtpChallenge.objects.create(
                user=make_user(),
                subject=SUBJECT,
                purpose=OtpPurpose.ENROL,
                code_hash="x" * 64,
                expires_at=timezone.now(),
            )


def test_database_allows_one_open_challenge_per_subject_and_purpose(app_db, otp_outbox):
    otp.issue_for_subject(subject=SUBJECT, contact="+919800000555", purpose=OtpPurpose.ENROL)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            OtpChallenge.objects.create(
                subject=SUBJECT,
                purpose=OtpPurpose.ENROL,
                code_hash="x" * 64,
                expires_at=timezone.now(),
            )


def test_issue_for_subject_rejects_empty_subject(app_db, otp_outbox):
    with pytest.raises(ValueError):
        otp.issue_for_subject(subject="", contact="+919800000555", purpose=OtpPurpose.ENROL)
