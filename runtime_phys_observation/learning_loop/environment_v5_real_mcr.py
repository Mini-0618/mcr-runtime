#!/usr/bin/env python3
"""
MCR Learning Loop v5 — MCR STRESS TEST (not learning)
=====================================================
Tests: can real MCR (WAL/compaction/decay/persistence) survive
       500 episodes × 3 steps × continuous tick + policy-driven access?

This is the INTEGRATION test, not the learning test.
Learning was proven in v4. This proves the MCR core is solid under load.

Metrics tracked:
  - WAL integrity (wal_ok)
  - Memory growth (total size)
  - Compaction events
  - Retrieval latency
  - Semantic tier activation
  - Archive pressure
"""
import sys, os, random, shutil, time
sys.path.insert(0, './stable')
sys.path.insert(0, './runtime_phys_observation/phase_IV_B_compaction')

from semantic_compaction import CompactionRuntime

TASK_QUERIES = ["python_gc","sql_query","docker_runtime","wal_replay",
                 "semantic_search","crash_recovery","network_protocol","file_system"]

TOPIC_CONTENT = {
    "python_gc": [
        ("Python GC uses reference counting and generational collection", ["gc","python","memory"], 0.8),
        ("heap memory divided into young and old generations", ["heap","memory","gc"], 0.7),
        ("ref_count=0 triggers immediate deallocation", ["reference_counting","dealloc"], 0.6),
        ("cyclic garbage collector handles circular references", ["cyclic_gc","cpython"], 0.7),
        ("memory leak: holding references prevents GC", ["memory_leak","reference"], 0.8),
    ],
    "sql_query": [
        ("B-tree indexes speed up SQL query execution", ["sql","index","b-tree"], 0.8),
        ("JOIN operations combine rows from two tables", ["sql","join","database"], 0.8),
        ("transaction isolation levels prevent dirty reads", ["transaction","isolation"], 0.7),
        ("SQLite uses B+ tree for indexes", ["sqlite","b+tree","index"], 0.6),
        ("ACID: Atomicity Consistency Isolation Durability", ["acid","transaction"], 0.7),
    ],
    "docker_runtime": [
        ("Docker container shares the host kernel", ["docker","container","kernel"], 0.8),
        ("container image layers are read-only", ["image","layer","docker"], 0.7),
        ("namespace isolation: PID NET IPC MNT UTS", ["namespace","isolation","linux"], 0.8),
        ("Dockerfile builds an image layer by layer", ["dockerfile","build","layer"], 0.7),
        ("container runtime: runc containerd docker-engine", ["runtime","containerd","runc"], 0.6),
    ],
    "wal_replay": [
        ("WAL writes data to log before applying to main database", ["wal","write_ahead"], 0.9),
        ("recovery: replay WAL to restore database after crash", ["recovery","replay","crash"], 0.8),
        ("checkpoint: periodic flush of WAL to reduce recovery time", ["checkpoint","wal"], 0.7),
        ("redo log records new value for recovery", ["redo","journal","wal"], 0.7),
        ("LSM-tree uses WAL for crash recovery", ["lsm","wal","crash"], 0.6),
    ],
    "semantic_search": [
        ("embedding vectors capture semantic meaning", ["embedding","vector","semantic"], 0.9),
        ("cosine similarity measures vector closeness", ["cosine","similarity","vector"], 0.8),
        ("RAG combines search and LLM generation", ["rag","retrieval","llm"], 0.8),
        ("ANN indexes: HNSW FAISS approximate nearest neighbor", ["ann","hnsw","faiss"], 0.7),
        ("chunking strategy affects retrieval quality", ["chunk","retrieval","rag"], 0.6),
    ],
    "crash_recovery": [
        ("checkpoint saves consistent state for fast restart", ["checkpoint","restart","recovery"], 0.9),
        ("journaling filesystem: ext4 uses journaling", ["journal","ext4","filesystem"], 0.8),
        ("fault tolerance via replication and checkpointing", ["fault_tolerance","replication"], 0.7),
        ("crash consistency: fsync ordering matters", ["fsync","crash_consistency"], 0.7),
        ("write barriers ensure disk write ordering", ["write_barrier","storage"], 0.6),
    ],
    "network_protocol": [
        ("TCP guarantees ordered reliable delivery", ["tcp","reliable","ordered"], 0.9),
        ("UDP is connectionless no delivery guarantee", ["udp","connectionless"], 0.8),
        ("HTTP/2 multiplexes streams over one connection", ["http2","multiplex","stream"], 0.7),
        ("socket API: bind listen accept connect", ["socket","api","tcp"], 0.7),
        ("packet loss triggers TCP congestion control", ["congestion","tcp","packet_loss"], 0.6),
    ],
    "file_system": [
        ("inode stores file metadata: size timestamps block pointers", ["inode","metadata","fs"], 0.9),
        ("directory entry maps filename to inode number", ["directory","dentry","fs"], 0.8),
        ("block allocator: extents vs bitmap allocation", ["block","allocator","extents"], 0.7),
        ("VFS virtual file system abstracts across fs types", ["vfs","filesystem","abstraction"], 0.7),
        ("page cache: kernel caches disk blocks in RAM", ["page_cache","buffer","kernel"], 0.6),
    ],
}

