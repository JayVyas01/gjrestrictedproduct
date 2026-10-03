from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.db import transaction

from audit.models import AuditEvent
from catalogue.models import (
    ApprovalThreshold,
    LicenceType,
    LicenceTypeRule,
    LicenceTypeRuleVersion,
)
from core.db_context import SYSTEM_ROLE, acting_as_system, set_actor
from governance.models import ProposalStatus, RuleChangeProposal
from governance.payloads import ProposalInvalid
from governance.service import NotAllowed, decide, draft, request_decision_code
from identity.roles import Role
from licensing.models import LicencePermissionsSnapshot
from positions.service import assign
from tests.conftest import BUYER_GSTIN, TEST_TRANSPORT
from transactions.service import start_transaction

pytestmark = pytest.mark.django_db

JUSTIFICATION = "Retail outlets now stock beer in larger volumes."
OWN = "You drafted this change, so another Head Authority officer must decide it."
NOT_HEAD = "Only the Head Authority can approve or reject rule changes."
DECIDED = "This change has already been decided."
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


@pytest.fixture
def people(org, make_user):
    superintendent = make_user(role=Role.PERSONNEL, contact="+919800000603")
    assign(org.district_officer, superintendent, by="test")
    return SimpleNamespace(
        licensing=make_user(role=Role.LICENSING_AUTHORITY, contact="+919800000601"),
        head=make_user(role=Role.HEAD_AUTHORITY, contact="+919800000602"),
        head_b=make_user(role=Role.HEAD_AUTHORITY, contact="+919800000604"),
        superintendent=superintendent,
        owner=make_user(role=Role.SOFTWARE_OWNER, contact="+919800000605"),
    )


def act(user):
    set_actor(user_id=user.user_id, role=user.role)


def draft_as(user, kind="NEW_LICENCE_TYPE", payload=None):
    act(user)
    return draft(
        user=user, kind=kind, payload=payload or dict(NEW_TYPE), justification=JUSTIFICATION
    )


def code_for(user, proposal, otp_outbox):
    act(user)
    challenge = request_decision_code(proposal_id=proposal.id, user=user)
    return str(challenge.public_id), otp_outbox[-1][1]


def sign(user, proposal, otp_outbox, outcome="APPROVE", note=""):
    challenge_id, code = code_for(user, proposal, otp_outbox)
    act(user)
    return decide(
        proposal_id=proposal.id,
        user=user,
        challenge_id=challenge_id,
        code=code,
        outcome=outcome,
        note=note,
    )


def reload(proposal):
    with acting_as_system("test"):
        return RuleChangeProposal.objects.get(pk=proposal.pk)


def events():
    with transaction.atomic():
        set_actor(user_id="test", role=SYSTEM_ROLE)
        return list(AuditEvent.objects.order_by("id"))


def test_approve_new_licence_type_applies_it(app_db, catalogue, people, otp_outbox):
    proposal = draft_as(people.licensing)
    decided = sign(people.head, proposal, otp_outbox, note="Agreed with the district.")
    new_type = LicenceType.objects.get(code="BEER_BAR")
    assert (new_type.name, new_type.description) == ("Beer bar", "On-premises beer")
    assert decided.status == ProposalStatus.APPROVED
    assert decided.decided_by == people.head.user_id
    assert decided.decided_at is not None
    assert decided.decision_note == "Agreed with the district."
    assert decided.applied_ref == f"licence_type:{new_type.id}"
    assert reload(proposal).status == ProposalStatus.APPROVED


def test_approve_rule_version_creates_rule_if_missing_and_versions_existing(
    app_db, catalogue, people, otp_outbox
):
    existing = draft_as(people.licensing, kind="RULE_VERSION", payload=dict(RULE))
    decided = sign(people.head, existing, otp_outbox)
    latest = catalogue.retail_rule.versions.order_by("-version").first()
    assert latest.version == 2
    assert (latest.may_sell, latest.max_stock_qty, latest.validity_months) == (
        False,
        Decimal("2000"),
        24,
    )
    assert latest.created_by == people.head.user_id
    assert decided.applied_ref == f"rule_version:{latest.id}"

    rum_rule = {k: v for k, v in RULE.items() if k != "class_code"}
    missing = draft_as(
        people.superintendent, kind="RULE_VERSION", payload={**rum_rule, "substance_code": "RUM"}
    )
    decided = sign(people.head, missing, otp_outbox)
    rule = LicenceTypeRule.objects.get(licence_type=catalogue.retail, substance=catalogue.rum)
    version = rule.versions.get()
    assert version.version == 1
    assert decided.applied_ref == f"rule_version:{version.id}"


