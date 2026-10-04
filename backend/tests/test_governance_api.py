"""The rule-change API: draft, read, withdraw and decide over HTTP (D2d Task 3)."""

from types import SimpleNamespace

import pytest
from django.db import transaction
from django.test import Client

from audit.models import AuditEvent
from catalogue.models import LicenceType
from core.db_context import SYSTEM_ROLE, acting_as_system, set_actor
from governance.models import ProposalStatus, RuleChangeProposal
from identity.models import OtpChallenge
from identity.roles import Role
from positions.service import assign
from tests.conftest import TEST_PASSWORD
from tests.test_transaction_api import login, post

pytestmark = pytest.mark.django_db

JUSTIFICATION = "Retail outlets now stock beer in larger volumes."
NEW_TYPE = {"code": "BEER_BAR", "name": "Beer bar", "description": "On-premises beer"}
RULE = {
    "licence_type_code": "RETAIL",
    "class_code": "SPIRITS",
    "may_buy": True,
    "may_sell": False,
    "may_transport": False,
    "max_stock_qty": "2000",
    "max_per_transaction_qty": "300",
    "validity_months": 24,
}
NOT_FOUND = {"detail": "Rule change not found."}
WRONG_CODE = {"detail": "The code is wrong or has expired. Request a new code."}


@pytest.fixture
def people(org, make_user):
    superintendent = make_user(role=Role.PERSONNEL, contact="+919800000603")
    assign(org.district_officer, superintendent, by="test")
    officer = make_user(role=Role.PERSONNEL, contact="+919800000606")
    assign(org.area_officer, officer, by="test")
    return SimpleNamespace(
        licensing=make_user(role=Role.LICENSING_AUTHORITY, contact="+919800000601"),
        head=make_user(role=Role.HEAD_AUTHORITY, contact="+919800000602"),
        head_b=make_user(role=Role.HEAD_AUTHORITY, contact="+919800000604"),
        superintendent=superintendent,
        officer=officer,
        owner=make_user(role=Role.SOFTWARE_OWNER, contact="+919800000605"),
        licensee=make_user(role=Role.LICENSEE, contact="+919800000607"),
    )


def draft(client, kind="NEW_LICENCE_TYPE", payload=None, justification=JUSTIFICATION):
    return post(
        client,
        "/api/rule-changes",
        {"kind": kind, "payload": payload or dict(NEW_TYPE), "justification": justification},
    )


def code_for(client, proposal_id, otp_outbox):
    response = post(client, f"/api/rule-changes/{proposal_id}/decision-code")
    assert response.status_code == 200, response.json()
    return response.json()["challenge_id"], otp_outbox[-1][1]


def decide(client, proposal_id, otp_outbox, outcome="APPROVE", note="", **override):
    challenge_id, code = code_for(client, proposal_id, otp_outbox)
    body = {"challenge_id": challenge_id, "code": code, "outcome": outcome, "note": note}
    return post(client, f"/api/rule-changes/{proposal_id}/decide", {**body, **override})


def status_of(proposal_id):
    with acting_as_system("test"):
        return RuleChangeProposal.objects.get(pk=proposal_id).status


def actions():
    with transaction.atomic():
        set_actor(user_id="test", role=SYSTEM_ROLE)
        return list(AuditEvent.objects.order_by("id").values_list("action", flat=True))


