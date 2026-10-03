"""Recompute the whole audit hash chain and report the first break, if any.

Needs read access to all events, so call it as a SYSTEM actor (see the management command).

Reads the chain head before iterating events, and under READ COMMITTED a concurrent
record() can commit new events after that read. Those events legitimately extend the
chain and must not look like tampering, so we only require the head hash to appear
somewhere among the events we verified (or to still be GENESIS_HASH), rather than
requiring it to equal the last event we saw.
"""

from dataclasses import dataclass

from audit.hashing import GENESIS_HASH, compute_hash, event_fields
from audit.models import AuditChainHead, AuditEvent


@dataclass(frozen=True)
class ChainReport:
    ok: bool
    checked: int
    first_bad_event_id: int | None = None
    problem: str = ""


def verify_chain() -> ChainReport:
    head_hash = AuditChainHead.objects.get(pk=1).last_hash
    expected_prev = GENESIS_HASH
    checked = 0
    head_seen = head_hash == GENESIS_HASH
    for event in AuditEvent.objects.order_by("id").iterator(chunk_size=1000):
        if event.prev_hash != expected_prev:
            return ChainReport(
                False, checked, event.id, "prev_hash does not match the previous event"
            )
        fields = event_fields(
            occurred_at=event.occurred_at,
            actor=event.actor,
            action=event.action,
            subject_type=event.subject_type,
            subject_id=event.subject_id,
            reason=event.reason,
            payload=event.payload,
        )
        if compute_hash(event.prev_hash, fields) != event.hash:
            return ChainReport(False, checked, event.id, "event contents do not match its hash")
        expected_prev = event.hash
        checked += 1
        if event.hash == head_hash:
            head_seen = True
    if not head_seen:
        return ChainReport(False, checked, None, "chain head does not match the last event")
    return ChainReport(True, checked)
