"""The transaction journey. Every write runs inside acting_as_system(...) AFTER checking in
plain Python who may act; row-level security only lets SYSTEM write.

Lock order (never reverse it): user row -> OTP challenge rows -> transaction row ->
stock balance rows (sorted) -> alert inserts -> audit (record() last).
"""

from dataclasses import dataclass
from decimal import Decimal

from django.utils import timezone

from alerts.service import raise_buyer_rejection_alerts
from audit.service import record
from catalogue.models import Substance
from catalogue.service import approval_chain_for
from core import crypto
from core.db_context import acting_as_system
from identity import otp
from identity.models import OtpChallenge, OtpPurpose, User
from licensing.models import Licence, LicenceStatus
from licensing.service import GSTIN_PATTERN, current_permissions
from positions.models import AreaLevel, Position
from positions.service import covering_position, positions_held
from reasons.models import ReasonKind
from reasons.service import resolve_reason
from stock.service import InsufficientStock, StockLimitExceeded, transfer
from transactions.checks import eligibility_problems, transaction_problems
from transactions.models import (
    ApprovalChain,
    DecisionOutcome,
    DecisionStep,
    Transaction,
    TransactionDecision,
    TransactionStatus,
)
from transactions.selection import licence_eligible, select_licence

NO_OFFICER = "No officer is responsible for your area yet. Please contact the Licensing Authority."
NO_SUPERINTENDENT = (
    "No superintendent is responsible for your district yet. "
    "Please contact the Licensing Authority."
)


class TransactionRefused(Exception):
    def __init__(self, reasons: list[str]):
        super().__init__("; ".join(reasons))
        self.reasons = reasons


class NotAllowed(Exception):
    pass


@dataclass(frozen=True)
class Transport:
    name: str
    id_number: str
    vehicle_number: str
    route: str


def find_buyer(*, gstin: str, by: User) -> str | None:
    """The buyer's registered name, or None. Audited by blind index only."""
    gstin = gstin.strip().upper()
    if not GSTIN_PATTERN.match(gstin):
        return None
    index = crypto.blind_index("gstin", gstin)
    with acting_as_system("buyer_lookup"):
        licence = (
            Licence.objects.filter(gstin_index=index, status=LicenceStatus.ACTIVE)
            .order_by("id")
            .first()
        )
        record(
            action="transaction.buyer_lookup",
            actor=by.user_id,
            payload={"gstin_index": index, "found": licence is not None},
        )
    return licence.holder_name if licence else None


def _refusals(seller_licence, buyer_licence, substance, quantity) -> list[str]:
    problems = eligibility_problems(seller_licence, buyer_licence, substance)
    if problems:
        return problems
    return transaction_problems(
        seller_licence=seller_licence,
        buyer_licence=buyer_licence,
        substance=substance,
        quantity=quantity,
    )


def _route(seller_licence: Licence) -> tuple[Position, Position]:
    """The seller's taluka officer and district superintendent positions; both must exist."""
    designated = covering_position(seller_licence.area, AreaLevel.TALUKA)
    if designated is None:
        raise TransactionRefused([NO_OFFICER])
    superintendent = covering_position(seller_licence.area, AreaLevel.DISTRICT)
    if superintendent is None:
        raise TransactionRefused([NO_SUPERINTENDENT])
    return designated, superintendent


def start_transaction(
    *, seller: User, buyer_gstin: str, substance: Substance, quantity: Decimal, transport: Transport
) -> Transaction:
    buyer_index = crypto.blind_index("gstin", buyer_gstin.strip().upper())
    if buyer_index == seller.licensee_gstin_index:
        raise TransactionRefused(["You cannot sell to your own business."])
    today = timezone.localdate()
    with acting_as_system("start_transaction"):
        seller_licence = select_licence(seller.licensee_gstin_index, substance, "sell", today)
        buyer_licence = select_licence(buyer_index, substance, "buy", today)
        problems = _refusals(seller_licence, buyer_licence, substance, quantity)
        if problems:
            raise TransactionRefused(problems)
        designated, superintendent = _route(seller_licence)
        tx = Transaction.objects.create(
            seller_licence=seller_licence,
            buyer_licence=buyer_licence,
            seller_gstin_index=seller_licence.gstin_index,
            buyer_gstin_index=buyer_licence.gstin_index,
            substance=substance,
            quantity=quantity,
            unit=substance.unit,
            transporter_name_encrypted=crypto.encrypt(transport.name),
            transporter_id_encrypted=crypto.encrypt(transport.id_number),
            vehicle_number_encrypted=crypto.encrypt(transport.vehicle_number),
            route=transport.route,
            designated_position=designated,
            superintendent_position=superintendent,
            approval_chain=approval_chain_for(substance, quantity),
            created_by=seller.user_id,
        )
        record(
            action="transaction.started",
            actor=seller.user_id,
            subject_type="transaction",
            subject_id=tx.reference,
        )
    return tx


