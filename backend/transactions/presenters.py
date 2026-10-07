"""What each viewer sees of a transaction. Party names are read as SYSTEM (the other party's
licence is hidden from the viewer by RLS) and only the registered name is shown. The buyer's
and officer's free-text comments, and who held the position when the officer
and superintendent decided (`held_by`), are shown to officer, superintendent and authority
viewers only. `can_decide` says whether the viewer is the one whose decision is awaited, and
`allowed_outcomes` what they may decide. `stock_limit_problem` (the buyer's own stock numbers)
is shown to the buyer only, while the sale waits for them; the seller never sees it.
`status_for_you` is the status worded for the viewer (owner decision A8): "Requires your
approval" for whoever must decide, "Requires … approval" for the seller and buyer while the
sale waits on someone else, and the plain status label otherwise. `awaiting_you` (in lists
too) is true exactly when the viewer is the decider, like `can_decide`."""

from core.db_context import acting_as_system
from identity.models import User
from identity.roles import Role
from positions.service import positions_held
from transactions.checks import fmt_qty
from transactions.models import DecisionStep, Transaction, TransactionStatus
from transactions.service import allowed_outcomes, decision_role, stock_limit_problem

_AUTHORITY_ROLES = {Role.HEAD_AUTHORITY, Role.SOFTWARE_OWNER}
_NEXT_ACTION = {
    TransactionStatus.AWAITING_BUYER: "Waiting for the buyer to confirm.",
    TransactionStatus.AWAITING_OFFICER: "Waiting for the officer's decision.",
    TransactionStatus.AWAITING_SUPERINTENDENT: "Waiting for the superintendent's final approval.",
}
_HELD_BY_STEPS = {DecisionStep.OFFICER, DecisionStep.SUPERINTENDENT}


def _role(tx: Transaction, viewer: User) -> str:
    if viewer.licensee_gstin_index == tx.seller_gstin_index:
        return "seller"
    if viewer.licensee_gstin_index == tx.buyer_gstin_index:
        return "buyer"
    held = positions_held(viewer)
    if tx.designated_position in held:
        return "officer"
    if tx.superintendent_position in held:
        return "superintendent"
    return "authority"


_PARTIES = {"seller", "buyer"}
_WAITING_ON = {
    TransactionStatus.AWAITING_BUYER: "Requires buyer approval",
    TransactionStatus.AWAITING_OFFICER: "Requires officer approval",
    TransactionStatus.AWAITING_SUPERINTENDENT: "Requires superintendent approval",
}


def status_for_you(tx: Transaction, role: str, deciding_as: str | None) -> str:
    """The A8 wording; `role` is the viewer's `your_role`, `deciding_as` their
    `decision_role` (None when nothing waits on them)."""
    if deciding_as is not None:
        return "Requires your approval"
    if role in _PARTIES and tx.status in _WAITING_ON:
        return _WAITING_ON[tx.status]
    return tx.get_status_display()


def _names(tx: Transaction) -> tuple[str, str]:
    with acting_as_system("transaction_view"):
        return tx.seller_licence.holder_name, tx.buyer_licence.holder_name


def transaction_summary(tx: Transaction, viewer: User) -> dict:
    seller_name, buyer_name = _names(tx)
    role = _role(tx, viewer)
    deciding_as = decision_role(tx, viewer)
    return {
        "reference": tx.reference,
        "status": tx.status,
        "status_label": tx.get_status_display(),
        "status_for_you": status_for_you(tx, role, deciding_as),
        "awaiting_you": deciding_as is not None,
        "substance": tx.substance.name,
        "quantity": fmt_qty(tx.quantity),
        "unit": tx.unit,
        "seller_name": seller_name,
        "buyer_name": buyer_name,
        "created_at": tx.created_at.isoformat(),
        "your_role": role,
        "approval_chain": tx.approval_chain,
        "approval_chain_label": tx.get_approval_chain_display(),
    }


def _next_action(tx: Transaction, deciding_as: str | None) -> str | None:
    """Your turn exactly when you are the decider (decision_role)."""
    if deciding_as is not None:
        return "Your decision is needed."
    return _NEXT_ACTION.get(tx.status)


def _timeline(tx: Transaction, for_authority: bool) -> list[dict]:
    events = [
        {
            "step": "SELLER",
            "outcome": "STARTED",
            "at": tx.created_at.isoformat(),
            "by": "Seller",
            "reason": None,
            "comment": None,
            "held_by": None,
        }
    ]
    for d in tx.decisions.select_related("reason", "position").order_by("id"):
        events.append(
            {
                "step": d.step,
                "outcome": d.outcome,
                "at": d.created_at.isoformat(),
                "by": d.position.title if d.position else d.get_step_display(),
                "reason": d.reason.label if d.reason else None,
                "comment": (d.comment or None) if for_authority else None,
                "held_by": (
                    d.actor_user_id if for_authority and d.step in _HELD_BY_STEPS else None
                ),
            }
        )
    return events


def transaction_detail(tx: Transaction, viewer: User) -> dict:
    summary = transaction_summary(tx, viewer)
    role = summary["your_role"]
    deciding_as = decision_role(tx, viewer) if summary["awaiting_you"] else None
    for_authority = (
        role in {"officer", "superintendent", "authority"} or viewer.role in _AUTHORITY_ROLES
    )
    return {
        **summary,
        "transport": {
            "name": tx.transporter_name(),
            "id_number": tx.transporter_id(),
            "vehicle_number": tx.vehicle_number(),
            "route": tx.route,
        },
        "designated_officer": tx.designated_position.title,
        "timeline": _timeline(tx, for_authority),
        "next_action": _next_action(tx, deciding_as),
        "can_decide": deciding_as is not None,
        "allowed_outcomes": (
            sorted(allowed_outcomes(tx, deciding_as, viewer)) if deciding_as else []
        ),
        "stock_limit_problem": (
            stock_limit_problem(tx)
            if role == "buyer" and tx.status == TransactionStatus.AWAITING_BUYER
            else None
        ),
    }
