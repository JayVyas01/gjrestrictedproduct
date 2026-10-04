"""Draft, withdraw and decide rule-change proposals.

Who may act is checked in plain Python first; writes then run as SYSTEM (the only role
row-level security lets write proposals), and the audit record() is always last. Audit
payloads hold only the proposal id and kind (plus applied_ref on approval), never the
payload values, the justification or the decision note.

Deciding (maker-checker): a Head Authority officer other than the drafter approves or
rejects with a one-time DECISION code. An approval applies the change to the catalogue in
the same SYSTEM block, so it is all or nothing. Lock order: user row -> OTP challenge ->
proposal row -> catalogue row (rule or threshold) -> audit.
"""

from decimal import Decimal

from django.utils import timezone

from audit.service import record
from catalogue.models import LicenceType, LicenceTypeRule, Substance, SubstanceClass
from catalogue.service import (
    LicenceTypeExists,
    add_licence_type,
    add_rule_version,
    add_threshold_version,
)
from core.db_context import acting_as_system
from governance.models import ProposalKind, ProposalStatus, RuleChangeProposal
from governance.payloads import ProposalInvalid, validate_payload
from identity import otp
from identity.models import OtpChallenge, OtpPurpose, User
from identity.roles import Role
from positions.models import AreaLevel, Position

NOT_A_DRAFTER = (
    "Only the Licensing Authority, a district superintendent or the Head Authority "
    "can draft rule changes."
)
ALREADY_DECIDED = "This change has already been decided."
NOT_THE_DRAFTER = "Only the officer who drafted this change can withdraw it."
BAD_JUSTIFICATION = "Explain the change in 10 to 1000 characters."
NOT_HEAD = "Only the Head Authority can approve or reject rule changes."
OWN_CHANGE = "You drafted this change, so another Head Authority officer must decide it."
NOTE_REQUIRED = "Say why you are rejecting this change."
NOTE_TOO_LONG = "Keep the decision note to 500 characters or fewer."
UNKNOWN_OUTCOME = "Approve or reject the change."
SOMEONE_ELSES_CODE = "This code belongs to someone else."

APPROVE = "APPROVE"
REJECT = "REJECT"


class NotAllowed(Exception):
    """A refusal. Each case is its own subclass with a fixed `message`, so the API can answer
    with that constant (and its own status) without ever echoing the exception's text."""

    message = "This action is not allowed."

    def __init__(self):
        super().__init__(self.message)


class ProposalNotFound(NotAllowed):
    message = "Rule change not found."


class NotADrafter(NotAllowed):
    message = NOT_A_DRAFTER


class AlreadyDecided(NotAllowed):
    message = ALREADY_DECIDED


class NotTheDrafter(NotAllowed):
    message = NOT_THE_DRAFTER


class NotHead(NotAllowed):
    message = NOT_HEAD


class OwnChange(NotAllowed):
    message = OWN_CHANGE


class UnknownOutcome(NotAllowed):
    message = UNKNOWN_OUTCOME


class SomeoneElsesCode(NotAllowed):
    message = SOMEONE_ELSES_CODE


def may_draft(user: User) -> bool:
    """The Licensing Authority, the Head Authority, or personnel holding a district position."""
    if user.role in (Role.LICENSING_AUTHORITY, Role.HEAD_AUTHORITY):
        return True
    return (
        user.role == Role.PERSONNEL
        and Position.objects.filter(
            assignments__user=user,
            assignments__ended_at__isnull=True,
            area__level=AreaLevel.DISTRICT,
        ).exists()
    )


def _audit(action: str, proposal: RuleChangeProposal, actor: str, **extra) -> None:
    record(
        action=action,
        actor=actor,
        subject_type="rule_change",
        subject_id=str(proposal.id),
        payload={"proposal_id": proposal.id, "kind": proposal.kind, **extra},
    )


def draft(*, user: User, kind: str, payload: dict, justification: str) -> RuleChangeProposal:
    if not may_draft(user):
        raise NotADrafter()
    cleaned = validate_payload(kind, payload)
    justification = justification.strip()
    if not 10 <= len(justification) <= 1000:
        raise ProposalInvalid([BAD_JUSTIFICATION])
    with acting_as_system("draft_rule_change"):
        proposal = RuleChangeProposal.objects.create(
            kind=kind,
            payload=cleaned,
            justification=justification,
            drafted_by=user.user_id,
            drafted_role=user.role,
        )
        _audit("rule_change.drafted", proposal, user.user_id)
    return proposal


def withdraw(*, proposal_id: int, user: User) -> RuleChangeProposal:
    # Read under the caller's own RLS: None means not found OR not theirs to see.
    proposal = RuleChangeProposal.objects.filter(pk=proposal_id).first()
    if proposal is None:
        raise ProposalNotFound()
    if proposal.drafted_by != user.user_id:
        raise NotTheDrafter()
    with acting_as_system("withdraw_rule_change"):
        locked = RuleChangeProposal.objects.select_for_update().get(pk=proposal.pk)
        if locked.status != ProposalStatus.SUBMITTED:
            raise AlreadyDecided()
        locked.status = ProposalStatus.WITHDRAWN
        locked.decided_by = user.user_id
        locked.decided_at = timezone.now()
        locked.save(update_fields=["status", "decided_by", "decided_at"])
        _audit("rule_change.withdrawn", locked, user.user_id)
    return locked


def _check_decider(proposal: RuleChangeProposal, user: User) -> None:
    if user.role != Role.HEAD_AUTHORITY:
        raise NotHead()
    if proposal.drafted_by == user.user_id:
        raise OwnChange()
    if proposal.status != ProposalStatus.SUBMITTED:
        raise AlreadyDecided()


