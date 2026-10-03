"""What an authority sees for an alert. Party names are read as SYSTEM (registered names only);
no licence numbers, GSTINs or contacts are ever included."""

from alerts.models import AlertKind, AuthorityAlert
from alerts.service import pattern_text
from core.db_context import acting_as_system
from transactions.checks import fmt_qty


def alert_view(alert: AuthorityAlert) -> dict:
    tx = alert.transaction
    with acting_as_system("alert_view"):
        seller_name, buyer_name = tx.seller_licence.holder_name, tx.buyer_licence.holder_name
    ack = getattr(alert, "acknowledgement", None)
    return {
        "id": alert.id,
        "kind": alert.kind,
        "kind_label": alert.get_kind_display(),
        "created_at": alert.created_at.isoformat(),
        "transaction_reference": tx.reference,
        "substance": tx.substance.name,
        "quantity": fmt_qty(tx.quantity),
        "unit": tx.unit,
        "seller_name": seller_name,
        "buyer_name": buyer_name,
        "reason": alert.reason.label,
        "comment": alert.comment or None,
        "pattern": (
            pattern_text(alert.pattern_count) if alert.kind == AlertKind.BUYER_REJECTION else None
        ),
        "acknowledged": ack is not None,
        "acknowledged_by": ack.user_id if ack else None,
        "acknowledged_at": ack.created_at.isoformat() if ack else None,
        "note": (ack.note or None) if ack else None,
    }