def test_end_to_end_licensing_drafts_head_approves(app_db, client, catalogue, people, otp_outbox):
    login(client, people.licensing, otp_outbox)
    created = draft(client)
    assert created.status_code == 201
    body = created.json()
    assert body["kind"] == "NEW_LICENCE_TYPE"
    assert body["kind_label"] == "New licence type"
    assert body["status"] == "SUBMITTED"
    assert body["justification"] == JUSTIFICATION
    assert body["drafted_by_role"] == "Licensing Authority"
    assert "drafted_by" not in body  # D-R2: only Head Authority and Software Owner see the id
    assert body["proposed"] == {**NEW_TYPE}
    assert body["current"] is None
    assert body["decision"] is None
    assert (body["can_withdraw"], body["can_decide"]) == (True, False)
    proposal_id = body["id"]

    login(client, people.head, otp_outbox)
    seen = client.get(f"/api/rule-changes/{proposal_id}").json()
    assert seen["drafted_by"] == people.licensing.user_id
    assert (seen["can_withdraw"], seen["can_decide"]) == (False, True)
    decided = decide(client, proposal_id, otp_outbox, note="Agreed with the district.")
    assert decided.status_code == 200, decided.json()
    assert decided.json()["status"] == "APPROVED"
    assert decided.json()["decision"]["outcome"] == "APPROVED"
    assert decided.json()["decision"]["note"] == "Agreed with the district."
    assert decided.json()["decision"]["decided_at"]
    assert decided.json()["can_decide"] is False
    assert LicenceType.objects.filter(code="BEER_BAR").exists()

    login(client, people.licensing, otp_outbox)
    types = client.get("/api/catalogue/licence-types").json()
    assert "BEER_BAR" in [t["code"] for t in types]


def test_rule_version_shows_current_and_proposed(app_db, client, catalogue, people, otp_outbox):
    login(client, people.superintendent, otp_outbox)
    body = draft(client, kind="RULE_VERSION", payload=dict(RULE)).json()
    assert body["drafted_by_role"] == "Authorised Personnel"
    assert "drafted_by" not in body
    assert body["proposed"] == {
        **RULE,
        "max_stock_qty": "2000.000",
        "max_per_transaction_qty": "300.000",
        "licence_type_name": "Retail",
        "scope": "Spirits",
        "scope_kind": "class",
        "unit": "L",
    }
    assert body["current"] == {
        "version": 1,
        "may_buy": True,
        "may_sell": True,
        "may_transport": False,
        "max_stock_qty": "1000.000",
        "max_per_transaction_qty": "500.000",
        "validity_months": 12,
    }

    rum = {k: v for k, v in RULE.items() if k != "class_code"}
    new_scope = draft(client, kind="RULE_VERSION", payload={**rum, "substance_code": "RUM"})
    assert new_scope.json()["current"] is None
    assert new_scope.json()["proposed"]["scope"] == "Rum"
    assert new_scope.json()["proposed"]["scope_kind"] == "substance"


def test_decided_proposal_has_no_live_current(app_db, client, catalogue, people, otp_outbox):
    login(client, people.superintendent, otp_outbox)
    drafted = draft(client, kind="RULE_VERSION", payload=dict(RULE)).json()
    assert drafted["current"]["version"] == 1
    login(client, people.head, otp_outbox)
    decided = decide(client, drafted["id"], otp_outbox)
    assert decided.status_code == 200, decided.json()
    detail = client.get(f"/api/rule-changes/{drafted['id']}").json()
    assert detail["status"] == "APPROVED"
    assert detail["current"] is None  # the live rule is now the proposed one; no misleading diff
    assert detail["proposed"] == drafted["proposed"]


def test_threshold_shows_current_and_proposed(
    app_db, client, catalogue, threshold, people, otp_outbox
):
    login(client, people.licensing, otp_outbox)
    payload = {"class_code": "SPIRITS", "superintendent_above_qty": "500"}
    body = draft(client, kind="APPROVAL_THRESHOLD", payload=payload).json()
    assert body["proposed"] == {
        "class_code": "SPIRITS",
        "superintendent_above_qty": "500.000",
        "scope": "Spirits",
        "scope_kind": "class",
        "unit": "L",
    }
    assert body["current"] == {"version": 1, "superintendent_above_qty": "200.000"}

    payload = {"substance_code": "WHISKY", "superintendent_above_qty": "100"}
    assert draft(client, kind="APPROVAL_THRESHOLD", payload=payload).json()["current"] is None


