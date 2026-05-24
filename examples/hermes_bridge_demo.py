"""
Hermes Bridge Minimal Demo — examples/hermes_bridge_demo.py

Demonstrates how Hermes Bridge connects an LLM to the MCR runtime:
  mock LLM output → parse proposals → EventGate validates → WAL → Reducer

This is NOT an AGI. This is an integration adapter.

Run:
    python examples/hermes_bridge_demo.py

No external LLM API required. Uses a mock Hermes response.
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.engine import MCRRuntimeEngine
from runtime.hermes_bridge import HermesBridge


MOCK_HERMES_RESPONSE = """
[
  {
    "event_type": "memory_store",
    "memory_id": "mock-task-001",
    "coaccess_group_id": "550e8400-e29b-41d4-a716-446655440000",
    "payload": {"content": "Review Q1 sprint goals", "tier": "episodic"},
    "justification": "User mentioned Q1 goals in conversation"
  },
  {
    "event_type": "memory_store",
    "memory_id": "mock-task-002",
    "coaccess_group_id": "550e8400-e29b-41d4-a716-446655440000",
    "payload": {"content": "Schedule team sync next week", "tier": "episodic"},
    "justification": "Action item from conversation"
  },
  {
    "event_type": "memory_access",
    "memory_id": "mock-task-001",
    "coaccess_group_id": "550e8400-e29b-41d4-a716-446655440000",
    "payload": {},
    "justification": "Retrieving task for context"
  }
]
"""


def main():
    print("=" * 60)
    print("Hermes Bridge v0.1 — Minimal Integration Demo")
    print("=" * 60)

    # ── 1. Create engine + bridge ──────────────────────────────────
    print("\n[1] Initialize runtime + Hermes Bridge...")
    wal_path = "/tmp/mcr_bridge_demo_wal.jsonl"
    Path(wal_path).unlink(missing_ok=True)
    engine = MCRRuntimeEngine(wal_path=wal_path)
    bridge = HermesBridge(engine)
    print("  ✓ Engine created")
    print("  ✓ Hermes Bridge attached")

    # ── 2. Show state snapshot (what LLM sees) ───────────────────────
    print("\n[2] State snapshot for LLM context...")
    snapshot = bridge.get_state_snapshot()
    for k, v in snapshot.items():
        print(f"  {k}: {v}")
    print("  ✓ Snapshot generated (access_history capped at 20)")

    # ── 3. Parse mock LLM output → proposals ────────────────────────
    print("\n[3] Parse mock LLM output → EventProposal list...")
    proposals = bridge.llm_to_proposals(MOCK_HERMES_RESPONSE)
    print(f"  ✓ Parsed {len(proposals)} proposals from LLM output")

    for i, p in enumerate(proposals):
        print(f"    [{i+1}] event_type={p.event_type}, memory_id={p.memory_id}, coaccess_group_id={p.coaccess_group_id[:8]}...")

    # ── 4. Submit proposals through EventGate ───────────────────────
    print("\n[4] Submit proposals through EventGate (validation)...")
    results = bridge.submit_proposals(proposals)

    accepted = [r for r in results if r.accepted]
    rejected = [r for r in results if not r.accepted]

    for i, r in enumerate(results):
        status = "ACCEPTED" if r.accepted else f"REJECTED ({r.reason})"
        print(f"    [{i+1}] {status}")

    print(f"\n  Summary: {len(accepted)} accepted, {len(rejected)} rejected")

    # ── 5. Inspect final state ──────────────────────────────────────
    print("\n[5] Final runtime state...")
    state = engine.state
    print(f"  tick:             {state.tick}")
    print(f"  memory items:     {len(state.memory)}")
    print(f"  WAL length:       {state.wal_length}")
    print(f"  access_history:   {len(state.access_history)}")
    print(f"  coaccess_graph:   {len(state.coaccess_graph)} nodes")

    for mid, minfo in state.memory.items():
        print(f"    {mid}: tier={minfo['tier']}, created_tick={minfo['created_tick']}")

    print("\n  ✓ All events processed through bridge → event_gate → WAL → reducer")

    # ── 6. Verify replay consistency ─────────────────────────────────
    print("\n[6] G2 replay verification...")
    from runtime.replay_verifier import ReplayVerifier
    verifier = ReplayVerifier()
    # Reload WAL from disk to simulate fresh load
    engine_verify = MCRRuntimeEngine(wal_path=wal_path)
    initial_state = engine_verify.state.clone()
    result = verifier.verify(engine.state, initial_state, engine.wal)

    if result['match']:
        print("  ✓ G2 VERIFICATION PASSED — runtime == replayed")
    else:
        print(f"  ✗ G2 VERIFICATION FAILED: {result['reason']} — {result['detail']}")

    print("\n" + "=" * 60)
    print("Hermes Bridge demo complete.")
    print("Note: This is an integration adapter, NOT an AGI.")
    print("=" * 60)

    return result['match']


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)