def load_visible(reference: str) -> Transaction | None:
    """Read under the caller's own RLS context: None means not found OR not theirs to see."""
    return (
        Transaction.objects.select_related("substance", "designated_position")
        .filter(reference=reference)
        .first()
    )


def cancel_transaction(*, reference: str, seller: User) -> Transaction:
    tx = load_visible(reference)
    if tx is None or tx.seller_gstin_index != seller.licensee_gstin_index:
        raise NotAllowed("Only the seller can cancel this transaction.")
    with acting_as_system("cancel_transaction"):
        locked = Transaction.objects.select_for_update().get(pk=tx.pk)
        if locked.status != TransactionStatus.AWAITING_BUYER:
            raise NotAllowed("This transaction can no longer be cancelled.")
        locked.status = TransactionStatus.CANCELLED
        locked.decided_at = timezone.now()
        locked.save(update_fields=["status", "decided_at"])
        TransactionDecision.objects.create(
            transaction=locked,
            step=DecisionStep.SELLER,
            outcome=DecisionOutcome.CANCEL,
            actor_user_id=seller.user_id,
        )
        record(
            action="transaction.cancelled",
            actor=seller.user_id,
            subject_type="transaction",
            subject_id=locked.reference,
        )
    return locked


WRONG_TURN = "This transaction is not waiting for your decision."
SAME_PERSON = (
    "You made the officer decision on this transaction; another officer must give final approval."
)
_REASON_KIND = {
    "buyer": ReasonKind.BUYER_REJECTION,
    "officer": ReasonKind.OFFICER_REJECTION,
    "superintendent": ReasonKind.OFFICER_REJECTION,
}


def decision_role(tx: Transaction, user: User) -> str | None:
    if (
        tx.status == TransactionStatus.AWAITING_BUYER
        and user.licensee_gstin_index == tx.buyer_gstin_index
    ):
        return "buyer"
    if tx.status == TransactionStatus.AWAITING_OFFICER and tx.designated_position in positions_held(
        user
    ):
        return "officer"
    if _may_act_as_superintendent(tx, user) and not _made_officer_decision(tx, user):
        return "superintendent"
    return None


def _may_act_as_superintendent(tx: Transaction, user: User) -> bool:
    return (
        tx.status == TransactionStatus.AWAITING_SUPERINTENDENT
        and tx.superintendent_position in positions_held(user)
    )


def _made_officer_decision(tx: Transaction, user: User) -> bool:
    """Separation of duties: whoever made the officer decision never gives the final one."""
    return tx.decisions.filter(step=DecisionStep.OFFICER, actor_user_id=user.user_id).exists()


def allowed_outcomes(tx: Transaction, role: str) -> set[str]:
    """What `role` may decide on `tx` now. On the two-step chain the officer recommends and
    the superintendent gives the final approval."""
    if role == "buyer":
        return {DecisionOutcome.CONFIRM, DecisionOutcome.REJECT}
    if role == "officer" and tx.approval_chain == ApprovalChain.OFFICER_THEN_SUPERINTENDENT:
        return {DecisionOutcome.RECOMMEND, DecisionOutcome.REJECT}
    if role in {"officer", "superintendent"}:
        return {DecisionOutcome.APPROVE, DecisionOutcome.REJECT}
    return set()


def _for_decision(reference: str, user: User) -> tuple[Transaction, str]:
    tx = load_visible(reference)
    role = decision_role(tx, user) if tx else None
    if role is None:
        if tx and _may_act_as_superintendent(tx, user):
            raise NotAllowed(SAME_PERSON)  # the holder made the officer decision
        raise NotAllowed(WRONG_TURN)
    return tx, role


def request_decision_code(*, reference: str, user: User) -> OtpChallenge:
    # The code is bound to its USER, not to one transaction: it can only be spent on a
    # transaction that is currently waiting for that user (checked again in decide()).
    _for_decision(reference, user)
    return otp.issue(user, OtpPurpose.DECISION)


def decide(
    *,
    reference: str,
    user: User,
    challenge_id: str,
    code: str,
    outcome: str,
    reason_code: str = "",
    comment: str = "",
) -> Transaction | None:
    tx, role = _for_decision(reference, user)
    if outcome not in allowed_outcomes(tx, role):
        raise NotAllowed("That decision is not available at this step.")
    reason = (
        resolve_reason(_REASON_KIND[role], reason_code, comment)
        if outcome == DecisionOutcome.REJECT
        else None
    )
    signer = otp.verify(challenge_id=challenge_id, purpose=OtpPurpose.DECISION, code=code)
    if signer is None:
        return None  # wrong or expired code: the attempt counts, nothing else changes
    if signer.pk != user.pk:
        raise NotAllowed("This code belongs to someone else.")
    try:
        with acting_as_system("decide_transaction"):
            return _apply(tx, user, role, outcome, reason, comment)
    except TransactionRefused:
        # The decision's writes rolled back with the savepoint; the refusal itself is kept.
        record(
            action="transaction.approval_refused",
            actor=user.user_id,
            subject_type="transaction",
            subject_id=tx.reference,
        )
        raise


