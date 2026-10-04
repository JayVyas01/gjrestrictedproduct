"""What a superintendent (or Head Authority) sees of a batch. Party names are read as SYSTEM;
no licence numbers, GSTINs or contacts are included."""

from datetime import date

from core.db_context import acting_as_system
from identity.models import User
from oversight.models import BatchSignOff, OversightBatch
from oversight.service import batch_status
from positions.service import positions_held
from transactions.checks import fmt_qty
from transactions.models import DecisionStep
from transactions.service import final_approval


def batch_summary(batch: OversightBatch, today: date) -> dict:
    signed = BatchSignOff.objects.filter(batch=batch).first()
    return {
        "id": batch.id,
        "position": batch.position.title,
        "period_start": batch.period_start.isoformat(),
        "period_end": batch.period_end.isoformat(),
        "due_on": batch.due_on().isoformat(),
        "status": batch_status(batch, today),
        "item_count": batch.items.count(),
        "flag_count": batch.items.filter(flag__isnull=False).count(),
        "signed_at": signed.created_at.isoformat() if signed else None,
        "signed_by": signed.signed_by if signed else None,
    }


def _item(item) -> dict:
    tx = item.transaction
    with acting_as_system("batch_view"):
        names = (tx.seller_licence.holder_name, tx.buyer_licence.holder_name)
    approval = final_approval(tx)
    flag = getattr(item, "flag", None)
    return {
        "reference": tx.reference,
        "substance": tx.substance.name,
        "quantity": fmt_qty(tx.quantity),
        "unit": tx.unit,
        "seller_name": names[0],
        "buyer_name": names[1],
        "approved_at": approval.created_at.isoformat(),
        "approved_by_position": approval.position.title,
        "approved_by_superintendent": approval.step == DecisionStep.SUPERINTENDENT,
        "flag": {
            "reason": flag.reason.label,
            "comment": flag.comment or None,
            "flagged_at": flag.created_at.isoformat(),
        }
        if flag
        else None,
    }


def batch_detail(batch: OversightBatch, today: date, viewer: User) -> dict:
    summary = batch_summary(batch, today)
    items = batch.items.select_related("transaction__substance").order_by("id")
    return {
        **summary,
        "items": [_item(item) for item in items],
        "can_sign": summary["status"] != "SIGNED" and batch.position in positions_held(viewer),
    }
