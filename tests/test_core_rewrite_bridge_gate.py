"""
test_core_rewrite_bridge_gate.py
EventGate validation, HermesBridge bypass prevention, engine tick authority tests.

Covers:
  - EventGate rejects unknown event_type
  - EventGate rejects missing required payload fields
  - EventGate rejects forbidden fields
  - EventGate rejects invalid coaccess_group_id
  - EventGate rejects empty memory_id on memory operations
  - EventGate rejects None memory_id on memory operations
  - EventGate accepts valid proposal
  - HermesBridge.submit_proposal() routes through EventGate (no bypass)
  - HermesBridge cannot set tick (Engine must override)
  - Engine.emit_raw() overrides tick from event
  - Engine.emit_raw() does not mutate caller's event
  - HermesBridge.create_proposal() exists and creates valid proposal
"""
import sys
import time
import uuid
import tempfile
import os
sys.path.insert(0, '.')

from runtime.events import EventProposal, ValidationResult, ALLOWED_EVENT_TYPES
from runtime.event_gate import EventGate, is_valid_uuid
from runtime.hermes_bridge import HermesBridge
from runtime.engine import MCRRuntimeEngine


def test_gate_rejects_unknown_event_type():
    """Rule 1: unknown event_type must be rejected."""
    gate = EventGate()
    proposal = EventProposal(
        event_type='UNKNOWN_EVENT',
        tick=1,
        memory_id=None,
        coaccess_group_id=str(uuid.uuid4()),
        payload={},
    )
    result = gate.validate(proposal)
    assert result.accepted is False, "unknown event_type must be rejected"
    assert 'Unknown event type' in result.reason
    print("[PASS] gate rejects unknown event_type")


def test_gate_rejects_missing_payload_fields():
    """Rule 2: missing required payload fields must be rejected."""
    gate = EventGate()
    proposal = EventProposal(
        event_type='memory_store',
        tick=1,
        memory_id='mem1',
        coaccess_group_id=str(uuid.uuid4()),
        payload={},  # missing content and tier
    )
    result = gate.validate(proposal)
    assert result.accepted is False, "missing required fields must be rejected"
    assert 'Missing required field' in result.reason
    print("[PASS] gate rejects missing payload fields")


def test_gate_rejects_forbidden_fields():
    """Rule 3: forbidden payload fields must be rejected."""
    gate = EventGate()
    proposal = EventProposal(
        event_type='memory_store',
        tick=1,
        memory_id='mem2',
        coaccess_group_id=str(uuid.uuid4()),
        payload={'content': 'test', 'tier': 'episodic', 'state': 'corrupt'},
    )
    result = gate.validate(proposal)
    assert result.accepted is False, "forbidden fields must be rejected"
    assert 'Unexpected payload field' in result.reason
    print("[PASS] gate rejects forbidden payload fields")


def test_gate_rejects_invalid_coaccess_group_id():
    """Rule 4: invalid coaccess_group_id must be rejected."""
    gate = EventGate()
    for bad_id in [None, '', 'not-a-uuid', 123]:
        proposal = EventProposal(
            event_type='memory_store',
            tick=1,
            memory_id='mem3',
            coaccess_group_id=bad_id,
            payload={'content': 'test', 'tier': 'episodic'},
        )
        result = gate.validate(proposal)
        assert result.accepted is False, f"coaccess_group_id={bad_id!r} must be rejected"
    print("[PASS] gate rejects invalid coaccess_group_id")


def test_gate_rejects_empty_memory_id():
    """Rule 5: empty string memory_id on memory ops must be rejected."""
    gate = EventGate()
    proposal = EventProposal(
        event_type='memory_store',
        tick=1,
        memory_id='',
        coaccess_group_id=str(uuid.uuid4()),
        payload={'content': 'test', 'tier': 'episodic'},
    )
    result = gate.validate(proposal)
    assert result.accepted is False
    print("[PASS] gate rejects empty memory_id")


def test_gate_rejects_none_memory_id():
    """Rule 5: None memory_id on memory ops must be rejected."""
    gate = EventGate()
    proposal = EventProposal(
        event_type='memory_store',
        tick=1,
        memory_id=None,
        coaccess_group_id=str(uuid.uuid4()),
        payload={'content': 'test', 'tier': 'episodic'},
    )
    result = gate.validate(proposal)
    assert result.accepted is False
    print("[PASS] gate rejects None memory_id")


def test_gate_rejects_extra_payload_fields():
    """Rule 7: payload fields not in schema must be rejected."""
    gate = EventGate()
    proposal = EventProposal(
        event_type='memory_store',
        tick=1,
        memory_id='mem4',
        coaccess_group_id=str(uuid.uuid4()),
        payload={'content': 'test', 'tier': 'episodic', 'extra_field': 'bad'},
    )
    result = gate.validate(proposal)
    assert result.accepted is False, "extra fields must be rejected"
    print("[PASS] gate rejects extra payload fields")


def test_gate_accepts_valid_proposal():
    """EventGate must accept fully valid proposal."""
    gate = EventGate()
    proposal = EventProposal(
        event_type='memory_store',
        tick=1,
        memory_id='mem5',
        coaccess_group_id=str(uuid.uuid4()),
        payload={'content': 'hello', 'tier': 'episodic'},
    )
    result = gate.validate(proposal)
    assert result.accepted is True, f"valid proposal rejected: {result.reason}"
    print("[PASS] gate accepts valid proposal")