def _apply(
    tx: Transaction, user: User, role: str, outcome: str, reason, comment: str
) -> Transaction:
    locked = Transaction.objects.select_for_update().get(pk=tx.pk)
    if role == "superintendent" and _made_officer_decision(locked, user):
        raise NotAllowed(SAME_PERSON)  # defence under the lock; _for_decision checked first
    if decision_role(locked, user) != role:
        raise NotAllowed(WRONG_TURN)
    now = timezone.now()
    if outcome == DecisionOutcome.APPROVE:
        _approve(locked)
    if outcome == DecisionOutcome.RECOMMEND:
        _recheck(locked)
    locked.status = _NEXT[(role, outcome)]
    if locked.status not in _WAITING:
        locked.decided_at = now
    locked.save(update_fields=["status", "decided_at"])
    TransactionDecision.objects.create(
        transaction=locked,
        step=_STEP[role],
        outcome=outcome,
        actor_user_id=user.user_id,
        position=_position(locked, role),
        reason=reason,
        comment=comment.strip(),
        otp_verified_at=now,
    )
    payload = None
    if role == "buyer" and outcome == DecisionOutcome.REJECT:
        alerts = raise_buyer_rejection_alerts(locked, reason, comment.strip())
        payload = {"alerts_raised": len(alerts)}
    record(
        action=_AUDIT[(role, outcome)],
        actor=user.user_id,
        subject_type="transaction",
        subject_id=locked.reference,
        payload=payload,
    )
    return locked


def _position(tx: Transaction, role: str) -> Position | None:
    if role == "officer":
        return tx.designated_position
    if role == "superintendent":
        return tx.superintendent_position
    return None


def _recheck(tx: Transaction) -> None:
    """Both licences are still eligible today, the limits, and stock (with the buyer's stock
    cap). Moves nothing: an officer recommendation runs this alone."""
    today = timezone.localdate()
    seller = tx.seller_licence
    buyer = tx.buyer_licence
    problems = _refusals(
        seller if licence_eligible(seller, tx.substance, "sell", today) else None,
        buyer if licence_eligible(buyer, tx.substance, "buy", today) else None,
        tx.substance,
        tx.quantity,
    )
    if problems:
        raise TransactionRefused(problems)


def _approve(tx: Transaction) -> None:
    """Re-check everything at approval, then move the stock (again under the balance locks,
    with the buyer's stock cap)."""
    _recheck(tx)
    try:
        transfer(
            from_gstin_index=tx.seller_gstin_index,
            to_gstin_index=tx.buyer_gstin_index,
            substance=tx.substance,
            quantity=tx.quantity,
            transaction_reference=tx.reference,
            max_target=current_permissions(tx.buyer_licence, tx.substance).max_stock_qty,
        )
    except (InsufficientStock, StockLimitExceeded) as exc:
        raise TransactionRefused([str(exc) + "."]) from exc


# (role, outcome) -> the status it leads to, and the audit action it records.
_NEXT = {
    ("buyer", DecisionOutcome.CONFIRM): TransactionStatus.AWAITING_OFFICER,
    ("buyer", DecisionOutcome.REJECT): TransactionStatus.REJECTED_BY_BUYER,
    ("officer", DecisionOutcome.APPROVE): TransactionStatus.APPROVED,
    ("officer", DecisionOutcome.RECOMMEND): TransactionStatus.AWAITING_SUPERINTENDENT,
    ("officer", DecisionOutcome.REJECT): TransactionStatus.REJECTED_BY_OFFICER,
    ("superintendent", DecisionOutcome.APPROVE): TransactionStatus.APPROVED,
    ("superintendent", DecisionOutcome.REJECT): TransactionStatus.REJECTED_BY_SUPERINTENDENT,
}
_AUDIT = {
    ("buyer", DecisionOutcome.CONFIRM): "transaction.buyer_confirmed",
    ("buyer", DecisionOutcome.REJECT): "transaction.buyer_rejected",
    ("officer", DecisionOutcome.APPROVE): "transaction.approved",
    ("officer", DecisionOutcome.RECOMMEND): "transaction.recommended",
    ("officer", DecisionOutcome.REJECT): "transaction.officer_rejected",
    ("superintendent", DecisionOutcome.APPROVE): "transaction.approved",
    ("superintendent", DecisionOutcome.REJECT): "transaction.superintendent_rejected",
}
_STEP = {
    "buyer": DecisionStep.BUYER,
    "officer": DecisionStep.OFFICER,
    "superintendent": DecisionStep.SUPERINTENDENT,
}
# Statuses still waiting for someone: decided_at stays null.
_WAITING = {TransactionStatus.AWAITING_OFFICER, TransactionStatus.AWAITING_SUPERINTENDENT}
