"""
test_core_rewrite_replay.py
Reducer determinism, state hash determinism, replay verifier PASS/FAIL tests.

Covers:
  - Reducer determinism: same event list always produces same state
  - State hash deterministic across Python sessions
  - ReplayVerifier.verify() PASS on clean WAL
  - ReplayVerifier.verify() FAIL on state divergence
  - ReplayVerifier.replay() produces correct final state
  - ReplayVerifier.wal_hash() deterministic
  - ReplayVerifier catches state mismatch details
"""
import sys
import time
import uuid
import copy
import tempfile
import os
sys.path.insert(0, '.')

from runtime.events import MCREvent
from runtime.wal import WAL
from runtime.state import SystemState
from runtime.reducer import DeterministicReducer
from runtime.replay_verifier import ReplayVerifier


def make_event(event_id, tick, memory_id, event_type='memory_store', payload=None):
    return MCREvent(
        event_id=event_id,
        event_type=event_type,
        tick=tick,
        memory_id=memory_id,
        coaccess_group_id='550e8400-e29b-41d4-a716-446655440000',
        payload=payload or {'content': f'content_{event_id}'},
        timestamp=time.time(),
        replay_hash='',
    )


def test_reducer_deterministic():
    """Reducer produces identical state for identical event sequence."""
    reducer = DeterministicReducer()
    state1 = SystemState.empty()
    state2 = SystemState.empty()

    events = [
        make_event('e1', 1, 'm1', payload={'content': 'a', 'tier': 'episodic'}),
        make_event('e2', 2, 'm2', payload={'content': 'b', 'tier': 'episodic'}),
        make_event('e3', 3, 'm1'),  # access
    ]

    for e in events:
        state1 = reducer.reduce(e, state1)

    for e in events:
        state2 = reducer.reduce(e, state2)

    assert state1.equals(state2), "reducer must be deterministic"
    assert state1.hash() == state2.hash()
    print(f"[PASS] reducer deterministic")


def test_reducer_clone_no_mutation_leak():
    """Reducer must not mutate input state."""
    reducer = DeterministicReducer()
    original = SystemState.empty()
    original.tick = 0
    original.memory['preexisting'] = {'content': 'keep', 'tier': 'episodic', 'created_tick': 0}

    after = reducer.reduce(
        make_event('x', 1, 'm1', payload={'content': 'x', 'tier': 'episodic'}),
        original,
    )

    assert 'preexisting' in original.memory, "input state must not be mutated"
    assert original.tick == 0, "input tick must not be mutated"
    assert after.tick == 1
    print("[PASS] reducer clone no mutation leak")


def test_state_hash_deterministic():
    """state.hash() must be stable across calls with identical content."""
    s1 = SystemState.empty()
    s1.memory['k1'] = {'content': 'v1', 'tier': 'episodic', 'created_tick': 1}
    s1.tick = 5

    h1 = s1.hash()
    h2 = s1.hash()
    assert h1 == h2, "hash must be deterministic"
    print(f"[PASS] state hash deterministic: {h1[:16]}...")


def test_state_clone_deep_copies_coaccess_graph():
    """SystemState.clone() deep-copies coaccess_graph sets."""
    s1 = SystemState.empty()
    s1.coaccess_graph['a'] = {'b', 'c'}
    s2 = s1.clone()
    s2.coaccess_graph['a'].add('d')

    assert 'd' not in s1.coaccess_graph['a'], "clone must deep-copy coaccess_graph"
    print("[PASS] state.clone() deep-copies coaccess_graph")