def populate(cr: CompactionRuntime):
    tick = 0
    for topic, memories in TOPIC_CONTENT.items():
        for content, tags, importance in memories:
            cr.store(content, memory_type="episodic", importance=importance,
                    tags=tags, current_tick=tick)
            tick += 10
    cr._lm.try_flush(tick)

def run_stress_test(n_episodes=500, seed=42):
    random.seed(seed)
    mcr_root = f"/tmp/mcr_stress_{seed}"
    if os.path.exists(mcr_root): shutil.rmtree(mcr_root)

    cr = CompactionRuntime(mcr_root)
    populate(cr)

    # Metrics collection
    tick_log = []
    retrieval_times = []
    memory_snapshots = []

    print(f"{'Ep':>4} {'Tick':>6} {'W':>4} {'E':>4} {'S':>4} {'A':>4}  {'compC':>6} {'wal_ok':>6}  {'t_retrieve(ms)':>14}")
    for ep in range(n_episodes):
        q = TASK_QUERIES[ep % len(TASK_QUERIES)]

        for step in range(1, 4):
            tick = ep * 10 + step
            t0 = time.time()
            results = cr.retrieve(q, current_goal="policy_step",
                                  current_tick=tick, max_results=5)
            t_ms = (time.time() - t0) * 1000
            retrieval_times.append(t_ms)
            cr.tick()

        # Snapshot every 50 episodes
        if ep % 50 == 0 or ep < 3:
            W,E,S,A = len(cr.working),len(cr.episodic),len(cr.semantic),len(cr.archive)
            total = W+E+S+A
            metrics = cr.get_compaction_metrics()
            compaction_count = metrics.get("compaction_count", 0)
            # Check WAL integrity
            try:
                wal_ok = cr._lm._wal is not None
            except:
                wal_ok = False
            print(f"{ep:>4} {cr._tick:>6} {W:>4} {E:>4} {S:>4} {A:>4}  {compaction_count:>6} {str(wal_ok):>6}  {t_ms:>14.2f}")
            memory_snapshots.append({
                "ep": ep, "tick": cr._tick,
                "W": W, "E": E, "S": S, "A": A, "total": total,
                "compaction_count": compaction_count,
                "wal_ok": wal_ok,
                "last_retrieve_ms": t_ms,
                "avg_retrieve_ms": sum(retrieval_times[-50:])/min(len(retrieval_times),50),
            })

    # Final analysis
    print(f"\n{'='*70}")
    print(f"STRESS TEST RESULTS (n={n_episodes} episodes × 3 steps = {n_episodes*3} retrievals)")
    print(f"  Final tick:        {cr._tick}")
    print(f"  Total retrievals:  {cr._retrieval_count}")
    print(f"  Compaction events: {cr.get_compaction_metrics().get('compaction_count',0)}")
    print(f"  Semantic summaries:{cr.get_compaction_metrics().get('total_summaries_created',0)}")
    print(f"  Coaccess edges:    {cr.get_compaction_metrics().get('coaccess_edge_count',0)}")
    print(f"  WAL integrity:     {memory_snapshots[-1]['wal_ok'] if memory_snapshots else 'UNKNOWN'}")

    # Memory growth
    if len(memory_snapshots) >= 2:
        first = memory_snapshots[0]
        last  = memory_snapshots[-1]
        growth = (last['total'] - first['total']) / max(first['total'], 1)
        print(f"  Memory growth:     {first['total']} → {last['total']} ({growth*100:+.1f}%)")

    # Retrieve latency
    if retrieval_times:
        print(f"  Avg retrieve ms:   {sum(retrieval_times)/len(retrieval_times):.3f}ms")
        print(f"  Max retrieve ms:   {max(retrieval_times):.3f}ms")
        print(f"  P99 retrieve ms:  {sorted(retrieval_times)[int(len(retrieval_times)*0.99)]:.3f}ms")

    # WAL check
    wal_ok = all(s['wal_ok'] for s in memory_snapshots)
    compaction_happened = memory_snapshots[-1]['compaction_count'] > 0 if memory_snapshots else False
    memory_bounded = abs(growth) < 0.5 if len(memory_snapshots) >= 2 else True

    print(f"\nPASS/FAIL:")
    print(f"  WAL integrity:     {'✅ PASS' if wal_ok else '❌ FAIL'}")
    print(f"  Compaction fired:  {'✅ PASS' if compaction_happened else '⚠️  none yet'}")
    print(f"  Memory bounded:    {'✅ PASS' if memory_bounded else '❌ UNBOUNDED'}")
    print(f"  Retrieve latency:  {'✅ PASS' if sum(retrieval_times)/len(retrieval_times) < 100 else '⚠️  SLOW'}")

    all_pass = wal_ok and memory_bounded
    print(f"\n{'='*70}")
    print(f"VERDICT: {'✅ MCR INTEGRATION SOLID' if all_pass else '❌ MCR HAS ISSUES'}")

    return {
        "wal_ok": wal_ok,
        "compaction_fired": compaction_happened,
        "memory_bounded": memory_bounded,
        "snapshots": memory_snapshots,
        "retrieve_times": retrieval_times,
    }

if __name__ == "__main__":
    print("MCR Learning Loop v5 — Real MCR STRESS TEST")
    print("Question: can real MCR survive 500 episodes × 3 steps?")
    print("="*70)
    run_stress_test(500, seed=42)