def test_approve_threshold_changes_new_transactions_only(
    app_db, catalogue, trade, threshold, people, otp_outbox
):
    def start():
        act(trade.seller)
        return start_transaction(
            seller=trade.seller,
            buyer_gstin=BUYER_GSTIN,
            substance=catalogue.whisky,
            quantity=Decimal("300"),
            transport=TEST_TRANSPORT,
        )

    in_flight = start()
    assert in_flight.approval_chain == "OFFICER_THEN_SUPERINTENDENT"
    proposal = draft_as(
        people.licensing,
        kind="APPROVAL_THRESHOLD",
        payload={"class_code": "SPIRITS", "superintendent_above_qty": "500"},
    )
    decided = sign(people.head, proposal, otp_outbox)
    latest = ApprovalThreshold.objects.get(substance_class=catalogue.spirits).versions.order_by(
        "-version"
    )[0]
    assert (latest.version, latest.superintendent_above_qty) == (2, Decimal("500"))
    assert decided.applied_ref == f"threshold_version:{latest.id}"

    with acting_as_system("test"):
        in_flight.refresh_from_db()
    assert in_flight.approval_chain == "OFFICER_THEN_SUPERINTENDENT"
    assert start().approval_chain == "OFFICER"


def test_existing_licence_permissions_unchanged_after_rule_change(
    app_db, catalogue, make_licence, people, otp_outbox
):
    licence = make_licence()
    with acting_as_system("test"):
        before = list(
            LicencePermissionsSnapshot.objects.filter(licence=licence).values(
                "rule_version", "may_sell", "max_stock_qty", "max_per_transaction_qty"
            )
        )
    proposal = draft_as(people.licensing, kind="RULE_VERSION", payload=dict(RULE))
    sign(people.head, proposal, otp_outbox)
    with acting_as_system("test"):
        after = list(
            LicencePermissionsSnapshot.objects.filter(licence=licence).values(
                "rule_version", "may_sell", "max_stock_qty", "max_per_transaction_qty"
            )
        )
    assert after == before
    assert before[0]["may_sell"] is True


@pytest.mark.parametrize("note", ["", "too short "])
def test_reject_needs_note_and_changes_nothing(app_db, catalogue, people, otp_outbox, note):
    proposal = draft_as(people.licensing)
    challenge_id, code = code_for(people.head, proposal, otp_outbox)
    act(people.head)
    with pytest.raises(ProposalInvalid) as invalid:
        decide(
            proposal_id=proposal.id,
            user=people.head,
            challenge_id=challenge_id,
            code=code,
            outcome="REJECT",
            note=note,
        )
    assert invalid.value.reasons == ["Say why you are rejecting this change."]
    assert reload(proposal).status == ProposalStatus.SUBMITTED

    # The code was not spent on the refused attempt: it still signs the rejection.
    act(people.head)
    rejected = decide(
        proposal_id=proposal.id,
        user=people.head,
        challenge_id=challenge_id,
        code=code,
        outcome="REJECT",
        note="  Duplicates the existing Retail type.  ",
    )
    assert rejected.status == ProposalStatus.REJECTED
    assert rejected.decision_note == "Duplicates the existing Retail type."
    assert rejected.applied_ref == ""
    assert not LicenceType.objects.filter(code="BEER_BAR").exists()
    assert events()[-1].action == "rule_change.rejected"
    assert events()[-1].payload == {"proposal_id": proposal.id, "kind": "NEW_LICENCE_TYPE"}


def test_drafter_cannot_decide_own_change(app_db, catalogue, people, otp_outbox):
    own = draft_as(people.head)
    act(people.head)
    with pytest.raises(NotAllowed) as refused:
        request_decision_code(proposal_id=own.id, user=people.head)
    assert str(refused.value) == OWN

    # A valid code obtained on someone else's proposal does not sign the drafter's own.
    other = draft_as(people.licensing, payload={**NEW_TYPE, "code": "TODDY_SHOP"})
    challenge_id, code = code_for(people.head, other, otp_outbox)
    act(people.head)
    with pytest.raises(NotAllowed) as refused:
        decide(
            proposal_id=own.id,
            user=people.head,
            challenge_id=challenge_id,
            code=code,
            outcome="APPROVE",
        )
    assert str(refused.value) == OWN
    assert reload(own).status == ProposalStatus.SUBMITTED
    assert not LicenceType.objects.filter(code="BEER_BAR").exists()
    # ...and the code was not spent: it still decides the proposal it was asked for.
    act(people.head)
    assert (
        decide(
            proposal_id=other.id,
            user=people.head,
            challenge_id=challenge_id,
            code=code,
            outcome="APPROVE",
        ).status
        == ProposalStatus.APPROVED
    )

    # Another Head Authority officer may decide it.
    assert sign(people.head_b, own, otp_outbox).status == ProposalStatus.APPROVED


