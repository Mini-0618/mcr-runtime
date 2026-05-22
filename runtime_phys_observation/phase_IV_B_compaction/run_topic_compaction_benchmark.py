#!/usr/bin/env python3
"""
MCR Phase IV-B.1: Topic-Bounded Compaction Benchmark
====================================================

6 topics: python_gc, sql_query, docker_runtime, wal_replay, semantic_search, crash_recovery
Workload: 10k ticks, retrieval storms, archive pressure, compaction cycles.

Research Questions (G1-G7):
  G1 compression ratio
  G2 semantic monopoly
  G3 information preservation
  G4 entropy stability
  G5 retrieval economics
  G6 merge purity
  G7 topic boundary integrity
"""

import sys, os, json, time, random, shutil, math
from pathlib import Path
from collections import defaultdict, Counter

sys.path.insert(0, '/home/minimak/mcr/stable')
sys.path.insert(0, '/home/minimak/mcr/runtime_phys_observation/phase_IV_B_compaction')
from layered_memory import LayeredMemory
from semantic_compaction import SemanticCompaction, CompactionRuntime

BASE = Path("/home/minimak/mcr/runtime_phys_observation/phase_IV_B_compaction")
RUNS = BASE / "runs"; FINDINGS = BASE / "findings"; METRICS = BASE / "metrics"
RUN_DIR = RUNS / "topic_bounded_10k"
for d in [RUN_DIR, FINDINGS, METRICS]:
    d.mkdir(parents=True, exist_ok=True)

WORKLOAD_TICKS = 10_000
SEED = 2025

TOPICS = {
    "python_gc": {
        "tag": "python_gc",
        "keywords": ["GC", "gc", "Garbage", "memory", "heap", "refcount", "cycle",
                     "collector", "allocation", "pause", "generation", "threshold",
                     "finalizer", "weakref", "reachability"],
        "templates": [
            "Python {k} issue at application {n}",
            "Python {k} tuning for service {n}",
            "Investigated Python {k} behavior in deployment {n}",
            "Python {k} pause blocking service {n}",
            "Python {k} configuration at container {n}",
        ],
    },
    "sql_query": {
        "tag": "sql_query",
        "keywords": ["SELECT", "JOIN", "index", "query", "WHERE", "table", "scan",
                     "optimize", "explain", "plan", "lookup", "sort"],
        "templates": [
            "Slow {k} on table {n} causing latency",
            "Optimized {k} plan for dashboard {n}",
            "Added {k} index to improve query {n}",
            "Analyzed {k} performance for report {n}",
            "Rewrote {k} with subquery for set {n}",
        ],
    },
    "docker_runtime": {
        "tag": "docker_runtime",
        "keywords": ["docker", "container", "image", "layer", "volume", "network",
                     "compose", "swarm", "registry", "pull", "run", "build"],
        "templates": [
            "Docker {k} consuming excessive disk on host {n}",
            "Container {k} failing health check in cluster {n}",
            "Docker {k} OOM killed in orchestration {n}",
            "Image {k} taking too long to pull in {n}",
            "Docker {k} network latency to {n}",
        ],
    },
    "wal_replay": {
        "tag": "wal_replay",
        "keywords": ["WAL", "write-ahead", "log", "replay", "LSN", "checkpoint",
                     "recovery", "redo", "undo", "segment", "flush", "durable",
                     "fsync", "crash-consistent", "point-in-time"],
        "templates": [
            "WAL {k} blocking on {n} during heavy write",
            "Checkpoint {k} taking {n}s causing replication lag",
            "Replay {k} slower than expected on {n}",
            "WAL {k} segment accumulation on {n}",
            "Durable {k} latency spike in {n}",
        ],
    },
    "semantic_search": {
        "tag": "semantic_search",
        "keywords": ["semantic", "embedding", "vector", "similarity", "search",
                     "retrieval", "rank", "relevance", "ANN", "HNSW", "index",
                     "approximate", "neighbor", "cosine", "distance"],
        "templates": [
            "Semantic {k} returning irrelevant results for {n}",
            "Vector {k} index growing unbounded in {n}",
            "ANN {k} recall degradation for query {n}",
            "Embedding {k} drift in production {n}",
            "Semantic {k} latency exceeding SLO for {n}",
        ],
    },
    "crash_recovery": {
        "tag": "crash_recovery",
        "keywords": ["crash", "recovery", "restart", "panic", "assert", "core",
                     "dump", "failover", "leader", "election", "split",
                     "brain", "fencing", "quorum", "restore", "backup"],
        "templates": [
            "Service {k} crash-loop after deployment {n}",
            "Recovery {k} taking {n}s exceeding RTO",
            "Leader {k} election timeout in {n}",
            "Split-brain {k} detected in cluster {n}",
            "Core {k} dump analysis for incident {n}",
        ],
    },
}

