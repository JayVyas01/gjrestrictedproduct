from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from identity import otp
from identity.models import OtpChallenge, OtpPurpose

pytestmark = pytest.mark.django_db


def test_issue_sends_six_digit_code_to_registered_contact(app_db, make_user, otp_outbox):
    user = make_user(contact="+919811111111")
    otp.issue(user, OtpPurpose.LOGIN)
    contact, code = otp_outbox[-1]
    assert contact == "+919811111111"
    assert len(code) == 6 and code.isdigit()


def test_code_is_not_stored_in_plaintext(app_db, make_user, otp_outbox):
    challenge = otp.issue(make_user(), OtpPurpose.LOGIN)
    code = otp_outbox[-1][1]
    stored = OtpChallenge.objects.get(pk=challenge.pk).code_hash
    assert stored != code and len(stored) == 64


def test_correct_code_returns_user_once(app_db, make_user, otp_outbox):
    user = make_user()
    challenge = otp.issue(user, OtpPurpose.LOGIN)
    code = otp_outbox[-1][1]
    args = dict(challenge_id=str(challenge.public_id), purpose=OtpPurpose.LOGIN, code=code)
    assert otp.verify(**args) == user
    assert otp.verify(**args) is None  # single use


def test_wrong_code_is_rejected_and_counted(app_db, make_user, otp_outbox):
    challenge = otp.issue(make_user(), OtpPurpose.LOGIN)
    code = otp_outbox[-1][1]
    wrong = "000000" if code != "000000" else "111111"
    assert (
        otp.verify(challenge_id=str(challenge.public_id), purpose=OtpPurpose.LOGIN, code=wrong)
        is None
    )
    challenge.refresh_from_db()
    assert challenge.attempts == 1


def test_challenge_closes_after_max_attempts(app_db, make_user, otp_outbox):
    challenge = otp.issue(make_user(), OtpPurpose.LOGIN)
    code = otp_outbox[-1][1]
    wrong = "000000" if code != "000000" else "111111"
    challenge_id = str(challenge.public_id)
    for _ in range(otp.OTP_MAX_ATTEMPTS):
        otp.verify(challenge_id=challenge_id, purpose=OtpPurpose.LOGIN, code=wrong)
    assert otp.verify(challenge_id=challenge_id, purpose=OtpPurpose.LOGIN, code=code) is None


def test_expired_code_is_rejected(app_db, make_user, otp_outbox):
    challenge = otp.issue(make_user(), OtpPurpose.LOGIN)
    code = otp_outbox[-1][1]
    OtpChallenge.objects.filter(pk=challenge.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    assert (
        otp.verify(challenge_id=str(challenge.public_id), purpose=OtpPurpose.LOGIN, code=code)
        is None
    )


def test_new_challenge_supersedes_the_old_one(app_db, make_user, otp_outbox):
    user = make_user()
    first = otp.issue(user, OtpPurpose.LOGIN)
    first_code = otp_outbox[-1][1]
    otp.issue(user, OtpPurpose.LOGIN)
    assert (
        otp.verify(challenge_id=str(first.public_id), purpose=OtpPurpose.LOGIN, code=first_code)
        is None
    )


def test_inactive_user_cannot_complete_otp(app_db, make_user, otp_outbox):
    user = make_user()
    challenge = otp.issue(user, OtpPurpose.LOGIN)
    code = otp_outbox[-1][1]
    user.is_active = False
    user.save(update_fields=["is_active"])
    assert (
        otp.verify(challenge_id=str(challenge.public_id), purpose=OtpPurpose.LOGIN, code=code)
        is None
    )


def test_malformed_challenge_id_is_rejected(app_db):
    assert otp.verify(challenge_id="not-a-uuid", purpose=OtpPurpose.LOGIN, code="123456") is None


def test_database_allows_one_open_challenge_per_user_and_purpose(app_db, make_user, otp_outbox):
    user = make_user()
    otp.issue(user, OtpPurpose.LOGIN)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            OtpChallenge.objects.create(
                user=user,
                purpose=OtpPurpose.LOGIN,
                code_hash="x" * 64,
                expires_at=timezone.now(),
            )
