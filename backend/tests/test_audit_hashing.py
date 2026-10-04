from datetime import UTC, datetime

from audit.hashing import GENESIS_HASH, compute_hash, event_fields


def sample_fields(**overrides):
    fields = dict(
        occurred_at=datetime(2026, 9, 26, 10, 0, 0, 123456, tzinfo=UTC),
        actor="GJTESTUSER01",
        action="test.action",
        subject_type="user",
        subject_id="GJTESTUSER02",
        reason="",
        payload={"b": 1, "a": "x"},
    )
    fields.update(overrides)
    return event_fields(**fields)


def test_hash_is_64_hex_chars_and_deterministic():
    first = compute_hash(GENESIS_HASH, sample_fields())
    assert first == compute_hash(GENESIS_HASH, sample_fields())
    assert len(first) == 64


def test_hash_ignores_payload_key_order():
    reordered = sample_fields(payload={"a": "x", "b": 1})
    assert compute_hash(GENESIS_HASH, reordered) == compute_hash(GENESIS_HASH, sample_fields())


def test_hash_changes_when_any_field_changes():
    base = compute_hash(GENESIS_HASH, sample_fields())
    assert compute_hash(GENESIS_HASH, sample_fields(reason="edited")) != base
    assert compute_hash("f" * 64, sample_fields()) != base
