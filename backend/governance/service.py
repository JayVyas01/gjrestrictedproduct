"""Draft and withdraw rule-change proposals.

Who may act is checked in plain Python first; writes then run as SYSTEM (the only role
row-level security lets write proposals), and the audit record() is always last. Audit
payloads hold only the proposal id and kind, never the payload values or the justification.
"""

from django.utils import timezone

from audit.service import record
from core.db_context import acting_as_system
from governance.models import ProposalStatus, RuleChangeProposal
from governance.payloads import ProposalInvalid, validate_payload
from identity.models import User
from identity.roles import Role
from positions.models import AreaLevel, Position

NOT_A_DRAFTER = (
    "Only the Licensing Authority, a district superintendent or the Head Authority "
    "can draft rule changes."
)
ALREADY_DECIDED = "This change has already been decided."
NOT_THE_DRAFTER = "Only the officer who drafted this change can withdraw it."
BAD_JUSTIFICATION = "Explain the change in 10 to 1000 characters."


class NotAllowed(Exception):
    pass


class ProposalNotFound(NotAllowed):
    def __init__(self):
        super().__init__("Rule change not found.")


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


def _audit(action: str, proposal: RuleChangeProposal, actor: str) -> None:
    record(
        action=action,
        actor=actor,
        subject_type="rule_change",
        subject_id=str(proposal.id),
        payload={"proposal_id": proposal.id, "kind": proposal.kind},
    )


def draft(*, user: User, kind: str, payload: dict, justification: str) -> RuleChangeProposal:
    if not may_draft(user):
        raise NotAllowed(NOT_A_DRAFTER)
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
        raise NotAllowed(NOT_THE_DRAFTER)
    with acting_as_system("withdraw_rule_change"):
        locked = RuleChangeProposal.objects.select_for_update().get(pk=proposal.pk)
        if locked.status != ProposalStatus.SUBMITTED:
            raise NotAllowed(ALREADY_DECIDED)
        locked.status = ProposalStatus.WITHDRAWN
        locked.decided_by = user.user_id
        locked.decided_at = timezone.now()
        locked.save(update_fields=["status", "decided_by", "decided_at"])
        _audit("rule_change.withdrawn", locked, user.user_id)
    return locked
