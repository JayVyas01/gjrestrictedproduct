from types import SimpleNamespace

import pytest
from django.db import DatabaseError, transaction
from django.utils import timezone

from audit.models import AuditEvent
from core.db_context import SYSTEM_ROLE, acting_as_system, set_actor
from governance.models import ProposalStatus, RuleChangeProposal
from governance.payloads import ProposalInvalid, validate_payload
from governance.service import NotAllowed, draft, may_draft, withdraw
from identity.roles import Role
from positions.service import assign

pytestmark = pytest.mark.django_db

NOT_A_DRAFTER = (
    "Only the Licensing Authority, a district superintendent or the Head Authority "
    "can draft rule changes."
)
JUSTIFICATION = "Retail outlets now stock beer in larger volumes."
NEW_TYPE = {"code": "BEER_BAR", "name": "Beer bar", "description": "On-premises beer"}
RULE = {
    "licence_type_code": "RETAIL",
    "class_code": "SPIRITS",
    "may_buy": True,
    "may_sell": True,
    "may_transport": False,
    "max_stock_qty": "2000",
    "max_per_transaction_qty": "500.5",
    "validity_months": 12,
}


@pytest.fixture
def people(org, make_user):
    licensing = make_user(role=Role.LICENSING_AUTHORITY, contact="+919800000501")
    head = make_user(role=Role.HEAD_AUTHORITY, contact="+919800000502")
    superintendent = make_user(role=Role.PERSONNEL, contact="+919800000503")
    officer = make_user(role=Role.PERSONNEL, contact="+919800000504")
    assign(org.district_officer, superintendent, by="test")
    assign(org.area_officer, officer, by="test")
    return SimpleNamespace(
        licensing=licensing,
        head=head,
        superintendent=superintendent,
        officer=officer,
        licensee=make_user(role=Role.LICENSEE, contact="+919800000505"),
        owner=make_user(role=Role.SOFTWARE_OWNER, contact="+919800000506"),
    )


def act(user):
    set_actor(user_id=user.user_id, role=user.role)


def draft_as(user, kind="NEW_LICENCE_TYPE", payload=None, justification=JUSTIFICATION):
    act(user)
    return draft(
        user=user, kind=kind, payload=payload or dict(NEW_TYPE), justification=justification
    )


def visible(user):
    with transaction.atomic():
        act(user)
        return list(RuleChangeProposal.objects.order_by("id"))


def last_event():
    with transaction.atomic():
        set_actor(user_id="test", role=SYSTEM_ROLE)
        return AuditEvent.objects.order_by("-id").first()


@pytest.mark.parametrize("who", ["licensing", "head", "superintendent"])
def test_licensing_authority_head_and_district_superintendent_may_draft(
    app_db, catalogue, people, who
):
    user = getattr(people, who)
    assert may_draft(user)
    proposal = draft_as(user)
    assert proposal.status == ProposalStatus.SUBMITTED
    assert proposal.drafted_by == user.user_id
    assert proposal.drafted_role == user.role
    assert proposal.payload == NEW_TYPE


@pytest.mark.parametrize("who", ["officer", "licensee", "owner"])
def test_others_may_not_draft(app_db, catalogue, people, who):
    user = getattr(people, who)
    assert not may_draft(user)
    with pytest.raises(NotAllowed) as refused:
        draft_as(user)
    assert str(refused.value) == NOT_A_DRAFTER
    with acting_as_system("test"):
        assert RuleChangeProposal.objects.count() == 0


def reasons_for(kind, payload):
    with pytest.raises(ProposalInvalid) as invalid:
        validate_payload(kind, payload)
    return invalid.value.reasons


def test_payload_validation_messages(app_db, catalogue):
    assert reasons_for("NEW_LICENCE_TYPE", {**NEW_TYPE, "code": "RETAIL"}) == [
        "A licence type with code RETAIL already exists."
    ]
    assert reasons_for("RULE_VERSION", {**RULE, "licence_type_code": "NOPE"}) == [
        "No licence type has code NOPE."
    ]
    assert reasons_for("RULE_VERSION", {**RULE, "class_code": "NOPE"}) == [
        "No substance class has code NOPE."
    ]
    rule_for_substance = {k: v for k, v in RULE.items() if k != "class_code"}
    assert reasons_for("RULE_VERSION", {**rule_for_substance, "substance_code": "NOPE"}) == [
        "No substance has code NOPE."
    ]
    assert reasons_for("RULE_VERSION", {**RULE, "max_per_transaction_qty": "2000.001"}) == [
        "The per-transaction limit can't be above the stock limit."
    ]
    both = {"substance_code": "WHISKY", "class_code": "SPIRITS", "superintendent_above_qty": "5"}
    assert reasons_for("APPROVAL_THRESHOLD", both) == [
        "Choose either a substance or a substance class."
    ]
    assert reasons_for("APPROVAL_THRESHOLD", {"superintendent_above_qty": "5"}) == [
        "Choose either a substance or a substance class."
    ]
    assert reasons_for("NO_SUCH_KIND", {}) == ["Unknown kind of rule change."]


def test_payload_field_rules(app_db, catalogue):
    assert reasons_for("NEW_LICENCE_TYPE", {**NEW_TYPE, "code": "beer"})
    assert reasons_for("NEW_LICENCE_TYPE", {**NEW_TYPE, "name": "x" * 101})
    assert reasons_for("RULE_VERSION", {**RULE, "max_stock_qty": "0"})
    assert reasons_for("RULE_VERSION", {**RULE, "validity_months": 121})
    assert reasons_for("APPROVAL_THRESHOLD", {"class_code": "SPIRITS"})
    assert reasons_for("RULE_VERSION", "not an object")


