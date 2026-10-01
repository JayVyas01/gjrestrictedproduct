"""Read and move stock. Writes need a SYSTEM context (row-level security enforces it).

Lock order: balance rows are locked in sorted GSTIN-index order so two transfers between the
same businesses can never deadlock. Callers audit the business action (e.g. the approval).
"""

from decimal import Decimal

from django.db import transaction

from audit.service import record
from catalogue.models import Substance
from stock.models import MovementReason, StockBalance, StockMovement


class InsufficientStock(Exception):
    pass


def balance_of(gstin_index: str, substance: Substance) -> Decimal:
    row = StockBalance.objects.filter(gstin_index=gstin_index, substance=substance).first()
    return row.quantity if row else Decimal("0")


def set_opening_balance(
    *, gstin_index: str, substance: Substance, quantity: Decimal, by: str
) -> StockBalance:
    with transaction.atomic():
        if StockBalance.objects.filter(gstin_index=gstin_index, substance=substance).exists():
            raise ValueError(
                "An opening balance is already recorded for this business and substance"
            )
        balance = StockBalance.objects.create(
            gstin_index=gstin_index, substance=substance, quantity=quantity
        )
        StockMovement.objects.create(
            gstin_index=gstin_index,
            substance=substance,
            delta=quantity,
            balance_after=quantity,
            reason=MovementReason.OPENING,
        )
        record(
            action="stock.opening_recorded",
            actor=by,
            subject_type="substance",
            subject_id=substance.code,
            payload={"gstin_index": gstin_index, "quantity": str(quantity)},
        )
    return balance


def _locked(gstin_index: str, substance: Substance) -> StockBalance:
    StockBalance.objects.get_or_create(
        gstin_index=gstin_index, substance=substance, defaults={"quantity": Decimal("0")}
    )
    return StockBalance.objects.select_for_update().get(
        gstin_index=gstin_index, substance=substance
    )


def transfer(
    *,
    from_gstin_index: str,
    to_gstin_index: str,
    substance: Substance,
    quantity: Decimal,
    transaction_reference: str,
) -> None:
    with transaction.atomic():
        rows = {
            index: _locked(index, substance) for index in sorted({from_gstin_index, to_gstin_index})
        }
        source, target = rows[from_gstin_index], rows[to_gstin_index]
        if source.quantity < quantity:
            raise InsufficientStock("The seller no longer has enough stock for this transaction")
        for row, delta in ((source, -quantity), (target, quantity)):
            row.quantity += delta
            row.save(update_fields=["quantity", "updated_at"])
            StockMovement.objects.create(
                gstin_index=row.gstin_index,
                substance=substance,
                delta=delta,
                balance_after=row.quantity,
                reason=MovementReason.TRANSACTION,
                transaction_reference=transaction_reference,
            )
