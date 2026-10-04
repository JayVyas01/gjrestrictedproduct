"""What a viewer sees of a rule-change proposal.

`proposed` is the cleaned payload with display names resolved; `current` is what the catalogue
holds today for the same scope (the latest rule version for the licence type and scope, or the
latest threshold for the scope), or null, which drives the before/after view. Catalogue tables
have no row-level security, so they are read as the viewer.

Ruling D-R2: the drafter's user id is shown only to Head Authority and Software Owner viewers;
everyone else sees the drafter's role.
"""

from catalogue.models import (
    ApprovalThreshold,
    LicenceType,
    LicenceTypeRule,
    Substance,
    SubstanceClass,
)
from catalogue.service import class_unit, latest_rule_version, latest_threshold
from governance.models import ProposalKind, ProposalStatus, RuleChangeProposal
from identity.models import User
from identity.roles import Role

_SEE_DRAFTER_ID = {Role.HEAD_AUTHORITY, Role.SOFTWARE_OWNER}


def _scope(payload: dict) -> tuple[dict, dict | None]:
    """The display fields of a payload's scope, and the filter that finds its catalogue rows
    (None when the substance or class no longer exists)."""
    if payload.get("substance_code"):
        substance = Substance.objects.filter(code=payload["substance_code"]).first()
        display = {
            "scope": substance and substance.name,
            "scope_kind": "substance",
            "unit": substance and substance.unit,
        }
        return display, substance and {"substance": substance}
    substance_class = SubstanceClass.objects.filter(code=payload.get("class_code")).first()
    display = {
        "scope": substance_class and substance_class.name,
        "scope_kind": "class",
        "unit": substance_class and class_unit(substance_class),
    }
    return display, substance_class and {"substance_class": substance_class}


def _rule_version(payload: dict, where: dict | None) -> tuple[dict, dict | None]:
    licence_type = LicenceType.objects.filter(code=payload["licence_type_code"]).first()
    names = {"licence_type_name": licence_type and licence_type.name}
    if licence_type is None or where is None:
        return names, None
    rule = LicenceTypeRule.objects.filter(licence_type=licence_type, **where).first()
    latest = latest_rule_version(rule)
    if latest is None:
        return names, None
    return names, {
        "version": latest.version,
        "may_buy": latest.may_buy,
        "may_sell": latest.may_sell,
        "may_transport": latest.may_transport,
        "max_stock_qty": str(latest.max_stock_qty),
        "max_per_transaction_qty": str(latest.max_per_transaction_qty),
        "validity_months": latest.validity_months,
    }


def _threshold(where: dict | None) -> dict | None:
    if where is None:
        return None
    latest = latest_threshold(ApprovalThreshold.objects.filter(**where).first())
    if latest is None:
        return None
    return {
        "version": latest.version,
        "superintendent_above_qty": str(latest.superintendent_above_qty),
    }


def _proposed_and_current(p: RuleChangeProposal) -> tuple[dict, dict | None]:
    payload = dict(p.payload)
    if p.kind == ProposalKind.NEW_LICENCE_TYPE:
        return payload, None
    display, where = _scope(payload)
    if p.kind == ProposalKind.RULE_VERSION:
        names, current = _rule_version(payload, where)
        return {**payload, **names, **display}, current
    return {**payload, **display}, _threshold(where)


def proposal_view(p: RuleChangeProposal, viewer: User) -> dict:
    proposed, current = _proposed_and_current(p)
    submitted = p.status == ProposalStatus.SUBMITTED
    if not submitted:
        # Once decided, the live catalogue no longer is "what this would replace".
        current = None
    view = {
        "id": p.id,
        "kind": p.kind,
        "kind_label": p.get_kind_display(),
        "status": p.status,
        "status_label": p.get_status_display(),
        "justification": p.justification,
        "drafted_at": p.drafted_at.isoformat(),
        "drafted_by_role": Role(p.drafted_role).label,
        "proposed": proposed,
        "current": current,
        "decision": None
        if submitted
        else {
            "outcome": p.status,
            "decided_at": p.decided_at.isoformat() if p.decided_at else None,
            "note": p.decision_note or None,
        },
        "can_withdraw": submitted and p.drafted_by == viewer.user_id,
        "can_decide": submitted
        and viewer.role == Role.HEAD_AUTHORITY
        and p.drafted_by != viewer.user_id,
    }
    if viewer.role in _SEE_DRAFTER_ID:
        view["drafted_by"] = p.drafted_by
    return view