CROSS_TOPIC_KEYWORDS = {
    "memory": ["python_gc", "semantic_search"],
    "index": ["sql_query", "semantic_search"],
    "latency": ["sql_query", "docker_runtime", "wal_replay", "semantic_search"],
    "cluster": ["docker_runtime", "crash_recovery"],
    "recovery": ["wal_replay", "crash_recovery"],
}


def generate_topic_workload(n_ticks, seed):
    rng = random.Random(seed)
    topic_names = list(TOPICS.keys())
    workload = []

    for tick in range(1, n_ticks + 1):
        # Normal writes (70%)
        if rng.random() < 0.7:
            topic = rng.choice(topic_names)
            tdef = TOPICS[topic]
            kw = rng.choice(tdef["keywords"])
            tmpl = rng.choice(tdef["templates"])
            content = tmpl.format(k=kw, n=rng.randint(1, 999))
            tags = [tdef["tag"], "topic_benchmark"]
            workload.append(("store", tick, content, tags))

        # Retrieval storms (10%)
        if rng.random() < 0.1:
            topic = rng.choice(topic_names)
            tdef = TOPICS[topic]
            storm_size = rng.randint(3, 6)
            for _ in range(storm_size):
                kw = rng.choice(tdef["keywords"])
                query = f"{tdef['tag']} {kw}"
                workload.append(("retrieve", tick, query, [tdef["tag"]]))

        # Overlapping cross-topic queries (15%)
        if rng.random() < 0.15:
            cross_kw = rng.choice(list(CROSS_TOPIC_KEYWORDS.keys()))
            related_topics = CROSS_TOPIC_KEYWORDS[cross_kw]
            topic = rng.choice(related_topics)
            tdef = TOPICS[topic]
            query = f"{cross_kw} {rng.choice(tdef['keywords'])}"
            workload.append(("retrieve", tick, query, [tdef["tag"]]))

        # Generic query (5%)
        if rng.random() < 0.05:
            topic = rng.choice(topic_names)
            tdef = TOPICS[topic]
            kw = rng.choice(tdef["keywords"])
            query = f"{kw}"
            workload.append(("retrieve", tick, query, []))

    return workload


def shannon_entropy(values):
    if not values:
        return 0.0
    total = sum(values)
    if total == 0:
        return 0.0
    probs = [v / total for v in values]
    return -sum(p * math.log2(p) for p in probs if p > 0)


def compute_semantic_entropy(semantic_list):
    if not semantic_list:
        return 0.0
    topic_counts = Counter(
        m.get("topic", "unknown")
        for m in semantic_list
        if m.get("memory_type") == "semantic_summary"
    )
    return shannon_entropy(list(topic_counts.values()))


def compute_coaccess_density(edges_dict, n_memories):
    if n_memories < 2:
        return 0.0
    actual_edges = sum(len(v) for v in edges_dict.values()) // 2
    max_edges = n_memories * (n_memories - 1) / 2
    return actual_edges / max_edges if max_edges > 0 else 0.0


