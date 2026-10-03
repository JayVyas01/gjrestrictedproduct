"""Pure functions defining the audit hash chain.

Each event's hash covers its own fields plus the previous event's hash, so changing,
removing or reordering any event breaks every hash after it.

The chain is unkeyed SHA-256, so it detects changes by anyone who cannot also rewrite
every later hash and the head; anchoring to a separate write-once store (Phase 5)
closes that gap.
"""

import hashlib
import json
from datetime import UTC, datetime

GENESIS_HASH = "0" * 64


def event_fields(
    *,
    occurred_at: datetime,
    actor: str,
    action: str,
    subject_type: str,
    subject_id: str,
    reason: str,
    payload: dict,
) -> dict:
    return {
        "occurred_at": occurred_at.astimezone(UTC).isoformat(timespec="microseconds"),
        "actor": actor,
        "action": action,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "reason": reason,
        "payload": payload,
    }


def compute_hash(prev_hash: str, fields: dict) -> str:
    canonical = json.dumps(
        {"prev_hash": prev_hash, **fields},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
