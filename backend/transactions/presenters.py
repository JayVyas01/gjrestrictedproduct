"""What each viewer sees of a transaction. Party names are read as SYSTEM (the other party's
licence is hidden from the viewer by RLS) and only the registered name is shown. The buyer's
and officer's free-text comments, and who held the officer position when it decided
(`held_by`), are shown to officer, superintendent and authority viewers only. `can_decide`
says whether the viewer is the one whose decision is awaited."""

from core.db_context import acting_as_system
from identity.models import User
from identity.roles import Role
from positions.service import positions_held
from transactions.checks import fmt_qty
from transactions.models import DecisionStep, Transaction, TransactionStatus
from transactions.service import decision_role

_AUTHORITY_ROLES = {Role.HEAD_AUTHORITY, Role.SOFTWARE_OWNER}
_NEXT_ACTION = {
    TransactionStatus.AWAITING_BUYER: "Waiting for the buyer to confirm.",
    TransactionStatus.AWAITING_OFFICER: "Waiting for the officer's decision.",
}


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


def _names(tx: Transaction) -> tuple[str, str]:
    with acting_as_system("transaction_view"):
        return tx.seller_licence.holder_name, tx.buyer_licence.holder_name


def transaction_summary(tx: Transaction, viewer: User) -> dict:
    seller_name, buyer_name = _names(tx)
    return {
        "reference": tx.reference,
        "status": tx.status,
        "status_label": tx.get_status_display(),
        "substance": tx.substance.name,
        "quantity": fmt_qty(tx.quantity),
        "unit": tx.unit,
        "seller_name": seller_name,
        "buyer_name": buyer_name,
        "created_at": tx.created_at.isoformat(),
        "your_role": _role(tx, viewer),
    }


def _next_action(tx: Transaction, role: str) -> str | None:
    if (tx.status, role) in {
        (TransactionStatus.AWAITING_BUYER, "buyer"),
        (TransactionStatus.AWAITING_OFFICER, "officer"),
    }:
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
                    d.actor_user_id if for_authority and d.step == DecisionStep.OFFICER else None
                ),
            }
        )
    return events


def transaction_detail(tx: Transaction, viewer: User) -> dict:
    summary = transaction_summary(tx, viewer)
    role = summary["your_role"]
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
        "next_action": _next_action(tx, role),
        "can_decide": decision_role(tx, viewer) is not None,
    }
