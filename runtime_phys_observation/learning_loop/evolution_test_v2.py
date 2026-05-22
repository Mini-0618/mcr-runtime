#!/usr/bin/env python3
"""
MCR Evolution Test v2 — Force Episodic Promotion
================================================
Same as v1 but with enough memory pressure to force episodic promotion,
so all 3 channels (working/episodic/semantic) are active and can learn.
"""
import sys, os, random, shutil, json
sys.path.insert(0, '/home/minimak/mcr/stable')
sys.path.insert(0, '/home/minimak/mcr/runtime_phys_observation/phase_IV_B_compaction')
sys.path.insert(0, '/home/minimak/mcr/runtime_phys_observation/phase_IV_A_adaptation')

from semantic_compaction import CompactionRuntime
from adaptive_policy import AdaptivePolicy

TASK_QUERIES = ["python_gc","sql_query","docker_runtime","wal_replay",
                 "semantic_search","crash_recovery","network_protocol","file_system"]

# 5 memories per topic = 40 total > MAX_WORKING=10 → forces episodic promotion
TOPIC_CONTENT = {
    "python_gc": [
        ("Python GC uses reference counting and generational collection", ["gc","python","memory"], 0.6),
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

def populate(cr):
    tick = 0
    for topic, memories in TOPIC_CONTENT.items():
        for content, tags, importance in memories:
            cr.store(content, memory_type="episodic", importance=importance,
                    tags=tags, current_tick=tick)
            tick += 5  # faster ticks to trigger LRU promotion
    cr._lm.try_flush(tick)

def oracle_relevance(query, results):
    if not results:
        return False, "empty"
    q_word = query.split("_")[0].lower()
    for r in results:
        content = r.get("content", "").lower()
        if q_word in content:
            return True, r.get("layer", "unknown")
    return False, results[0].get("layer", "unknown") if results else "unknown"

class EvolutionRuntime:
    def __init__(self, root: str):
        self._cr = CompactionRuntime(root)
        self._ap = AdaptivePolicy(root)
        self._tick = 0
        self._feedback_log = []

    def retrieve(self, query: str, max_results: int = 5) -> list:
        results = self._cr.retrieve(
            query, current_goal="evolution_test",
            current_tick=self._tick, max_results=max_results
        )
        if not results:
            return results

        weights = self._ap.get_weights()
        for r in results:
            ch = r.get("layer", "episodic")
            r["_raw_score"] = r.get("retrieval_score", 0.0)
            r["retrieval_score"] = r["_raw_score"] * weights.get(ch, 1.0)
        results.sort(key=lambda x: x["retrieval_score"], reverse=True)

        was_useful, primary_layer = oracle_relevance(query, results)
        self._ap.record_retrieval_feedback(
            channel=primary_layer,
            relevance=1.0 if was_useful else 0.0,
            was_useful=was_useful
        )
        self._feedback_log.append({
            "tick": self._tick, "query": query,
            "primary_layer": primary_layer,
            "was_useful": was_useful,
        })
        return results

    def tick(self):
        self._tick += 1
        self._cr.tick()
        self._ap.tick(self._tick)

    @property
    def episodic(self): return self._cr.episodic
    @property
    def working(self): return self._cr.working

    def get_weights(self): return self._ap.get_weights()
    def get_adaptation_count(self): return self._ap.get_adaptation_count()

def run(n_episodes=400, seed=42):
    random.seed(seed)
    mcr_root = f"/tmp/mcr_evolution_v2_{seed}"
    if os.path.exists(mcr_root): shutil.rmtree(mcr_root)

    er = EvolutionRuntime(mcr_root)
    populate(er._cr)

    print(f"{'Ep':>4} {'Tick':>5} {'W':>3} {'E':>3} {'A':>3}  {'adapt':>5}  "
          f"{'W_wt':>6} {'E_wt':>6} {'S_wt':>6}  {'useful%':>7}")
    print("-" * 75)

    for ep in range(n_episodes):
        q = TASK_QUERIES[ep % len(TASK_QUERIES)]
        er.retrieve(q, max_results=4)
        er.tick()

        if ep % 40 == 0 or ep < 3:
            wts = er.get_weights()
            adapt = er.get_adaptation_count()
            W,E,S = len(er.working), len(er.episodic), len(er._cr.semantic)
            recent = er._feedback_log[-40:] if len(er._feedback_log) >= 40 else er._feedback_log
            useful_pct = 100 * sum(1 for fb in recent if fb["was_useful"]) / max(1, len(recent))
            print(f"{ep:>4} {er._tick:>5} {W:>3} {E:>3} {S:>3}  {adapt:>5}  "
                  f"{wts.get('working',0):>6.3f} {wts.get('episodic',0):>6.3f} {wts.get('semantic',0):>6.3f}  "
                  f"{useful_pct:>6.1f}%")

    wts = er.get_weights()
    total = len(er._feedback_log)
    useful = sum(1 for fb in er._feedback_log if fb["was_useful"])
    adapt = er.get_adaptation_count()

    # Per-channel feedback breakdown
    channel_stats = {}
    for fb in er._feedback_log:
        ch = fb["primary_layer"]
        if ch not in channel_stats:
            channel_stats[ch] = {"total": 0, "useful": 0}
        channel_stats[ch]["total"] += 1
        if fb["was_useful"]:
            channel_stats[ch]["useful"] += 1

    print(f"\n{'='*75}")
    print(f"EVOLUTION v2 RESULTS ({n_episodes} episodes)")
    print(f"{'='*75}")
    print(f"  Total retrievals:       {total}")
    print(f"  Useful retrievals:     {useful} ({100*useful/max(1,total):.1f}%)")
    print(f"  Adaptation events:    {adapt}")
    print(f"\n  Channel breakdown:")
    for ch, stats in sorted(channel_stats.items()):
        pct = 100*stats["useful"]/max(1,stats["total"])
        print(f"    {ch:>12}: {stats['total']:>4} total, {stats['useful']:>4} useful ({pct:>5.1f}%)")
    print(f"\n  Final weights:")
    for ch, w in sorted(wts.items()):
        delta = w - 1.0
        arrow = "↑" if delta > 0.01 else "↓" if delta < -0.01 else "→"
        print(f"    {ch:>12}: {w:.4f} ({arrow} {delta:+.4f})")

    G0 = total > 0
    G1 = adapt > 0
    G2 = any(abs(w - 1.0) > 0.01 for w in wts.values())
    G3 = useful > 0 and adapt > 0 and len(channel_stats) >= 2  # at least 2 channels active

    print(f"\nVERDICT:")
    print(f"  G0 Integration:      {'✅' if G0 else '❌'}")
    print(f"  G1 Feedback fired:   {'✅' if G1 else '❌'}")
    print(f"  G2 Weight diverge:   {'✅' if G2 else '❌'}")
    print(f"  G3 Multi-channel:    {'✅' if G3 else '❌'}")

    print(f"\n{'='*75}")
    if G0 and G1 and G2 and G3:
        print(f"✅ MCR EVOLVED — multi-channel learning confirmed")
    else:
        print(f"❌ MCR: G0={G0} G1={G1} G2={G2} G3={G3}")
    print(f"{'='*75}")

    shutil.rmtree(mcr_root)

if __name__ == "__main__":
    print("MCR EVOLUTION v2 — Force episodic promotion")
    print("="*75)
    run(400, seed=42)