def test_owner_sees_drafted_by(app_db, client, catalogue, people, otp_outbox):
    login(client, people.superintendent, otp_outbox)
    proposal_id = draft(client).json()["id"]
    login(client, people.owner, otp_outbox)
    seen = client.get(f"/api/rule-changes/{proposal_id}").json()
    assert seen["drafted_by"] == people.superintendent.user_id
    assert (seen["can_withdraw"], seen["can_decide"]) == (False, False)


def test_list_visibility_status_filter_and_order(app_db, catalogue, people, otp_outbox):
    # One client per user: each logs in once (the login throttle allows 10 a minute).
    clients = {}
    for who in ("superintendent", "licensing", "head", "owner", "officer", "licensee"):
        clients[who] = Client()
        login(clients[who], getattr(people, who), otp_outbox)

    own = draft(clients["superintendent"]).json()["id"]
    other = draft(clients["licensing"], payload={**NEW_TYPE, "code": "TODDY_SHOP"}).json()["id"]
    assert post(clients["licensing"], f"/api/rule-changes/{other}/withdraw").status_code == 200

    def ids(who, query=""):
        response = clients[who].get(f"/api/rule-changes{query}")
        assert response.status_code == 200
        return [row["id"] for row in response.json()]

    assert ids("licensing") == [other, own]  # newest first
    assert ids("head") == [other, own]
    assert ids("owner") == [other, own]
    assert ids("superintendent") == [own]
    assert ids("officer") == ids("licensee") == []
    assert ids("head", "?status=SUBMITTED") == [own]
    assert ids("head", "?status=WITHDRAWN") == [other]
    assert ids("head", "?status=") == [other, own]

    unknown = clients["head"].get("/api/rule-changes?status=DONE")
    assert unknown.status_code == 400
    assert unknown.json() == {"detail": "Unknown filter value."}

    assert clients["officer"].get(f"/api/rule-changes/{own}").status_code == 404
    assert clients["officer"].get(f"/api/rule-changes/{own}").json() == NOT_FOUND
    assert clients["superintendent"].get(f"/api/rule-changes/{other}").json() == NOT_FOUND
    assert clients["superintendent"].get("/api/rule-changes/999999").status_code == 404


def test_needs_login(app_db, client):
    assert client.get("/api/rule-changes").status_code == 403
    assert client.get("/api/catalogue/licence-types").status_code == 403


@pytest.mark.parametrize("who", ["officer", "licensee", "owner"])
def test_others_may_not_draft(app_db, client, catalogue, people, otp_outbox, who):
    login(client, getattr(people, who), otp_outbox)
    response = draft(client)
    assert response.status_code == 403
    with acting_as_system("test"):
        assert RuleChangeProposal.objects.count() == 0


def test_personnel_without_district_position_gets_the_fixed_message(
    app_db, client, catalogue, people, otp_outbox
):
    login(client, people.officer, otp_outbox)
    assert draft(client).json() == {
        "detail": (
            "Only the Licensing Authority, a district superintendent or the Head Authority "
            "can draft rule changes."
        )
    }


def test_invalid_payload_and_justification_are_422(app_db, client, catalogue, people, otp_outbox):
    login(client, people.licensing, otp_outbox)
    taken = draft(client, payload={**NEW_TYPE, "code": "RETAIL"})
    assert taken.status_code == 422
    assert taken.json() == {
        "detail": "This rule change can't be saved.",
        "reasons": ["A licence type with code RETAIL already exists."],
    }
    months = draft(client, kind="RULE_VERSION", payload={**RULE, "validity_months": 121})
    assert months.status_code == 422
    assert months.json()["reasons"] == [
        "Validity (months): Ensure this value is less than or equal to 120."
    ]
    short = draft(client, justification="too short")
    assert short.status_code == 422
    assert short.json()["reasons"] == ["Explain the change in 10 to 1000 characters."]
    with acting_as_system("test"):
        assert RuleChangeProposal.objects.count() == 0


def test_unknown_kind_is_400(app_db, client, catalogue, people, otp_outbox):
    login(client, people.licensing, otp_outbox)
    assert draft(client, kind="DELETE_EVERYTHING").status_code == 400


