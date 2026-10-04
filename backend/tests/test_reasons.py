import pytest

from reasons.models import ReasonCode, ReasonKind
from reasons.service import InvalidReason, active_reasons, resolve_reason
from tests.conftest import TEST_PASSWORD

pytestmark = pytest.mark.django_db


def test_defaults_are_seeded_for_every_kind(app_db):
    for kind in ReasonKind.values:
        codes = list(active_reasons(kind).values_list("code", flat=True))
        assert "OTHER" in codes
        assert len(codes) >= 4


def test_buyer_defaults_match_the_spec(app_db):
    labels = set(active_reasons(ReasonKind.BUYER_REJECTION).values_list("label", flat=True))
    assert {
        "I did not place this order",
        "Quantity does not match",
        "Wrong substance",
        "Terms dispute",
    } <= labels


def test_other_requires_text(app_db):
    with pytest.raises(InvalidReason, match="describe the reason"):
        resolve_reason(ReasonKind.OFFICER_REJECTION, "OTHER", "   ")
    reason = resolve_reason(ReasonKind.OFFICER_REJECTION, "OTHER", "Seal was broken")
    assert reason.code == "OTHER"


def test_unknown_or_inactive_code_is_rejected(app_db):
    with pytest.raises(InvalidReason, match="Choose a reason"):
        resolve_reason(ReasonKind.BUYER_REJECTION, "NO_SUCH_CODE", "")
    ReasonCode.objects.filter(kind=ReasonKind.BUYER_REJECTION, code="TERMS_DISPUTE").update(
        active=False
    )
    with pytest.raises(InvalidReason):
        resolve_reason(ReasonKind.BUYER_REJECTION, "TERMS_DISPUTE", "")


def test_code_of_another_kind_is_rejected(app_db):
    with pytest.raises(InvalidReason):
        resolve_reason(ReasonKind.BUYER_REJECTION, "TRANSPORTER_INVALID", "")


def test_admin_can_add_a_new_reason_without_code_change(app_db):
    ReasonCode.objects.create(
        kind=ReasonKind.OFFICER_REJECTION, code="SEAL_BROKEN", label="Seal broken", sort_order=50
    )
    assert resolve_reason(ReasonKind.OFFICER_REJECTION, "SEAL_BROKEN", "").label == "Seal broken"


def test_reason_code_api_lists_active_codes(app_db, client, make_user, otp_outbox):
    user = make_user()
    first = client.post(
        "/api/auth/login",
        {"user_id": user.user_id, "password": TEST_PASSWORD},
        content_type="application/json",
    )
    client.post(
        "/api/auth/login/verify",
        {"challenge_id": first.json()["challenge_id"], "code": otp_outbox[-1][1]},
        content_type="application/json",
    )
    body = client.get("/api/reason-codes?kind=BUYER_REJECTION").json()
    assert {
        "code": "NOT_ORDERED",
        "label": "I did not place this order",
        "requires_text": False,
    } in body
    assert client.get("/api/reason-codes?kind=NOPE").status_code == 400


def test_reason_code_api_requires_login(app_db, client):
    assert client.get("/api/reason-codes?kind=BUYER_REJECTION").status_code == 403
