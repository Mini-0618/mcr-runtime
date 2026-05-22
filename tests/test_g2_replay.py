"""
G2 Replay Equivalence Test
验证: runtime_state == replay(WAL)
"""
import sys, os, random
sys.path.insert(0, '/home/minimak/mcr')

from runtime import MCRRuntimeEngine, SystemState, WAL
from runtime.replay_verifier import ReplayVerifier

RANDOM_SEED = 42


def random_memory_id():
    return f"mem_{random.randint(1000,9999)}"


def test_g2_replay():
    random.seed(RANDOM_SEED)
    print("=== G2 Replay Equivalence Test ===\n")

    # fresh WAL
    wal_path = "/home/minimak/mcr/.wal/test_events.jsonl"
    if os.path.exists(wal_path):
        os.remove(wal_path)

    engine = MCRRuntimeEngine(wal_path=wal_path)

    num_operations = 50
    for i in range(num_operations):
        op = random.choice(['store', 'access', 'store', 'access'])
        group_id = str(random.randint(1, 5))
        mem_id = random_memory_id()

        if op == 'store':
            engine.emit(
                event_type='memory_store',
                memory_id=mem_id,
                coaccess_group_id=group_id,
                payload={'content': f'content_{i}', 'tier': 'episodic'}
            )
        else:
            engine.emit(
                event_type='memory_access',
                memory_id=mem_id,
                coaccess_group_id=group_id,
                payload={}
            )

    # checkpoint every 10 ticks
    for t in [10, 20, 30, 40, 50]:
        engine.run(num_ticks=t - engine.tick_count, verify=True)

    runtime_state = engine.get_state()
    wal = engine.get_wal()

    print(f"\n--- Final State ---")
    print(f"tick: {runtime_state.tick}")
    print(f"memory items: {len(runtime_state.memory)}")
    print(f"access_history: {len(runtime_state.access_history)}")
    print(f"WAL events: {wal.len()}")

    # Tick monotonicity: WAL ticks must be strictly 1..N with no gaps.
    # Engine owns tick authority; if LLM ever assigns ticks directly,
    # WAL ticks will diverge from engine.tick_count.
    events = wal.get_all()
    for i, evt in enumerate(events):
        expected = i + 1
        if evt.tick != expected:
            raise AssertionError(
                f"TICK MONOTONICITY VIOLATION: WAL event index {i} has tick={evt.tick}, "
                f"expected {expected}. LLM may be assigning ticks."
            )
    print(f"[tick] WAL ticks 1..{len(events)} monotonically sequential — OK")

    # G2 verification
    verifier = ReplayVerifier()
    initial = SystemState.empty()

    result = verifier.verify(runtime_state, initial, wal)

    print(f"\n--- G2 Verification ---")
    print(f"match: {result['match']}")
    print(f"runtime_hash: {result['runtime_hash']}")
    print(f"replay_hash:  {result['replay_hash']}")
    print(f"wal_length: {result['wal_length']}")
    print(f"wal_hash:   {result['wal_hash']}")

    if result['match']:
        print("\n✅ G2-COMPLETE: runtime_state == replay(WAL)")
    else:
        print("\n❌ G2 VIOLATION DETECTED")
        raise AssertionError(f"G2 replay mismatch: {result}")

    return result


if __name__ == '__main__':
    result = test_g2_replay()