def test_payload_is_cleaned(app_db, catalogue):
    assert validate_payload("NEW_LICENCE_TYPE", {"code": "BEER_BAR", "name": " Beer bar "}) == {
        "code": "BEER_BAR",
        "name": "Beer bar",
        "description": "",
    }
    assert validate_payload("RULE_VERSION", {**RULE, "max_stock_qty": 2000, "extra": 1}) == {
        **RULE,
        "max_stock_qty": "2000.000",
        "max_per_transaction_qty": "500.500",
    }
    assert validate_payload(
        "APPROVAL_THRESHOLD", {"substance_code": "WHISKY", "superintendent_above_qty": "150"}
    ) == {"substance_code": "WHISKY", "superintendent_above_qty": "150.000"}


def test_invalid_payload_is_not_drafted(app_db, catalogue, people):
    with pytest.raises(ProposalInvalid):
        draft_as(people.licensing, payload={**NEW_TYPE, "code": "RETAIL"})
    with acting_as_system("test"):
        assert RuleChangeProposal.objects.count() == 0


@pytest.mark.parametrize("justification", ["", "too short ", "x" * 1001])
def test_justification_required(app_db, catalogue, people, justification):
    with pytest.raises(ProposalInvalid) as invalid:
        draft_as(people.licensing, justification=justification)
    assert invalid.value.reasons == ["Explain the change in 10 to 1000 characters."]


def test_justification_limits_are_inclusive(app_db, catalogue, people):
    draft_as(people.licensing, justification="x" * 10)
    draft_as(people.licensing, justification="x" * 1000)


def test_draft_is_audited_without_payload_values(app_db, catalogue, people):
    proposal = draft_as(people.licensing, kind="RULE_VERSION", payload=dict(RULE))
    event = last_event()
    assert event.action == "rule_change.drafted"
    assert event.actor == people.licensing.user_id
    assert (event.subject_type, event.subject_id) == ("rule_change", str(proposal.id))
    assert event.payload == {"proposal_id": proposal.id, "kind": "RULE_VERSION"}


def test_withdraw_rules(app_db, catalogue, people):
    proposal = draft_as(people.superintendent)
    act(people.head)
    with pytest.raises(NotAllowed) as refused:
        withdraw(proposal_id=proposal.id, user=people.head)
    assert str(refused.value) == "Only the officer who drafted this change can withdraw it."

    act(people.superintendent)
    withdrawn = withdraw(proposal_id=proposal.id, user=people.superintendent)
    assert withdrawn.status == ProposalStatus.WITHDRAWN
    assert withdrawn.decided_by == people.superintendent.user_id
    assert withdrawn.decided_at is not None
    event = last_event()
    assert event.action == "rule_change.withdrawn"
    assert event.payload == {"proposal_id": proposal.id, "kind": "NEW_LICENCE_TYPE"}

    act(people.superintendent)
    with pytest.raises(NotAllowed) as refused:
        withdraw(proposal_id=proposal.id, user=people.superintendent)
    assert str(refused.value) == "This change has already been decided."


def test_withdraw_an_invisible_proposal_is_not_found(app_db, catalogue, people):
    proposal = draft_as(people.licensing)
    act(people.superintendent)
    with pytest.raises(NotAllowed) as refused:
        withdraw(proposal_id=proposal.id, user=people.superintendent)
    assert str(refused.value) == "Rule change not found."
    act(people.superintendent)
    with pytest.raises(NotAllowed, match="not found"):
        withdraw(proposal_id=999999, user=people.superintendent)


def test_visibility(app_db, catalogue, people, make_user):
    own = draft_as(people.superintendent)
    other = draft_as(people.licensing)
    assert visible(people.superintendent) == [own]
    assert visible(people.licensing) == [own, other]
    assert visible(people.head) == [own, other]
    assert visible(people.owner) == [own, other]
    assert visible(people.licensee) == visible(people.officer) == []


def test_only_system_writes_proposals(app_db, catalogue, people):
    act(people.licensing)
    with pytest.raises(DatabaseError, match="row-level security"):
        with transaction.atomic():
            RuleChangeProposal.objects.create(
                kind="NEW_LICENCE_TYPE",
                payload=NEW_TYPE,
                justification=JUSTIFICATION,
                drafted_by=people.licensing.user_id,
                drafted_role=people.licensing.role,
            )


def test_decided_proposal_cannot_change_even_for_owner(db, catalogue, people):
    proposal = draft_as(people.licensing)
    rows = RuleChangeProposal.objects.filter(pk=proposal.pk)
    rows.update(status=ProposalStatus.APPROVED, decided_at=timezone.now())
    for change in ({"decision_note": "edited"}, {"status": ProposalStatus.SUBMITTED}):
        with pytest.raises(DatabaseError, match="already been decided"):
            with transaction.atomic():
                rows.update(**change)


def test_app_role_can_update_only_decision_columns(app_db, catalogue, people):
    proposal = draft_as(people.licensing)
    with acting_as_system("test"):
        rows = RuleChangeProposal.objects.filter(pk=proposal.pk)
        with pytest.raises(DatabaseError, match="permission denied"):
            with transaction.atomic():
                rows.update(payload={"code": "OTHER"})
        rows.update(decision_note="Checked with the district.", applied_ref="x")


def test_proposals_cannot_be_deleted(app_db, catalogue, people):
    proposal = draft_as(people.licensing)
    with acting_as_system("test"):
        with pytest.raises(DatabaseError, match="permission denied"):
            with transaction.atomic():
                RuleChangeProposal.objects.filter(pk=proposal.pk).delete()


def test_proposals_cannot_be_deleted_even_for_owner(db, catalogue, people):
    draft_as(people.licensing)
    with pytest.raises(DatabaseError, match="append-only"):
        with transaction.atomic():
            RuleChangeProposal.objects.all().delete()