def test_replay_verifier_pass():
    """verify() returns match=True on clean WAL replay."""
    with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
        path = f.name
    try:
        wal = WAL(path)
        reducer = DeterministicReducer()
        state = SystemState.empty()
        events = [
            make_event('rv1', 1, 'm1', payload={'content': 'x', 'tier': 'episodic'}),
            make_event('rv2', 2, 'm2', payload={'content': 'y', 'tier': 'episodic'}),
        ]
        for e in events:
            wal.append(e)
            state = reducer.reduce(e, state)

        verifier = ReplayVerifier()
        initial = SystemState.empty()
        result = verifier.verify(state, initial, wal)

        assert result['match'] is True, f"Expected PASS, got {result}"
        assert result['reason'] == 'ok'
        print("[PASS] replay verifier PASS on clean WAL")
    finally:
        os.unlink(path)


def test_replay_verifier_catches_divergence():
    """verify() returns match=False with detail when state diverges from replay."""
    with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
        path = f.name
    try:
        wal = WAL(path)
        reducer = DeterministicReducer()
        state = SystemState.empty()
        events = [
            make_event('dv1', 1, 'm1', payload={'content': 'x', 'tier': 'episodic'}),
            make_event('dv2', 2, 'm2', payload={'content': 'y', 'tier': 'episodic'}),
        ]
        for e in events:
            wal.append(e)
            state = reducer.reduce(e, state)

        # Tamper with state after WAL was built
        state.memory['dv1'] = {'content': 'tampered', 'tier': 'episodic', 'created_tick': 1}

        verifier = ReplayVerifier()
        initial = SystemState.empty()
        result = verifier.verify(state, initial, wal)

        assert result['match'] is False, "tampered state must fail verification"
        assert result['reason'] == 'state_mismatch'
        assert 'memory' in result['detail'], "detail must name divergent field"
        print(f"[PASS] replay verifier catches divergence: {result['detail']}")
    finally:
        os.unlink(path)


def test_wal_hash_deterministic():
    """wal_hash() is deterministic across calls."""
    with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
        path = f.name
    try:
        wal = WAL(path)
        wal.append(make_event('wh1', 1, 'm1', payload={'content': 'a', 'tier': 'episodic'}))
        wal.append(make_event('wh2', 2, 'm2', payload={'content': 'b', 'tier': 'episodic'}))

        verifier = ReplayVerifier()
        h1 = verifier.wal_hash(wal)
        h2 = verifier.wal_hash(wal)
        assert h1 == h2, "wal_hash must be deterministic"
        assert len(h1) == 64
        print(f"[PASS] wal_hash deterministic: {h1[:16]}...")
    finally:
        os.unlink(path)


def test_wal_hash_empty():
    """wal_hash() returns empty string for empty WAL."""
    path = tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False).name
    os.unlink(path)
    try:
        wal = WAL(path)
        verifier = ReplayVerifier()
        h = verifier.wal_hash(wal)
        assert h == '', "empty WAL must have empty hash"
        print("[PASS] wal_hash empty WAL")
    finally:
        os.unlink(path) if os.path.exists(path) else None


def test_replay_from_empty_state():
    """ReplayVerifier.replay() produces correct final state from empty initial."""
    with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
        path = f.name
    try:
        wal = WAL(path)
        wal.append(make_event('rf1', 1, 'r1', payload={'content': 'x', 'tier': 'episodic'}))
        wal.append(make_event('rf2', 2, 'r2', payload={'content': 'y', 'tier': 'episodic'}))

        verifier = ReplayVerifier()
        initial = SystemState.empty()
        final = verifier.replay(initial, wal)

        assert final.tick == 2, f"Expected tick 2, got {final.tick}"
        assert len(final.memory) == 2
        print(f"[PASS] replay from empty: tick={final.tick}, mem={len(final.memory)}")
    finally:
        os.unlink(path)


if __name__ == '__main__':
    test_reducer_deterministic()
    test_reducer_clone_no_mutation_leak()
    test_state_hash_deterministic()
    test_state_clone_deep_copies_coaccess_graph()
    test_replay_verifier_pass()
    test_replay_verifier_catches_divergence()
    test_wal_hash_deterministic()
    test_wal_hash_empty()
    test_replay_from_empty_state()
    print("\n=== All Replay/Dedup tests PASSED ===")