def test_hermes_bridge_create_proposal():
    """HermesBridge.create_proposal() creates a valid EventProposal."""
    with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
        path = f.name
    try:
        engine = MCRRuntimeEngine(wal_path=path)
        bridge = HermesBridge(engine)
        p = bridge.create_proposal(
            event_type='memory_store',
            tick=99,  # ignored
            memory_id='mem_test',
            coaccess_group_id=str(uuid.uuid4()),
            payload={'content': 'test', 'tier': 'episodic'},
            justification='unit test',
        )
        assert isinstance(p, EventProposal)
        assert p.event_type == 'memory_store'
        assert p.memory_id == 'mem_test'
        assert p.tick == 99  # kept as provided
        print("[PASS] HermesBridge.create_proposal works")
    finally:
        os.unlink(path)


def test_hermes_bridge_submit_proposal_via_gate():
    """submit_proposal() routes through EventGate — invalid proposals are rejected."""
    with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
        path = f.name
    try:
        engine = MCRRuntimeEngine(wal_path=path)
        bridge = HermesBridge(engine)

        # Invalid proposal (bad event_type)
        bad = EventProposal(
            event_type='NOT_REAL',
            tick=1,
            memory_id=None,
            coaccess_group_id=str(uuid.uuid4()),
            payload={},
        )
        result = bridge.submit_proposal(bad)
        assert result.accepted is False, "invalid proposal must be rejected by gate"

        # Valid proposal must be accepted
        good = EventProposal(
            event_type='memory_store',
            tick=1,
            memory_id='mem_valid',
            coaccess_group_id=str(uuid.uuid4()),
            payload={'content': 'test', 'tier': 'episodic'},
        )
        result2 = bridge.submit_proposal(good)
        assert result2.accepted is True, "valid proposal must be accepted"
        print("[PASS] HermesBridge.submit_proposal enforces gate")
    finally:
        os.unlink(path)


def test_engine_emits_through_gate():
    """engine.emit() creates event through gate and WAL appends it."""
    with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
        path = f.name
    try:
        engine = MCRRuntimeEngine(wal_path=path)
        engine.emit(
            event_type='memory_store',
            memory_id='emit1',
            coaccess_group_id=str(uuid.uuid4()),
            payload={'content': 'hello', 'tier': 'episodic'},
        )
        assert engine.wal.len() == 1, f"expected 1 WAL event, got {engine.wal.len()}"
        assert 'emit1' in engine.state.memory, "event must be in state"
        print("[PASS] engine.emit() works through gate")
    finally:
        os.unlink(path)


def test_engine_tick_authority():
    """Engine.emit_raw() must override any tick provided by event source."""
    with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
        path = f.name
    try:
        engine = MCRRuntimeEngine(wal_path=path)

        # Create event with incorrect tick (simulating LLM assigning wrong tick)
        from runtime.events import MCREvent
        bad_tick_event = MCREvent(
            event_id='fake-id',
            event_type='memory_store',
            tick=9999,  # wrong tick
            memory_id='x',
            coaccess_group_id=str(uuid.uuid4()),
            payload={'content': 'y', 'tier': 'episodic'},
            timestamp=time.time(),
            replay_hash='',
        )
        engine.emit_raw(bad_tick_event)

        # Engine must have corrected tick=1
        assert engine.wal.get_all()[0].tick == 1, f"Engine must override tick, got {engine.wal.get_all()[0].tick}"
        print("[PASS] engine tick authority enforced")
    finally:
        os.unlink(path)


def test_engine_does_not_mutate_callers_event():
    """emit_raw() must not mutate the caller's event object."""
    with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
        path = f.name
    try:
        engine = MCRRuntimeEngine(wal_path=path)
        from runtime.events import MCREvent
        original = MCREvent(
            event_id='orig-id',
            event_type='memory_store',
            tick=5,  # will be overridden
            memory_id='orig_mem',
            coaccess_group_id=str(uuid.uuid4()),
            payload={'content': 'orig', 'tier': 'episodic'},
            timestamp=1.0,
            replay_hash='',
        )
        original_replay_hash_before = original.compute_replay_hash()
        engine.emit_raw(original)

        # Caller event must NOT have been mutated by emit_raw
        assert original.tick == 5, f"caller's event.tick must not be mutated, got {original.tick}"
        assert original.replay_hash == '', f"caller's event.replay_hash must not be set, got '{original.replay_hash}'"
        assert original.compute_replay_hash() == original_replay_hash_before, "caller's hash must not change"
        print("[PASS] engine.emit_raw() does not mutate caller event")
    finally:
        os.unlink(path)


def test_is_valid_uuid():
    """is_valid_uuid() returns correct answers for valid/invalid inputs."""
    assert is_valid_uuid('550e8400-e29b-41d4-a716-446655440000') is True
    assert is_valid_uuid('not-a-uuid') is False
    assert is_valid_uuid('') is False
    assert is_valid_uuid(None) is False
    assert is_valid_uuid(123) is False
    print("[PASS] is_valid_uuid correct")


if __name__ == '__main__':
    test_gate_rejects_unknown_event_type()
    test_gate_rejects_missing_payload_fields()
    test_gate_rejects_forbidden_fields()
    test_gate_rejects_invalid_coaccess_group_id()
    test_gate_rejects_empty_memory_id()
    test_gate_rejects_none_memory_id()
    test_gate_rejects_extra_payload_fields()
    test_gate_accepts_valid_proposal()
    test_hermes_bridge_create_proposal()
    test_hermes_bridge_submit_proposal_via_gate()
    test_engine_emits_through_gate()
    test_engine_tick_authority()
    test_engine_does_not_mutate_callers_event()
    test_is_valid_uuid()
    print("\n=== All Bridge/Gate tests PASSED ===")