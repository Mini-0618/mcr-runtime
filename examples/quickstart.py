"""
MCR Quickstart Demo — examples/quickstart.py

Demonstrates the complete MCR event-sourced runtime loop:
1. create runtime
2. append memory events
3. retrieve and inspect state
4. replay WAL
5. verify replay consistency (G2)

Run:
    python examples/quickstart.py

No external LLM API required. No network access. Runs in ~1 second.
"""
import sys
import os

# Add project root to path so examples can import runtime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.engine import MCRRuntimeEngine
from runtime.replay_verifier import ReplayVerifier
from runtime.state import SystemState
from pathlib import Path


def main():
    print("=" * 60)
    print("MCR Quickstart — Event-Sourced Memory Runtime Demo")
    print("=" * 60)

    # ── 1. Create runtime ────────────────────────────────────────
    print("\n[1] Create runtime...")
    wal_path = "/tmp/mcr_quickstart_wal.jsonl"
    # Clean WAL so each run starts fresh — residual events from previous runs
    # would cause wal_length mismatch in G2 verification.
    Path(wal_path).unlink(missing_ok=True)
    engine = MCRRuntimeEngine(wal_path=wal_path)
    verifier = ReplayVerifier()

    # Save clean initial state for replay verification
    initial_state = engine.state.clone()
    print(f"  tick={engine.state.tick}, memory items={len(engine.state.memory)}")
    print("  [OK] Runtime created")

    # ── 2. Append memory events ───────────────────────────────────
    print("\n[2] Append memory events...")

    events = [
        ("memory_store", "mem-alpha",  "group-001", {"content": "Project alpha milestone reached", "tier": "episodic"}),
        ("memory_store", "mem-beta",   "group-001", {"content": "Beta release delayed by 1 week",  "tier": "episodic"}),
        ("memory_store", "mem-gamma",  "group-002", {"content": "User research session completed", "tier": "episodic"}),
        ("memory_access", "mem-alpha", "group-001", {}),
        ("memory_access", "mem-beta",  "group-001", {}),
    ]

    for evt_type, mem_id, coaccess_id, payload in events:
        event = engine.emit(evt_type, mem_id, coaccess_id, payload)
        print(f"  tick={event.tick}  {evt_type:16s}  memory_id={mem_id}")

    print(f"  [OK] {len(events)} events emitted")

    # ── 3. Inspect state ───────────────────────────────────────────
    print("\n[3] Inspect current state...")
    state = engine.state
    print(f"  tick:          {state.tick}")
    print(f"  memory items:  {len(state.memory)}")
    print(f"  WAL length:    {state.wal_length}")
    print(f"  access_history:{len(state.access_history)}")
    print(f"  coaccess_graph:{len(state.coaccess_graph)} nodes")
    print(f"  state hash:    {state.hash()[:16]}...")

    for mid, minfo in state.memory.items():
        print(f"    {mid}: tier={minfo['tier']}, created_tick={minfo['created_tick']}")

    # ── 4. Replay WAL ──────────────────────────────────────────────
    print("\n[4] Replay WAL from initial state...")
    replayed_state = verifier.replay(initial_state, engine.wal)
    print(f"  replayed tick:          {replayed_state.tick}")
    print(f"  replayed memory items:  {len(replayed_state.memory)}")
    print(f"  replayed access_history:{len(replayed_state.access_history)}")
    print(f"  replayed state hash:    {replayed_state.hash()[:16]}...")
    print("  [OK] WAL replayed")

    # ── 5. Verify replay consistency ───────────────────────────────
    print("\n[5] Verify G2 consistency (original == replayed)...")
    result = verifier.verify(state, initial_state, engine.wal)

    print(f"  runtime hash:   {result['runtime_hash'][:16]}...")
    print(f"  replay hash:    {result['replay_hash'][:16]}...")
    print(f"  WAL event count:{result['wal_length']}")
    print(f"  WAL hash:       {result['wal_hash'][:16]}...")

    if result['match']:
        print("\n  [OK] G2 VERIFICATION PASSED")
        print("  Runtime state == Replayed state (deterministic replay confirmed)")
    else:
        print(f"\n  [FAIL] G2 VERIFICATION FAILED: {result['reason']} -- {result['detail']}")

    print("\n" + "=" * 60)
    print("Quickstart complete. MCR runtime is working correctly.")
    print("=" * 60)

    return result['match']


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)