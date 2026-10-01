"""The transaction journey. Every write runs inside acting_as_system(...) AFTER checking in
plain Python who may act; row-level security only lets SYSTEM write.

Lock order (never reverse it): user row -> OTP challenge rows -> transaction row ->
stock balance rows (sorted) -> audit (record() last).
"""

from dataclasses import dataclass
from decimal import Decimal

from django.utils import timezone

from audit.service import record
from catalogue.models import Substance
from core import crypto
from core.db_context import acting_as_system
from identity.models import User
from licensing.models import Licence, LicenceStatus
from licensing.service import GSTIN_PATTERN
from positions.models import AreaLevel
from positions.service import covering_position
from transactions.checks import eligibility_problems, transaction_problems
from transactions.models import (
    DecisionOutcome,
    DecisionStep,
    Transaction,
    TransactionDecision,
    TransactionStatus,
)
from transactions.selection import select_licence

NO_OFFICER = "No officer is responsible for your area yet. Please contact the Licensing Authority."


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
        designated = covering_position(seller_licence.area, AreaLevel.TALUKA)
        if designated is None:
            raise TransactionRefused([NO_OFFICER])
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
            superintendent_position=covering_position(seller_licence.area, AreaLevel.DISTRICT),
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
