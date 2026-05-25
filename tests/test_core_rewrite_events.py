"""
test_core_rewrite_events.py
MCREvent schema, serialization, and replay_hash lifecycle tests.

Covers:
  - MCREvent schema / serialization round-trip
  - replay_hash lifecycle: compute -> write -> validate
  - replay_hash deterministic across sessions
  - to_dict / from_dict round-trip preserves fields
  - equals() excludes replay_hash
"""
import sys
import time
import uuid
sys.path.insert(0, '.')

from runtime.events import MCREvent


def test_event_serialization_roundtrip():
    """to_dict + from_dict preserves all MCREvent fields."""
    event = MCREvent(
        event_id=str(uuid.uuid4()),
        event_type='memory_store',
        tick=1,
        memory_id='mem_001',
        coaccess_group_id='550e8400-e29b-41d4-a716-446655440000',
        payload={'content': 'hello', 'tier': 'episodic'},
        timestamp=time.time(),
        replay_hash='',
    )
    d = event.to_dict()
    restored = MCREvent.from_dict(d)

    assert restored.event_id == event.event_id
    assert restored.event_type == event.event_type
    assert restored.tick == event.tick
    assert restored.memory_id == event.memory_id
    assert restored.coaccess_group_id == event.coaccess_group_id
    assert restored.payload == event.payload
    assert abs(restored.timestamp - event.timestamp) < 1e-6
    # replay_hash not preserved in to_dict/from_dict by default
    print(f"[PASS] event serialization roundtrip")


def test_replay_hash_computed_deterministic():
    """compute_replay_hash() is deterministic across calls with same content."""
    event = MCREvent(
        event_id='id-001',
        event_type='memory_store',
        tick=5,
        memory_id='mem_x',
        coaccess_group_id='550e8400-e29b-41d4-a716-446655440000',
        payload={'content': 'test', 'tier': 'episodic'},
        timestamp=100.0,
        replay_hash='',
    )
    h1 = event.compute_replay_hash()
    h2 = event.compute_replay_hash()
    assert h1 == h2, "replay_hash must be deterministic"
    assert len(h1) == 64, "SHA-256 hex is 64 chars"
    print(f"[PASS] replay_hash deterministic: {h1[:16]}...")


def test_replay_hash_excludes_itself():
    """compute_replay_hash() result is NOT included in the hash input."""
    event = MCREvent(
        event_id='id-002',
        event_type='memory_access',
        tick=2,
        memory_id='mem_y',
        coaccess_group_id='550e8400-e29b-41d4-a716-446655440000',
        payload={},
        timestamp=200.0,
        replay_hash='SOME_PRE_EXISTING_HASH',
    )
    hash_without = event.compute_replay_hash()

    event2 = MCREvent(
        event_id='id-002',
        event_type='memory_access',
        tick=2,
        memory_id='mem_y',
        coaccess_group_id='550e8400-e29b-41d4-a716-446655440000',
        payload={},
        timestamp=200.0,
        replay_hash='',
    )
    hash_blank = event2.compute_replay_hash()
    assert hash_without == hash_blank, "replay_hash field must not affect its own computation"
    print(f"[PASS] replay_hash excludes itself")


def test_validate_replay_hash():
    """validate_replay_hash() returns True when hash is set and matches."""
    event = MCREvent(
        event_id='id-003',
        event_type='memory_store',
        tick=3,
        memory_id='mem_z',
        coaccess_group_id='550e8400-e29b-41d4-a716-446655440000',
        payload={'content': 'data', 'tier': 'episodic'},
        timestamp=300.0,
        replay_hash='',
    )
    event.replay_hash = event.compute_replay_hash()

    assert event.validate_replay_hash() is True
    print(f"[PASS] replay_hash validates correctly")


def test_validate_replay_hash_fails_on_tamper():
    """validate_replay_hash() returns False when event was modified."""
    event = MCREvent(
        event_id='id-004',
        event_type='memory_store',
        tick=4,
        memory_id='mem_w',
        coaccess_group_id='550e8400-e29b-41d4-a716-446655440000',
        payload={'content': 'original', 'tier': 'episodic'},
        timestamp=400.0,
        replay_hash='',
    )
    event.replay_hash = event.compute_replay_hash()

    # Tamper with payload after hash was set
    event.payload = {'content': 'tampered', 'tier': 'episodic'}
    assert event.validate_replay_hash() is False, "tampered event must fail validation"
    print(f"[PASS] replay_hash detects tampering")


def test_validate_replay_hash_empty_is_false():
    """validate_replay_hash() returns False when replay_hash is empty."""
    event = MCREvent(
        event_id='id-005',
        event_type='memory_archive',
        tick=5,
        memory_id=None,
        coaccess_group_id='550e8400-e29b-41d4-a716-446655440000',
        payload={'reason': 'aged'},
        timestamp=500.0,
        replay_hash='',
    )
    assert event.validate_replay_hash() is False, "empty replay_hash must fail validation"
    print(f"[PASS] empty replay_hash rejected")


def test_equals_excludes_replay_hash():
    """equals() returns True for content-identical events with different replay_hash."""
    event_a = MCREvent(
        event_id='id-006',
        event_type='memory_store',
        tick=6,
        memory_id='mem_v',
        coaccess_group_id='550e8400-e29b-41d4-a716-446655440000',
        payload={'content': 'same', 'tier': 'working'},
        timestamp=600.0,
        replay_hash='HASH_A',
    )
    event_b = MCREvent(
        event_id='id-006',
        event_type='memory_store',
        tick=6,
        memory_id='mem_v',
        coaccess_group_id='550e8400-e29b-41d4-a716-446655440000',
        payload={'content': 'same', 'tier': 'working'},
        timestamp=600.0,
        replay_hash='HASH_B',
    )
    assert event_a.equals(event_b) is True, "equals must ignore replay_hash"
    print(f"[PASS] equals() ignores replay_hash")


def test_event_type_key_serialization():
    """to_dict uses _event_type key, from_dict restores event_type."""
    event = MCREvent(
        event_id='id-007',
        event_type='memory_purge',
        tick=7,
        memory_id='mem_u',
        coaccess_group_id='550e8400-e29b-41d4-a716-446655440000',
        payload={},
        timestamp=700.0,
        replay_hash='',
    )
    d = event.to_dict()
    assert '_event_type' in d, "to_dict must use _event_type key"
    assert 'event_type' not in d

    restored = MCREvent.from_dict(d)
    assert restored.event_type == 'memory_purge'
    print(f"[PASS] _event_type serialization correct")


if __name__ == '__main__':
    test_event_serialization_roundtrip()
    test_replay_hash_computed_deterministic()
    test_replay_hash_excludes_itself()
    test_validate_replay_hash()
    test_validate_replay_hash_fails_on_tamper()
    test_validate_replay_hash_empty_is_false()
    test_equals_excludes_replay_hash()
    test_event_type_key_serialization()
    print("\n=== All MCREvent tests PASSED ===")