def test_drafter_is_refused_under_the_lock(app_db, catalogue, people, otp_outbox, monkeypatch):
    """Even if the first check were bypassed, the re-check under the lock refuses the drafter."""
    import governance.service as service

    own = draft_as(people.head)
    other = draft_as(people.licensing, payload={**NEW_TYPE, "code": "TODDY_SHOP"})
    challenge_id, code = code_for(people.head, other, otp_outbox)
    monkeypatch.setattr(
        service,
        "_for_decision",
        lambda proposal_id, user: RuleChangeProposal.objects.get(pk=proposal_id),
    )
    act(people.head)
    with pytest.raises(NotAllowed) as refused:
        decide(
            proposal_id=own.id,
            user=people.head,
            challenge_id=challenge_id,
            code=code,
            outcome="APPROVE",
        )
    assert str(refused.value) == OWN
    assert reload(own).status == ProposalStatus.SUBMITTED


@pytest.mark.parametrize("who", ["licensing", "superintendent", "owner"])
def test_only_head_can_decide(app_db, catalogue, people, otp_outbox, who):
    proposal = draft_as(people.superintendent)
    user = getattr(people, who)
    act(user)
    with pytest.raises(NotAllowed) as refused:
        request_decision_code(proposal_id=proposal.id, user=user)
    assert str(refused.value) == NOT_HEAD
    act(user)
    with pytest.raises(NotAllowed) as refused:
        decide(
            proposal_id=proposal.id,
            user=user,
            challenge_id="00000000-0000-0000-0000-000000000000",
            code="000000",
            outcome="APPROVE",
        )
    assert str(refused.value) == NOT_HEAD


def test_unknown_outcome_is_refused(app_db, catalogue, people, otp_outbox):
    proposal = draft_as(people.licensing)
    challenge_id, code = code_for(people.head, proposal, otp_outbox)
    act(people.head)
    with pytest.raises(NotAllowed):
        decide(
            proposal_id=proposal.id,
            user=people.head,
            challenge_id=challenge_id,
            code=code,
            outcome="WITHDRAW",
        )


def test_code_of_another_user_is_refused(app_db, catalogue, people, otp_outbox):
    proposal = draft_as(people.licensing)
    challenge_id, code = code_for(people.head_b, proposal, otp_outbox)
    act(people.head)
    with pytest.raises(NotAllowed, match="someone else"):
        decide(
            proposal_id=proposal.id,
            user=people.head,
            challenge_id=challenge_id,
            code=code,
            outcome="APPROVE",
        )
    assert reload(proposal).status == ProposalStatus.SUBMITTED


def test_wrong_code_counts_and_changes_nothing(app_db, catalogue, people, otp_outbox):
    from identity.models import OtpChallenge

    proposal = draft_as(people.licensing)
    challenge_id, code = code_for(people.head, proposal, otp_outbox)
    wrong = "000000" if code != "000000" else "111111"
    act(people.head)
    assert (
        decide(
            proposal_id=proposal.id,
            user=people.head,
            challenge_id=challenge_id,
            code=wrong,
            outcome="APPROVE",
        )
        is None
    )
    with acting_as_system("test"):
        assert OtpChallenge.objects.get(public_id=challenge_id).attempts == 1
    assert reload(proposal).status == ProposalStatus.SUBMITTED
    assert not LicenceType.objects.filter(code="BEER_BAR").exists()


def test_apply_failure_rolls_back_and_is_audited(app_db, catalogue, people, otp_outbox):
    first = draft_as(people.licensing)
    second = draft_as(people.superintendent)
    sign(people.head, first, otp_outbox)
    types_before = LicenceType.objects.count()
    events_before = len(events())

    with pytest.raises(ProposalInvalid) as invalid:
        sign(people.head, second, otp_outbox)
    assert invalid.value.reasons == ["A licence type with code BEER_BAR already exists."]
    assert LicenceType.objects.count() == types_before
    after = reload(second)
    assert (after.status, after.decided_by, after.applied_ref) == (ProposalStatus.SUBMITTED, "", "")
    new_events = events()[events_before:]
    assert [e.action for e in new_events] == ["rule_change.apply_failed"]
    assert new_events[0].actor == people.head.user_id
    assert new_events[0].payload == {"proposal_id": second.id, "kind": "NEW_LICENCE_TYPE"}