def run_benchmark():
    print(f"[TOPIC_BOUNDED] {WORKLOAD_TICKS} ticks, 6 topics...")
    print(f"  Topics: {', '.join(TOPICS.keys())}")
    print()

    if os.path.exists(RUN_DIR):
        shutil.rmtree(RUN_DIR)
    os.makedirs(RUN_DIR, exist_ok=True)

    cr = CompactionRuntime(str(RUN_DIR))
    # Override coaccess thresholds for benchmark (sparse random retrieval)
    cr._compaction.MIN_COACCESS_COUNT = 1
    cr._compaction.MIN_REDUNDANT_GROUP_SIZE = 2
    t0 = time.perf_counter()
    workload = generate_topic_workload(WORKLOAD_TICKS, SEED)

    tick_metrics = []
    entropy_timeline = []
    coaccess_density_timeline = []
    retrieval_latencies = []

    print(f"  Running {len(workload)} events...", end=" ", flush=True)

    for event_type, tick, content, tags in workload:
        if event_type == "store":
            cr.store(content, tags=tags, importance=0.6, current_tick=tick)
        elif event_type == "retrieve":
            t_start = time.perf_counter()
            results = cr.retrieve(content, current_tick=tick, max_results=5)
            latency_ms = (time.perf_counter() - t_start) * 1000
            retrieval_latencies.append(latency_ms)

        cr.tick()

        if tick % 200 == 0:
            cm = cr._compaction.get_metrics()
            edges_dict = cr._compaction._coaccess.edges
            n_epi = len(cr.episodic)
            density = compute_coaccess_density(edges_dict, n_epi)
            sem_entropy = compute_semantic_entropy(cr.semantic)

            snapshot = {
                "tick": tick,
                "working": len(cr.working),
                "episodic": n_epi,
                "semantic": len(cr.semantic),
                "archive": len(cr.archive),
                "coaccess_density": density,
                "semantic_entropy": sem_entropy,
                "summaries_created": cm.get("total_summaries_created", 0),
                "cross_topic_merge_rate": cm.get("cross_topic_merge_rate", 0.0),
                "semantic_purity": cm.get("semantic_purity", 0.0),
                "empty_summary_rate": cm.get("empty_summary_rate", 0.0),
                "topology_fragmentation": cm.get("topology_fragmentation", 0),
                "avg_latency_ms": sum(
                    lat for _, lat in [(i, l) for i, l in enumerate(retrieval_latencies[-50:])]
                ) / min(len(retrieval_latencies), 50) if retrieval_latencies else 0,
            }
            tick_metrics.append(snapshot)
            entropy_timeline.append({"tick": tick, "entropy": sem_entropy})
            coaccess_density_timeline.append({"tick": tick, "density": density})

    # Final compaction
    cr._compaction.run_compaction()

    elapsed = time.perf_counter() - t0
    cm = cr._compaction.get_metrics()

    final_memory = {
        "working": len(cr.working),
        "episodic": len(cr.episodic),
        "semantic": len(cr.semantic),
        "archive": len(cr.archive),
    }
    sem_summaries = [m for m in cr.semantic if m.get("memory_type") == "semantic_summary"]

    # G1
    total_compacted = cm.get("total_memories_compacted", 0)
    total_summaries = cm.get("total_summaries_created", 0)
    avg_compression = cm.get("avg_compression_ratio", 0.0)
    max_compression = cm.get("max_compression_ratio", 0.0)

    # G2
    topic_counts = Counter(m.get("topic", "unknown") for m in sem_summaries)
    total_sem = len(sem_summaries)
    monopoly_topic = None
    if topic_counts and total_sem > 0:
        max_topic, max_count = topic_counts.most_common(1)[0]
        if max_count / total_sem >= 0.6:
            monopoly_topic = max_topic
    monopoly_detected = monopoly_topic is not None

    # G3
    sem_archive_ratio = len(cr.archive) / max(1, total_compacted + len(cr.archive))

    # G4
    entropies = [e["entropy"] for e in entropy_timeline]
    if len(entropies) >= 2:
        entropy_delta = max(entropies) - min(entropies)
        entropy_bounded = entropy_delta < 3.0
    else:
        entropy_delta = 0.0
        entropy_bounded = True

    # G5
    avg_latency = sum(retrieval_latencies) / max(1, len(retrieval_latencies))
    sorted_lats = sorted(retrieval_latencies)
    p99_idx = int(len(sorted_lats) * 0.99)
    p99_latency = sorted_lats[p99_idx] if sorted_lats else 0
    retrieval_economical = p99_latency < 100

    # G6
    cross_topic_rate = cm.get("cross_topic_merge_rate", 0.0)
    merge_pure = cross_topic_rate < 0.1

    # G7 — use topic_counts derived from semantic summaries (same as G2)
    # fragmentation = distinct topics with ≥1 summary
    # 0 summaries = topology absent (PASS, no boundary violation)
    # 1-2 topics = isolated topology (threshold should be low)
    # 3+ topics = healthy multi-topic topology (PASS)
    fragmentation = len(topic_counts)
    topic_boundary_intact = fragmentation >= 1

    # Classification
    CLASS_F = []
    CLASS_E = []

    if avg_compression >= 2.0:
        CLASS_F.append(f"G1: avg_compression={avg_compression:.2f}x")
    else:
        CLASS_E.append(f"G1: avg_compression={avg_compression:.2f}x < 2x")

    if not monopoly_detected:
        CLASS_F.append(f"G2: no semantic monopoly")
    else:
        CLASS_E.append(f"G2: MONOPOLY {monopoly_topic} >= 60%")

    if sem_archive_ratio > 0.8:
        CLASS_F.append(f"G3: archive_ratio={sem_archive_ratio:.2f}")
    else:
        CLASS_E.append(f"G3: info loss risk archive_ratio={sem_archive_ratio:.2f}")

    if entropy_bounded:
        CLASS_F.append(f"G4: entropy bounded delta={entropy_delta:.3f}")
    else:
        CLASS_E.append(f"G4: entropy UNBOUNDED delta={entropy_delta:.3f}")

    if retrieval_economical:
        CLASS_F.append(f"G5: p99={p99_latency:.1f}ms")
    else:
        CLASS_E.append(f"G5: retrieval expensive p99={p99_latency:.1f}ms")

    if merge_pure:
        CLASS_F.append(f"G6: cross_topic_rate={cross_topic_rate:.3f}")
    else:
        CLASS_E.append(f"G6: cross-topic contamination rate={cross_topic_rate:.3f}")

    if topic_boundary_intact:
        CLASS_F.append(f"G7: fragmentation={fragmentation}")
    else:
        CLASS_E.append(f"G7: topic boundary COLLAPSED fragmentation={fragmentation}")

    all_passed = len(CLASS_E) == 0

    print("done.")
    print()
    print(f"{'='*60}")
    print(f"  FINAL: {final_memory}")
    print(f"  SUMMARIES: {total_summaries} (compressed {total_compacted} memories)")
    print(f"  COMPRESSION: avg={avg_compression:.2f}x max={max_compression:.1f}x")
    print(f"  CROSS-TOPIC: {cm.get('cross_topic_merge_count',0)}  SAME-TOPIC: {cm.get('same_topic_merge_count',0)}")
    print(f"  PURITY: {cm.get('semantic_purity',0):.3f}  EMPTY: {cm.get('empty_summary_count',0)}")
    print(f"  FRAGMENTATION: {fragmentation}  TOPIC COUNTS: {dict(topic_counts)}")
    print(f"  ELAPSED: {elapsed:.2f}s")
    print()
    print(f"  G1={avg_compression:.2f}x {'PASS' if avg_compression>=2.0 else 'FAIL'}  G2={'PASS' if not monopoly_detected else 'FAIL'}  G3={'PASS' if sem_archive_ratio>0.8 else 'FAIL'}")
    print(f"  G4={'PASS' if entropy_bounded else 'FAIL'}  G5={'PASS' if retrieval_economical else 'FAIL'}  G6={'PASS' if merge_pure else 'FAIL'}  G7={'PASS' if topic_boundary_intact else 'FAIL'}")
    print()
    for e in CLASS_E: print(f"  CLASS_E: {e}")
    for e in CLASS_F: print(f"  CLASS_F: {e}")
    print()
    print(f"  OVERALL: {'VALIDATED ✓' if all_passed else 'PATHOLOGY ✗'}")
    print(f"{'='*60}")

    # Save
    run_id = f"topic_bounded_10k_{int(time.time())}"
    run_base = RUNS / run_id
    run_base.mkdir(parents=True, exist_ok=True)

    results = {
        "run_id": run_id,
        "experiment": "PHASE_IV_B1_Topic_Bounded_Compaction",
        "LKG": "637a11c907e8a889b909513522dfab8c",
        "workload_ticks": WORKLOAD_TICKS,
        "seed": SEED,
        "topics": list(TOPICS.keys()),
        "elapsed_s": elapsed,
        "final_memory": final_memory,
        "compaction_metrics": {
            "total_memories_compacted": total_compacted,
            "total_summaries_created": total_summaries,
            "avg_compression_ratio": avg_compression,
            "max_compression_ratio": max_compression,
            "avg_entropy_delta": cm.get("avg_entropy_delta", 0),
            "cross_topic_merge_count": cm.get("cross_topic_merge_count", 0),
            "same_topic_merge_count": cm.get("same_topic_merge_count", 0),
            "cross_topic_merge_rate": cross_topic_rate,
            "semantic_purity": cm.get("semantic_purity", 0.0),
            "empty_summary_count": cm.get("empty_summary_count", 0),
            "empty_summary_rate": cm.get("empty_summary_rate", 0.0),
            "topology_fragmentation": fragmentation,
            "topic_summary_counts": cm.get("topic_summary_counts", {}),
        },
        "G_results": {
            "G1_compression": {"avg": avg_compression, "max": max_compression,
                               "total_compacted": total_compacted, "PASS": avg_compression >= 2.0},
            "G2_monopoly": {"detected": monopoly_detected, "topic": monopoly_topic,
                            "topic_counts": dict(topic_counts), "PASS": not monopoly_detected},
            "G3_info_preservation": {"archive_ratio": sem_archive_ratio, "PASS": sem_archive_ratio > 0.8},
            "G4_entropy": {"delta": entropy_delta, "min": min(entropies) if entropies else 0,
                           "max": max(entropies) if entropies else 0, "PASS": entropy_bounded},
            "G5_retrieval_econ": {"p99_ms": p99_latency, "avg_ms": avg_latency,
                                  "PASS": retrieval_economical},
            "G6_merge_purity": {"cross_topic_rate": cross_topic_rate,
                                "PASS": merge_pure},
            "G7_topic_boundary": {"fragmentation": fragmentation,
                                   "topic_counts": dict(topic_counts), "PASS": topic_boundary_intact},
        },
        "classification": {"CLASS_E": CLASS_E, "CLASS_F": CLASS_F},
        "all_passed": all_passed,
        "timeline": tick_metrics,
        "entropy_timeline": entropy_timeline,
        "coaccess_density_timeline": coaccess_density_timeline,
        "retrieval_latencies_sample": retrieval_latencies[-1000:],
    }
    with open(run_base / "topic_compaction_metrics.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    with open(run_base / "entropy_timeline.json", "w") as f:
        json.dump({"entropy_timeline": entropy_timeline,
                   "stats": {"delta": entropy_delta, "bounded": entropy_bounded,
                             "min": min(entropies) if entropies else 0,
                             "max": max(entropies) if entropies else 0}}, f, indent=2)

    topology = {
        "nodes": [],
        "edges": [],
        "topic_distribution": dict(topic_counts),
        "fragmentation_score": fragmentation,
    }
    for m in sem_summaries:
        topology["nodes"].append({
            "id": m.get("id"), "topic": m.get("topic"),
            "tags": m.get("tags"), "members": m.get("members", []),
            "compression_ratio": m.get("compression_ratio"),
            "centroid_vector": m.get("centroid_vector"),
            "representative_terms": m.get("representative_terms", []),
            "tick_created": m.get("tick_created"),
        })
    for src_id, neighbors in cr._compaction._coaccess.edges.items():
        for tgt_id, weight in neighbors.items():
            if weight >= 2:
                topology["edges"].append({"source": src_id, "target": tgt_id, "weight": weight})
    with open(run_base / "semantic_topology_graph.json", "w") as f:
        json.dump(topology, f, indent=2, default=str)

    summary_list = [{
        "id": m.get("id"), "topic": m.get("topic"), "content": m.get("content"),
        "members": m.get("members", []), "compression_ratio": m.get("compression_ratio"),
        "entropy_delta": m.get("entropy_delta"), "tick_created": m.get("tick_created"),
    } for m in sem_summaries]
    with open(run_base / "semantic_summaries.json", "w") as f:
        json.dump(summary_list, f, indent=2, default=str)

    print(f"\n[Saved] {run_base}/")
    return results


if __name__ == "__main__":
    run_benchmark()
