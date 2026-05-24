"""
library_usage.py — MCR v0.9.4
Demonstrates using MCR as a library: create runtime, append events, inspect state, verify replay.
"""
import sys, os
from pathlib import Path

# Ensure runtime is importable from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.engine import MCRRuntimeEngine
from runtime.replay_verifier import ReplayVerifier


def main():
    print("=== MCR Library Usage Demo ===\n")

    # 1. Create runtime with isolated WAL
    wal_path = "/tmp/mcr_library_demo.wal.jsonl"
    Path(wal_path).unlink(missing_ok=True)

    engine = MCRRuntimeEngine(wal_path=wal_path)
    initial_state = engine.state.clone()
    print("[1/4] Runtime created")
    print(f"    tick={engine.state.tick}, memory_items={len(engine.state.memory)}")

    # 2. Append memory events via emit()
    events = [
        ("memory_store", "lib-mem-001", "lib-group-001", {"content": "Project kickoff", "tier": "episodic"}),
        ("memory_store", "lib-mem-002", "lib-group-001", {"content": "API spec defined", "tier": "episodic"}),
        ("memory_access", "lib-mem-001", "lib-group-001", {}),
    ]

    for evt_type, mem_id, coaccess_id, payload in events:
        engine.emit(evt_type, mem_id, coaccess_id, payload)

    print(f"\n[2/4] Events appended")
    print(f"    Runtime memory items: {len(engine.state.memory)}")
    for mid, minfo in engine.state.memory.items():
        print(f"    - {mid}: {minfo.get('content', '')}")

    # 3. Inspect state
    state = engine.state
    print(f"\n[3/4] State snapshot")
    print(f"    tick:           {state.tick}")
    print(f"    memory items:   {len(state.memory)}")
    print(f"    access_history: {len(state.access_history)}")
    print(f"    state hash:     {state.hash()[:16]}...")

    # 4. Replay verification (G2)
    verifier = ReplayVerifier()
    result = verifier.verify(state, initial_state, engine.wal)

    print(f"\n[4/4] Replay verification")
    print(f"    runtime hash:  {result['runtime_hash'][:16]}...")
    print(f"    replay hash:   {result['replay_hash'][:16]}...")
    print(f"    WAL events:    {result['wal_length']}")

    if result["match"]:
        print("\n    Replay verification: PASS")
        print("\n=== MCR can be used as a library ===")
        return 0
    else:
        print(f"\n    Replay verification: FAIL — {result['reason']}")
        return 1


if __name__ == "__main__":
    sys.exit(main())