def test_withdraw_over_http(app_db, client, catalogue, people, otp_outbox):
    login(client, people.superintendent, otp_outbox)
    proposal_id = draft(client).json()["id"]

    login(client, people.head, otp_outbox)
    refused = post(client, f"/api/rule-changes/{proposal_id}/withdraw")
    assert refused.status_code == 403
    assert refused.json() == {"detail": "Only the officer who drafted this change can withdraw it."}

    login(client, people.licensing, otp_outbox)
    other = draft(client, payload={**NEW_TYPE, "code": "TODDY_SHOP"}).json()["id"]
    login(client, people.superintendent, otp_outbox)
    assert post(client, f"/api/rule-changes/{other}/withdraw").json() == NOT_FOUND

    withdrawn = post(client, f"/api/rule-changes/{proposal_id}/withdraw")
    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "WITHDRAWN"
    assert withdrawn.json()["decision"]["outcome"] == "WITHDRAWN"
    assert withdrawn.json()["can_withdraw"] is False
    again = post(client, f"/api/rule-changes/{proposal_id}/withdraw")
    assert again.status_code == 409
    assert again.json() == {"detail": "This change has already been decided."}


@pytest.mark.parametrize("who", ["licensing", "superintendent", "owner"])
def test_only_head_may_ask_for_a_decision_code(app_db, client, catalogue, people, otp_outbox, who):
    login(client, people.licensing, otp_outbox)
    proposal_id = draft(client).json()["id"]
    login(client, getattr(people, who), otp_outbox)
    refused = post(client, f"/api/rule-changes/{proposal_id}/decision-code")
    assert refused.status_code == 403
    assert refused.json() == {
        "detail": "Only the Head Authority can approve or reject rule changes."
    }


def test_head_cannot_decide_own_change(app_db, client, catalogue, people, otp_outbox):
    login(client, people.head, otp_outbox)
    own = draft(client).json()
    assert own["can_decide"] is False
    refused = post(client, f"/api/rule-changes/{own['id']}/decision-code")
    assert refused.status_code == 403
    assert refused.json() == {
        "detail": "You drafted this change, so another Head Authority officer must decide it."
    }
    assert client.get("/api/rule-changes/999999/decision-code").status_code == 405
    assert post(client, "/api/rule-changes/999999/decision-code").json() == NOT_FOUND


def test_reject_without_note_is_400_and_keeps_the_code(
    app_db, client, catalogue, people, otp_outbox
):
    login(client, people.licensing, otp_outbox)
    proposal_id = draft(client).json()["id"]
    login(client, people.head, otp_outbox)
    challenge_id, code = code_for(client, proposal_id, otp_outbox)
    url = f"/api/rule-changes/{proposal_id}/decide"
    body = {"challenge_id": challenge_id, "code": code, "outcome": "REJECT"}
    for note in ("", "too short "):
        refused = post(client, url, {**body, "note": note})
        assert refused.status_code == 400
        assert refused.json() == {"note": ["Say why you are rejecting this change."]}
    with acting_as_system("test"):
        assert OtpChallenge.objects.get(public_id=challenge_id).attempts == 0

    rejected = post(client, url, {**body, "note": "Duplicates the existing Retail type."})
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"
    assert rejected.json()["decision"] == {
        "outcome": "REJECTED",
        "decided_at": rejected.json()["decision"]["decided_at"],
        "note": "Duplicates the existing Retail type.",
    }
    assert not LicenceType.objects.filter(code="BEER_BAR").exists()


def test_decide_input_is_validated(app_db, client, catalogue, people, otp_outbox):
    login(client, people.licensing, otp_outbox)
    proposal_id = draft(client).json()["id"]
    login(client, people.head, otp_outbox)
    assert decide(client, proposal_id, otp_outbox, outcome="WITHDRAW").status_code == 400
    assert decide(client, proposal_id, otp_outbox, code="12345").status_code == 400
    assert decide(client, proposal_id, otp_outbox, note="x" * 501).status_code == 400
    assert status_of(proposal_id) == ProposalStatus.SUBMITTED


