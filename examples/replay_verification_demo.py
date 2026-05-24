"""
MCR Replay Verification Demo — examples/replay_verification_demo.py

Demonstrates MCR's core guarantee:
  original runtime state == replayed runtime state

Run:
    python examples/replay_verification_demo.py

No external LLM API required. No network access. Runs in ~1 second.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.engine import MCRRuntimeEngine
from runtime.replay_verifier import ReplayVerifier
from runtime.state import SystemState


def run_and_verify():
    """
    Run 10 ticks with mixed events, then verify:
      runtime_state == replay(WAL)
    """
    wal_path = "/tmp/mcr_replay_demo_wal.jsonl"

    engine = MCRRuntimeEngine(wal_path=wal_path)
    verifier = ReplayVerifier()
    initial_state = engine.state.clone()

    # Emit 10 events across different types
    operations = [
        ("memory_store",  "A", "gid-001", {"content": "First memory item", "tier": "episodic"}),
        ("memory_store",  "B", "gid-001", {"content": "Second memory item", "tier": "episodic"}),
        ("memory_store",  "C", "gid-002", {"content": "Third memory item",  "tier": "episodic"}),
        ("memory_access", "A", "gid-001", {}),
        ("memory_access", "B", "gid-001", {}),
        ("memory_store",  "D", "gid-003", {"content": "Fourth memory item", "tier": "episodic"}),
        ("memory_archive","A", "gid-001", {"reason": "consolidated"}),
        ("memory_access", "C", "gid-002", {}),
        ("memory_access", "D", "gid-003", {}),
        ("memory_purge",  "B", "gid-001", {}),
    ]

    for evt_type, mem_id, coaccess_id, payload in operations:
        engine.emit(evt_type, mem_id, coaccess_id, payload)

    runtime_state = engine.state
    result = verifier.verify(runtime_state, initial_state, engine.wal)

    return result


def main():
    print("=" * 60)
    print("MCR Replay Verification Demo")
    print("=" * 60)

    result = run_and_verify()

    print()
    print(f"  event_count:        {result['wal_length']}")
    print(f"  runtime_tick:       {result['runtime_tick']}")
    print(f"  replay_tick:        {result['replay_tick']}")
    print(f"  runtime_mem:        {result['runtime_mem']}")
    print(f"  replay_mem:         {result['replay_mem']}")
    print(f"  runtime_hash:       {result['runtime_hash'][:20]}...")
    print(f"  replay_hash:        {result['replay_hash'][:20]}...")
    print(f"  wal_hash:           {result['wal_hash'][:20]}...")
    print()
    print(f"  verification:       {'PASS ✓' if result['match'] else 'FAIL ✗'}")
    if not result['match']:
        print(f"  reason:             {result['reason']}")
        print(f"  detail:             {result['detail']}")

    print()
    print("=" * 60)
    if result['match']:
        print("RESULT: PASS — original runtime state == replayed state")
    else:
        print("RESULT: FAIL — state divergence detected")
    print("=" * 60)

    return result['match']


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)