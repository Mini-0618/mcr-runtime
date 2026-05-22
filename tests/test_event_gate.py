"""
Event Gate + Hermes Bridge Integration Test
验证:
1. EventGate validates proposals correctly
2. HermesBridge parses LLM output to proposals
3. Accepted events go through reducer → WAL
4. Rejected events are blocked
"""
import sys, os
sys.path.insert(0, '/home/minimak/mcr')

from runtime import (
    MCRRuntimeEngine, EventGate, HermesBridge,
    EventProposal, ValidationResult
)


def test_event_gate_validation():
    print("=== Event Gate Validation Tests ===\n")

    gate = EventGate()

    # Test 1: valid proposal
    valid = EventProposal(
        event_type="memory_store",
        tick=1,
        memory_id="mem_001",
        coaccess_group_id="550e8400-e29b-41d4-a716-446655440000",
        payload={"content": "test", "tier": "episodic"},
        justification="storing test memory"
    )
    result = gate.validate(valid)
    print(f"[1] Valid proposal: {result.accepted} — {result.reason}")

    # Test 2: invalid event type
    invalid_type = EventProposal(
        event_type="INVALID_TYPE",
        tick=2,
        memory_id="mem_002",
        coaccess_group_id="550e8400-e29b-41d4-a716-446655440000",
        payload={},
    )
    result2 = gate.validate(invalid_type)
    print(f"[2] Invalid type: {result2.accepted} — {result2.reason}")

    # Test 3: missing required field
    missing_field = EventProposal(
        event_type="memory_store",
        tick=3,
        memory_id="mem_003",
        coaccess_group_id="550e8400-e29b-41d4-a716-446655440000",
        payload={},  # missing content and tier
    )
    result3 = gate.validate(missing_field)
    print(f"[3] Missing field: {result3.accepted} — {result3.reason}")

    # Test 4: forbidden field
    forbidden = EventProposal(
        event_type="memory_store",
        tick=4,
        memory_id="mem_004",
        coaccess_group_id="550e8400-e29b-41d4-a716-446655440000",
        payload={"content": "test", "tier": "episodic", "state": "corrupted"},
    )
    result4 = gate.validate(forbidden)
    print(f"[4] Forbidden field: {result4.accepted} — {result4.reason}")

    # Test 5: non-monotonic tick
    nonmono = EventProposal(
        event_type="memory_store",
        tick=1,  # same as before
        memory_id="mem_005",
        coaccess_group_id="550e8400-e29b-41d4-a716-446655440000",
        payload={"content": "test", "tier": "episodic"},
    )
    result5 = gate.validate(nonmono)
    print(f"[5] Non-monotonic tick: {result5.accepted} — {result5.reason}")


def test_hermes_bridge():
    print("\n=== Hermes Bridge Tests ===\n")

    # clean WAL
    wal_path = "/home/minimak/mcr/.wal/test_bridge.jsonl"
    if os.path.exists(wal_path):
        os.remove(wal_path)

    engine = MCRRuntimeEngine(wal_path=wal_path)
    bridge = HermesBridge(engine)

    # Test: LLM output parsing
    llm_output = '''
    {
      "proposals": [
        {
          "event_type": "memory_store",
          "tick": 1,
          "memory_id": "mem_llm_001",
          "coaccess_group_id": "550e8400-e29b-41d4-a716-446655440000",
          "payload": {"content": "from LLM", "tier": "episodic"},
          "justification": "initial memory store"
        },
        {
          "event_type": "memory_access",
          "tick": 2,
          "memory_id": "mem_llm_001",
          "coaccess_group_id": "550e8400-e29b-41d4-a716-446655440000",
          "payload": {},
          "justification": "accessing stored memory"
        }
      ]
    }
    '''

    proposals = bridge.llm_to_proposals(llm_output)
    print(f"[1] Parsed {len(proposals)} proposals from LLM output")

    # Submit proposals through bridge
    results = bridge.submit_proposals(proposals)
    accepted = [r for r in results if r.accepted]
    rejected = [r for r in results if not r.accepted]
    print(f"[2] Accepted: {len(accepted)}, Rejected: {len(rejected)}")

    # Check WAL
    print(f"[3] WAL length: {engine.wal.len()}")
    print(f"[4] Memory items: {len(engine.state.memory)}")


def test_full_integration():
    print("\n=== Full Integration Test ===\n")

    wal_path = "/home/minimak/mcr/.wal/test_integration.jsonl"
    if os.path.exists(wal_path):
        os.remove(wal_path)

    engine = MCRRuntimeEngine(wal_path=wal_path)
    bridge = HermesBridge(engine)

    # Generate proposals via bridge API
    p1 = bridge.create_proposal(
        event_type="memory_store",
        tick=1,
        memory_id="mem_integ_1",
        coaccess_group_id=str(__import__('uuid').uuid4()),
        payload={"content": "integration test 1", "tier": "episodic"},
        justification="setup"
    )

    p2 = bridge.create_proposal(
        event_type="memory_store",
        tick=2,
        memory_id="mem_integ_2",
        coaccess_group_id=str(__import__('uuid').uuid4()),
        payload={"content": "integration test 2", "tier": "semantic"},
        justification="setup"
    )

    p3 = bridge.create_proposal(
        event_type="memory_access",
        tick=3,
        memory_id="mem_integ_1",
        coaccess_group_id=p1.coaccess_group_id,
        payload={},
        justification="access"
    )

    results = bridge.submit_proposals([p1, p2, p3])
    print(f"[1] Submitted 3 proposals: {len([r for r in results if r.accepted])} accepted")

    # G2 check
    from runtime.replay_verifier import ReplayVerifier
    verifier = ReplayVerifier()
    from runtime.state import SystemState

    result = verifier.verify(engine.state, SystemState.empty(), engine.wal)
    print(f"[2] G2 check: {result['match']}")
    print(f"[3] runtime_hash={result['runtime_hash']}, replay_hash={result['replay_hash']}")

    if result['match']:
        print("\n✅ FULL INTEGRATION: EventGate + HermesBridge + Reducer + WAL — G2 PASS")
    else:
        print("\n❌ G2 FAIL")


if __name__ == '__main__':
    test_event_gate_validation()
    test_hermes_bridge()
    test_full_integration()