def test_wrong_code_is_401_and_counts(app_db, client, catalogue, people, otp_outbox):
    login(client, people.licensing, otp_outbox)
    proposal_id = draft(client).json()["id"]
    login(client, people.head, otp_outbox)
    challenge_id, code = code_for(client, proposal_id, otp_outbox)
    wrong = "000000" if code != "000000" else "111111"
    response = post(
        client,
        f"/api/rule-changes/{proposal_id}/decide",
        {"challenge_id": challenge_id, "code": wrong, "outcome": "APPROVE"},
    )
    assert response.status_code == 401
    assert response.json() == WRONG_CODE
    with acting_as_system("test"):
        assert OtpChallenge.objects.get(public_id=challenge_id).attempts == 1
    assert status_of(proposal_id) == ProposalStatus.SUBMITTED


def test_already_decided_is_409(app_db, client, catalogue, people, otp_outbox):
    login(client, people.licensing, otp_outbox)
    proposal_id = draft(client).json()["id"]
    login(client, people.head_b, otp_outbox)
    assert decide(client, proposal_id, otp_outbox).status_code == 200
    login(client, people.head, otp_outbox)
    again = post(client, f"/api/rule-changes/{proposal_id}/decision-code")
    assert again.status_code == 409
    assert again.json() == {"detail": "This change has already been decided."}


def test_code_of_another_user_is_403(app_db, client, catalogue, people, otp_outbox):
    login(client, people.licensing, otp_outbox)
    proposal_id = draft(client).json()["id"]
    login(client, people.head_b, otp_outbox)
    challenge_id, code = code_for(client, proposal_id, otp_outbox)
    login(client, people.head, otp_outbox)
    refused = post(
        client,
        f"/api/rule-changes/{proposal_id}/decide",
        {"challenge_id": challenge_id, "code": code, "outcome": "APPROVE"},
    )
    assert refused.status_code == 403
    assert refused.json() == {"detail": "This code belongs to someone else."}


def test_apply_failure_is_422_and_audited(app_db, client, catalogue, people, otp_outbox):
    login(client, people.licensing, otp_outbox)
    first = draft(client).json()["id"]
    login(client, people.superintendent, otp_outbox)
    second = draft(client).json()["id"]
    login(client, people.head, otp_outbox)
    assert decide(client, first, otp_outbox).status_code == 200
    failed = decide(client, second, otp_outbox)
    assert failed.status_code == 422
    assert failed.json() == {
        "detail": "This rule change can't be saved.",
        "reasons": ["A licence type with code BEER_BAR already exists."],
    }
    assert status_of(second) == ProposalStatus.SUBMITTED
    assert actions()[-1] == "rule_change.apply_failed"  # kept: the view returns, not raises


def test_posts_need_csrf(app_db, catalogue, people, otp_outbox):
    c = Client(enforce_csrf_checks=True)
    token = c.get("/api/auth/csrf").cookies["csrftoken"].value
    first = c.post(
        "/api/auth/login",
        {"user_id": people.licensing.user_id, "password": TEST_PASSWORD},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    c.post(
        "/api/auth/login/verify",
        {"challenge_id": first.json()["challenge_id"], "code": otp_outbox[-1][1]},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    token = c.cookies["csrftoken"].value
    body = {"kind": "NEW_LICENCE_TYPE", "payload": NEW_TYPE, "justification": JUSTIFICATION}
    assert post(c, "/api/rule-changes", body).status_code == 403
    created = c.post(
        "/api/rule-changes", body, content_type="application/json", HTTP_X_CSRFTOKEN=token
    )
    assert created.status_code == 201
    url = f"/api/rule-changes/{created.json()['id']}/withdraw"
    assert post(c, url).status_code == 403
    assert c.post(url, content_type="application/json", HTTP_X_CSRFTOKEN=token).status_code == 200
