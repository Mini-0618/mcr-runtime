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
    ops = ['store', 'access', 'store', 'access', 'archive', 'purge']
    for i in range(num_operations):
        op = random.choice(ops)
        group_id = str(random.randint(1, 5))
        mem_id = random_memory_id()

        if op == 'store':
            engine.emit(
                event_type='memory_store',
                memory_id=mem_id,
                coaccess_group_id=group_id,
                payload={'content': f'content_{i}', 'tier': 'episodic'}
            )
        elif op == 'archive':
            # archive a random previously stored memory if any exist
            if engine.state.memory:
                target = random.choice(list(engine.state.memory.keys()))
                engine.emit(
                    event_type='memory_archive',
                    memory_id=target,
                    coaccess_group_id=group_id,
                    payload={'reason': f'archive_{i}'}
                )
        elif op == 'purge':
            # purge a random memory if any exist
            if engine.state.memory:
                target = random.choice(list(engine.state.memory.keys()))
                engine.emit(
                    event_type='memory_purge',
                    memory_id=target,
                    coaccess_group_id=group_id,
                    payload={}
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
        remaining = t - engine.tick_count
        if remaining > 0:
            engine.run(num_ticks=remaining, verify=True)
        # if remaining <= 0, this checkpoint was already passed by the ops loop;
        # run(-N) is a no-op and would silently skip verification — guard against it

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
        # Explicit memory content verification.
        # equals() only compares memory.keys(), not item contents. A reducer bug that
        # stores wrong values (e.g., swapped content, wrong tier, stale created_tick)
        # would pass equals() since keys match. Verify exact memory item contents.
        replayed_state = verifier.replay(initial, wal)
        memory_ok = True
        if set(runtime_state.memory.keys()) != set(replayed_state.memory.keys()):
            memory_ok = False
        else:
            for k in runtime_state.memory:
                if runtime_state.memory[k] != replayed_state.memory[k]:
                    memory_ok = False
                    break
        if not memory_ok:
            print("\n❌ MEMORY_CONTENT_MISMATCH")
            raise AssertionError(
                f"memory item content mismatch: runtime={dict(runtime_state.memory)}, "
                f"replayed={dict(replayed_state.memory)}"
            )
        print("[memory] content integrity: PASS")

        # Explicit coaccess_graph edge integrity check.
        # equals() only compares coaccess_graph keys (not edge contents), so a shallow
        # copy bug in clone() or equals() would not be caught by G2 alone.
        # Verify that replayed coaccess_graph has identical edge sets to runtime.
        runtime_graph = runtime_state.coaccess_graph
        replayed_graph = replayed_state.coaccess_graph
        edges_ok = True
        if set(runtime_graph.keys()) != set(replayed_graph.keys()):
            edges_ok = False
        else:
            for k, runtime_neighbors in runtime_graph.items():
                replayed_neighbors = replayed_graph.get(k, set())
                if set(runtime_neighbors) != set(replayed_neighbors):
                    edges_ok = False
                    break
        if not edges_ok:
            print("\n❌ COACCESS_EDGE_MISMATCH")
            raise AssertionError(
                f"coaccess_graph edge divergence: runtime={dict(runtime_graph)}, "
                f"replayed={dict(replayed_graph)}"
            )
        print("[coaccess] edge integrity: PASS")
        print("\n✅ G2-COMPLETE: runtime_state == replay(WAL)")
    else:
        print("\n❌ G2 VIOLATION DETECTED")
        raise AssertionError(f"G2 replay mismatch: {result}")

    return result


if __name__ == '__main__':
    result = test_g2_replay()