def _for_decision(proposal_id: int, user: User) -> RuleChangeProposal:
    if user.role != Role.HEAD_AUTHORITY:
        raise NotHead()
    # Read under the caller's own RLS: None means not found OR not theirs to see.
    proposal = RuleChangeProposal.objects.filter(pk=proposal_id).first()
    if proposal is None:
        raise ProposalNotFound()
    _check_decider(proposal, user)
    return proposal


def request_decision_code(*, proposal_id: int, user: User) -> OtpChallenge:
    # The code is bound to its USER, not to one proposal: decide() checks the decider rule
    # again for the proposal it is spent on (before and under the lock).
    _for_decision(proposal_id, user)
    return otp.issue(user, OtpPurpose.DECISION)


def _clean_note(outcome: str, note: str) -> str:
    note = note.strip()
    if outcome == REJECT and len(note) < 10:
        raise ProposalInvalid([NOTE_REQUIRED])
    if len(note) > 500:
        raise ProposalInvalid([NOTE_TOO_LONG])
    return note


def decide(
    *,
    proposal_id: int,
    user: User,
    challenge_id: str,
    code: str,
    outcome: str,
    note: str = "",
) -> RuleChangeProposal | None:
    if outcome not in (APPROVE, REJECT):
        raise UnknownOutcome()
    # Every check that can fail before the code is spent, so a refusal keeps the code usable.
    note = _clean_note(outcome, note)
    proposal = _for_decision(proposal_id, user)
    signer = otp.verify(challenge_id=challenge_id, purpose=OtpPurpose.DECISION, code=code)
    if signer is None:
        return None  # wrong or expired code: the attempt counts, nothing else changes
    if signer.pk != user.pk:
        raise SomeoneElsesCode()
    try:
        with acting_as_system("decide_rule_change"):
            return _decide_locked(proposal.pk, user, outcome, note)
    except ProposalInvalid:
        # The decision and any catalogue rows rolled back with the SYSTEM block's savepoint
        # (the proposal stays SUBMITTED); the failed attempt itself is kept.
        _audit("rule_change.apply_failed", proposal, user.user_id)
        raise


def _decide_locked(pk: int, user: User, outcome: str, note: str) -> RuleChangeProposal:
    locked = RuleChangeProposal.objects.select_for_update().get(pk=pk)
    _check_decider(locked, user)  # it may have been withdrawn or decided since the first check
    if outcome == APPROVE:
        locked.applied_ref = apply_change(locked, by=user.user_id)
        locked.status = ProposalStatus.APPROVED
    else:
        locked.status = ProposalStatus.REJECTED
    locked.decided_by = user.user_id
    locked.decided_at = timezone.now()
    locked.decision_note = note
    locked.save(
        update_fields=["status", "decided_by", "decided_at", "decision_note", "applied_ref"]
    )
    if outcome == APPROVE:
        _audit("rule_change.approved", locked, user.user_id, applied_ref=locked.applied_ref)
    else:
        _audit("rule_change.rejected", locked, user.user_id)
    return locked


def _scope(cleaned: dict) -> dict:
    if cleaned.get("substance_code"):
        return {"substance": Substance.objects.get(code=cleaned["substance_code"])}
    return {"substance_class": SubstanceClass.objects.get(code=cleaned["class_code"])}


def _catalogue_audit(action: str, proposal: RuleChangeProposal, by: str, **ids) -> None:
    record(
        action=action,
        actor=by,
        subject_type="rule_change",
        subject_id=str(proposal.id),
        payload={"proposal_id": proposal.id, **ids},
    )


def apply_change(proposal: RuleChangeProposal, *, by: str) -> str:
    """Apply an approved proposal to the catalogue and return its applied_ref. Must run inside
    the decision's SYSTEM block: re-validates the payload (the catalogue may have changed since
    drafting) and raises ProposalInvalid, which rolls the whole decision back."""
    cleaned = validate_payload(proposal.kind, proposal.payload)
    if proposal.kind == ProposalKind.NEW_LICENCE_TYPE:
        try:
            licence_type = add_licence_type(
                code=cleaned["code"],
                name=cleaned["name"],
                description=cleaned["description"],
                created_by=by,
            )
        except LicenceTypeExists as exists:
            raise ProposalInvalid([str(exists)]) from None
        _catalogue_audit(
            "catalogue.licence_type_added", proposal, by, licence_type_id=licence_type.id
        )
        return f"licence_type:{licence_type.id}"
    if proposal.kind == ProposalKind.RULE_VERSION:
        rule, _ = LicenceTypeRule.objects.get_or_create(
            licence_type=LicenceType.objects.get(code=cleaned["licence_type_code"]),
            **_scope(cleaned),
        )
        version = add_rule_version(
            rule,
            created_by=by,
            may_buy=cleaned["may_buy"],
            may_sell=cleaned["may_sell"],
            may_transport=cleaned["may_transport"],
            max_stock_qty=Decimal(cleaned["max_stock_qty"]),
            max_per_transaction_qty=Decimal(cleaned["max_per_transaction_qty"]),
            validity_months=cleaned["validity_months"],
        )
        _catalogue_audit("catalogue.rule_version_added", proposal, by, rule_version_id=version.id)
        return f"rule_version:{version.id}"
    version = add_threshold_version(
        **_scope(cleaned),
        superintendent_above_qty=Decimal(cleaned["superintendent_above_qty"]),
        created_by=by,
    )
    _catalogue_audit(
        "catalogue.threshold_version_added", proposal, by, threshold_version_id=version.id
    )
    return f"threshold_version:{version.id}"
