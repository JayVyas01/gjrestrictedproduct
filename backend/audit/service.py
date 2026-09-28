"""Append events to the audit trail.

Uses a plain INSERT (no RETURNING) on purpose: RLS hides events from most roles, and
RETURNING would require read access. Callers get the new hash back instead.
"""

import json

from django.db import connection, transaction
from django.utils import timezone

from audit.hashing import compute_hash, event_fields
from audit.models import AuditChainHead

_ALLOWED_VALUE_TYPES = (str, int, bool, type(None))

_INSERT = """
INSERT INTO audit_auditevent
    (occurred_at, actor, action, subject_type, subject_id, reason, payload, prev_hash, hash)
VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
"""


def _check_payload(payload: dict) -> None:
    # Flat, simple values only: they survive the JSONB round trip unchanged,
    # so the hash can always be recomputed exactly.
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, _ALLOWED_VALUE_TYPES):
            raise TypeError(f"Audit payload field {key!r} must be str, int, bool or None")


def record(
    *,
    action: str,
    actor: str = "",
    subject_type: str = "",
    subject_id: str = "",
    reason: str = "",
    payload: dict | None = None,
) -> str:
    payload = payload or {}
    _check_payload(payload)
    with transaction.atomic():
        head = AuditChainHead.objects.select_for_update().get(pk=1)
        occurred_at = timezone.now()
        fields = event_fields(
            occurred_at=occurred_at,
            actor=actor,
            action=action,
            subject_type=subject_type,
            subject_id=subject_id,
            reason=reason,
            payload=payload,
        )
        new_hash = compute_hash(head.last_hash, fields)
        with connection.cursor() as cursor:
            cursor.execute(
                _INSERT,
                [
                    occurred_at,
                    actor,
                    action,
                    subject_type,
                    subject_id,
                    reason,
                    json.dumps(payload),
                    head.last_hash,
                    new_hash,
                ],
            )
        head.last_hash = new_hash
        head.save(update_fields=["last_hash"])
    return new_hash
