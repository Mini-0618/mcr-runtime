"""
test_core_rewrite_wal.py
WAL append, replay, and corruption handling tests.

Covers:
  - WAL append + get_all order
  - WAL append does NOT mutate caller's event
  - WAL append writes replay_hash correctly
  - WAL append is append-only (existing lines preserved)
  - WAL skip bad lines on load
  - WAL from empty has is_empty() = True
  - WAL len() correct
"""
import sys
import os
import time
import uuid
import tempfile
sys.path.insert(0, '.')

from runtime.events import MCREvent
from runtime.wal import WAL


def make_event(event_id, tick, memory_id, payload=None):
    return MCREvent(
        event_id=event_id,
        event_type='memory_store',
        tick=tick,
        memory_id=memory_id,
        coaccess_group_id='550e8400-e29b-41d4-a716-446655440000',
        payload=payload or {'content': f'content_{event_id}'},
        timestamp=time.time(),
        replay_hash='',
    )


def test_wal_append_does_not_mutate_caller_event():
    """WAL.append() must not modify the event passed by the caller."""
    with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
        path = f.name
    try:
        wal = WAL(path)
        original = make_event('c1', 1, 'm1')
        original_hash_before = original.compute_replay_hash()

        wal.append(original)

        # Caller event must NOT have replay_hash set by WAL.append
        assert original.replay_hash == '', f"WAL.append must not set replay_hash on caller's event, got '{original.replay_hash}'"
        # Caller event must not have been tampered with
        assert original.compute_replay_hash() == original_hash_before
        print("[PASS] WAL.append does not mutate caller event")
    finally:
        os.unlink(path)


def test_wal_append_order_preserved():
    """get_all() returns events in the same order they were appended."""
    with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
        path = f.name
    try:
        wal = WAL(path)
        events = [make_event(f'ev{i}', i, f'mem{i}') for i in range(1, 6)]
        for e in events:
            wal.append(e)

        retrieved = wal.get_all()
        assert len(retrieved) == 5, f"Expected 5 events, got {len(retrieved)}"
        for i, e in enumerate(retrieved):
            assert e.tick == i + 1, f"Event order mismatch at index {i}: tick={e.tick}"
        print("[PASS] WAL append order preserved")
    finally:
        os.unlink(path)


def test_wal_append_writes_replay_hash():
    """Each WAL line must contain a non-empty replay_hash after append."""
    with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
        path = f.name
    try:
        wal = WAL(path)
        event = make_event('rh1', 1, 'mem1')
        wal.append(event)

        retrieved = wal.get_all()
        assert len(retrieved) == 1
        assert retrieved[0].replay_hash != '', "stored event must have replay_hash"
        assert len(retrieved[0].replay_hash) == 64, "replay_hash must be SHA-256 hex"
        print(f"[PASS] WAL writes replay_hash: {retrieved[0].replay_hash[:16]}...")
    finally:
        os.unlink(path)


def test_wal_append_is_append_only():
    """Append must not overwrite or remove existing lines."""
    with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
        path = f.name
    try:
        wal = WAL(path)
        wal.append(make_event('ao1', 1, 'm1'))
        wal.append(make_event('ao2', 2, 'm2'))

        # Re-read from disk
        wal2 = WAL(path)
        assert wal2.len() == 2, f"Expected 2 events, got {wal2.len()}"
        print("[PASS] WAL append-only semantics preserved")
    finally:
        os.unlink(path)


def test_wal_is_empty_on_new_path():
    """WAL on non-existent path must be empty."""
    with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
        path = f.name
    os.unlink(path)
    wal = WAL(path)
    assert wal.is_empty() is True, "new WAL must be empty"
    assert wal.len() == 0
    print("[PASS] new WAL is empty")


def test_wal_len_after_append():
    """WAL.len() increments correctly after each append."""
    with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
        path = f.name
    try:
        wal = WAL(path)
        assert wal.len() == 0
        wal.append(make_event('l1', 1, 'm1'))
        assert wal.len() == 1
        wal.append(make_event('l2', 2, 'm2'))
        assert wal.len() == 2
        print("[PASS] WAL len correct after append")
    finally:
        os.unlink(path)


def test_wal_skip_bad_lines():
    """WAL._load() skips malformed JSON and entries with bad replay_hash."""
    path = tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False).name
    try:
        with open(path, 'w', encoding='utf-8') as f:
            # Write valid event first
            e = make_event('good1', 1, 'm1')
            import json
            d = e.to_dict()
            d['replay_hash'] = e.compute_replay_hash()
            f.write(json.dumps(d) + '\n')
            # Write bad JSON
            f.write('not valid json\n')
            # Write valid event second
            e2 = make_event('good2', 2, 'm2')
            d2 = e2.to_dict()
            d2['replay_hash'] = e2.compute_replay_hash()
            f.write(json.dumps(d2) + '\n')
            # Write JSON with wrong replay_hash (tampered)
            d3 = e2.to_dict()
            d3['replay_hash'] = 'wrong_hash'
            f.write(json.dumps(d3) + '\n')
        wal = WAL(path)
        # Must load 2 good events, skip 2 bad ones
        assert wal.len() == 2, f"Expected 2 events, got {wal.len()} — bad lines not skipped correctly"
        assert wal.get_all()[0].event_id == 'good1'
        assert wal.get_all()[1].event_id == 'good2'
        print(f"[PASS] WAL skips bad lines: loaded {wal.len()}/4 events")
    finally:
        os.unlink(path)


def test_wal_clear():
    """WAL.clear() removes file and resets in-memory events."""
    with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
        path = f.name
    wal = WAL(path)
    wal.append(make_event('c1', 1, 'm1'))
    wal.append(make_event('c2', 2, 'm2'))
    assert wal.len() == 2
    wal.clear()
    assert wal.len() == 0
    assert wal.is_empty() is True
    # Re-reading from cleared WAL must also be empty
    wal2 = WAL(path)
    assert wal2.is_empty() is True
    print("[PASS] WAL.clear() works correctly")


def test_wal_replay_from_empty():
    """WAL replay reconstructs state from events in order."""
    with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
        path = f.name
    try:
        wal = WAL(path)
        wal.append(make_event('r1', 1, 'mem_a', {'content': 'alpha', 'tier': 'episodic'}))
        wal.append(make_event('r2', 2, 'mem_b', {'content': 'beta', 'tier': 'episodic'}))

        retrieved = wal.get_all()
        assert len(retrieved) == 2
        assert retrieved[0].memory_id == 'mem_a'
        assert retrieved[1].memory_id == 'mem_b'
        print("[PASS] WAL replay order correct")
    finally:
        os.unlink(path)


if __name__ == '__main__':
    test_wal_append_does_not_mutate_caller_event()
    test_wal_append_order_preserved()
    test_wal_append_writes_replay_hash()
    test_wal_append_is_append_only()
    test_wal_is_empty_on_new_path()
    test_wal_len_after_append()
    test_wal_skip_bad_lines()
    test_wal_clear()
    test_wal_replay_from_empty()
    print("\n=== All WAL tests PASSED ===")