def test_rule_version_apply_failure_leaves_no_rule(app_db, catalogue, people, otp_outbox):
    rum_rule = {k: v for k, v in RULE.items() if k != "class_code"}
    proposal = draft_as(
        people.licensing, kind="RULE_VERSION", payload={**rum_rule, "substance_code": "RUM"}
    )
    rules_before = LicenceTypeRule.objects.count()
    versions_before = LicenceTypeRuleVersion.objects.count()
    # The catalogue changed after drafting: the licence type was recoded.
    LicenceType.objects.filter(code="RETAIL").update(code="RETAIL_OLD")
    with pytest.raises(ProposalInvalid) as invalid:
        sign(people.head, proposal, otp_outbox)
    assert invalid.value.reasons == ["No licence type has code RETAIL."]
    assert LicenceTypeRule.objects.count() == rules_before
    assert LicenceTypeRuleVersion.objects.count() == versions_before
    assert reload(proposal).status == ProposalStatus.SUBMITTED


def test_already_decided_is_refused(app_db, catalogue, people, otp_outbox):
    proposal = draft_as(people.licensing)
    challenge_id, code = code_for(people.head, proposal, otp_outbox)
    sign(people.head_b, proposal, otp_outbox, outcome="REJECT", note="Not needed this year.")
    act(people.head)
    with pytest.raises(NotAllowed) as refused:
        request_decision_code(proposal_id=proposal.id, user=people.head)
    assert str(refused.value) == DECIDED
    act(people.head)
    with pytest.raises(NotAllowed) as refused:
        decide(
            proposal_id=proposal.id,
            user=people.head,
            challenge_id=challenge_id,
            code=code,
            outcome="APPROVE",
        )
    assert str(refused.value) == DECIDED
    assert reload(proposal).status == ProposalStatus.REJECTED


def test_decision_on_invisible_or_missing_proposal_is_not_found(app_db, catalogue, people):
    act(people.head)
    with pytest.raises(NotAllowed, match="not found"):
        request_decision_code(proposal_id=999999, user=people.head)


@pytest.mark.parametrize(
    "kind, payload, catalogue_action, id_key",
    [
        ("NEW_LICENCE_TYPE", NEW_TYPE, "catalogue.licence_type_added", "licence_type_id"),
        ("RULE_VERSION", RULE, "catalogue.rule_version_added", "rule_version_id"),
        (
            "APPROVAL_THRESHOLD",
            {"class_code": "SPIRITS", "superintendent_above_qty": "500"},
            "catalogue.threshold_version_added",
            "threshold_version_id",
        ),
    ],
)
def test_audit_order_catalogue_then_rule_change_approved_last(
    app_db, catalogue, people, otp_outbox, kind, payload, catalogue_action, id_key
):
    proposal = draft_as(people.licensing, kind=kind, payload=dict(payload))
    decided = sign(people.head, proposal, otp_outbox)
    *_, catalogue_event, approved = events()
    applied_id = int(decided.applied_ref.split(":")[1])
    assert catalogue_event.action == catalogue_action
    assert catalogue_event.actor == people.head.user_id
    assert catalogue_event.payload == {"proposal_id": proposal.id, id_key: applied_id}
    assert approved.action == "rule_change.approved"
    assert approved.actor == people.head.user_id
    assert (approved.subject_type, approved.subject_id) == ("rule_change", str(proposal.id))
    assert approved.payload == {
        "proposal_id": proposal.id,
        "kind": kind,
        "applied_ref": decided.applied_ref,
    }


def test_duplicate_type_code_at_insert_is_refused_with_the_exact_message(
    app_db, catalogue, people, otp_outbox, monkeypatch
):
    """A code taken after re-validation (a concurrent approval) is refused by
    catalogue.add_licence_type and becomes ProposalInvalid with the same message."""
    import governance.service as service

    proposal = draft_as(people.licensing, payload={**NEW_TYPE, "code": "RETAIL_TWO"})
    LicenceType.objects.filter(code="WHOLESALE").update(code="RETAIL_TWO")
    monkeypatch.setattr(service, "validate_payload", lambda kind, payload: dict(payload))
    with pytest.raises(ProposalInvalid) as invalid:
        sign(people.head, proposal, otp_outbox)
    assert invalid.value.reasons == ["A licence type with code RETAIL_TWO already exists."]
    assert reload(proposal).status == ProposalStatus.SUBMITTED
    assert events()[-1].action == "rule_change.apply_failed"
