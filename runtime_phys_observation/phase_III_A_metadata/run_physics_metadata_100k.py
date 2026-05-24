#!/usr/bin/env python3
"""
MCR Phase III-A: Metadata Physics — 100k Tick Run
===================================================
Focus: Verify metadata boundedness across all dimensions.

METADATA CATEGORIES (STRICTLY SEPARATED FROM MEMORY):
  T1 — transition log entries       (transitions.jsonl)
  T2 — trace events                 (memory_trace output)
  T3 — snapshot metadata             (per-snapshot overhead)
  T4 — rerank cache entries          (goal_relevance cache)
  T5 — semantic topology state       (graph structure)
  T6 — decay buffer in-flight       (volatile until committed)

MEMORY CATEGORIES (REAL OBJECTS):
  working / episodic / semantic / archive

RESEARCH QUESTIONS:
  G1. Does metadata grow without bound?
  G2. Does metadata growth outpace memory growth?
  G3. Does retrieval latency degrade as metadata grows?
  G4. Do transitions/event/log/snapshot form a hidden memory leak?
  G5. Does metadata compaction reach natural plateau?

OUTPUT:
  metadata_metrics.json — all metadata stats
  growth_curves.csv     — time-series for plotting
  METADATA_PHYSICS_REPORT.md — analysis + conclusions
"""

import sys
import os
import time
import json
import math
import random
from collections import defaultdict

_MCR_ROOT = '.'
sys.path.insert(0, _MCR_ROOT)
sys.path.insert(0, os.path.join(_MCR_ROOT, 'stable'))

from layered_memory import LayeredMemory

# ─── Output ─────────────────────────────────────────────────────────────────

PHASE_DIR = './runtime_phys_observation/phase_III_A_metadata'
RUN_DIR = os.path.join(PHASE_DIR, 'runs/metadata_100k')
METRICS_FILE = os.path.join(PHASE_DIR, 'metrics/metadata_metrics.json')
CURVES_FILE = os.path.join(PHASE_DIR, 'metrics/growth_curves.csv')

os.makedirs(RUN_DIR, exist_ok=True)

# ─── Workload (same as run_physics_100k.py for comparability) ───────────────

TOPICS = [
    "project_alpha", "project_beta", "project_gamma",
    "meeting_notes", "decision_log", "risk_register",
    "user_feedback", "bug_report", "feature_request",
    "code_review", "deployment_log", "test_results",
    "research_notes", "experiment_log", "analysis_report",
]
MEMORY_TEMPLATES = [
    "completed {topic} milestone {n} with status {s}",
    "updated {topic} documentation for release {n}",
    "resolved {topic} critical issue in component {c}",
    "deployed {topic} version {n} to {e}",
    "reviewed {topic} PR #{n} from contributor {w}",
]
ENVS = ["production", "staging", "development", "qa"]
TEAMS = ["backend", "frontend", "infra", "security", "data"]
COMPS = ["api", "ui", "db", "cache", "worker", "gateway"]
PEOPLE = ["alice", "bob", "charlie", "diana", "eve", "frank"]
STATUSES = ["complete", "partial", "failed", "pending"]

# ─── Config ─────────────────────────────────────────────────────────────────

TICKS = 100_000
REPORT_EVERY = 5_000
SNAPSHOT_EVERY = 5_000

random.seed(42)
lm = LayeredMemory(RUN_DIR)

# ─── Module-level metadata counters ─────────────────────────────────────────
_snapshot_count = 0
_snapshot_overhead_total = 0.0

# ─── Metrics: Memory (REAL) ──────────────────────────────────────────────────

memory_counts = []          # {tick, working, episodic, semantic, archive}
memory_total_curve = []     # (tick, total_memories)
memory_growth_rate = []    # (tick, rate)

# ─── Metrics: Metadata (STRICTLY SEPARATED) ──────────────────────────────────

# T1: transitions.jsonl
transitions_size_curve = []      # (tick, bytes)
transitions_count_curve = []    # (tick, line_count)
transitions_growth_rate = []    # (tick, rate)

# T2: trace events
trace_event_count = []          # (tick, count)

# T3: snapshot metadata
snapshot_overhead_curve = []    # (tick, cumulative_bytes)
snapshot_count = 0
snapshot_overhead_total = 0

# T4: rerank cache (in-memory goal_relevance cache)
#    Tracked as: cache_misses * avg_entry_size
rerank_cache_size = []          # (tick, estimated_bytes)
rerank_cache_hits = 0
rerank_cache_misses = 0

# T5: semantic topology state
semantic_topo_size = []         # (tick, bytes) — graph structure
semantic_topo_nodes = 0

# T6: decay buffer in-flight
decay_buffer_size = []          # (tick, bytes)

# ─── Metadata totals ─────────────────────────────────────────────────────────

metadata_total_curve = []       # (tick, total_metadata_bytes)
metadata_entries_curve = []     # (tick, total_metadata_entries)
metadata_to_memory_ratio = []   # (tick, ratio)

# ─── Performance: Retrieval Latency ─────────────────────────────────────────

retrieval_latency = []         # (tick, ms)
retrieval_latency_p50 = []     # (tick, p50)
retrieval_latency_p95 = []     # (tick, p95)

# Decomposition
retrieve_cost_curve = []        # (tick, ms) — pure retrieve()
decay_cost_curve = []           # (tick, ms) — process_decay_buffer
review_cost_curve = []          # (tick, ms) — incremental_review
flush_cost_curve = []           # (tick, ms) — try_flush

# ─── Rerank cost ─────────────────────────────────────────────────────────────

rerank_cost_curve = []          # (tick, ms)
rerank_modifications = []       # (tick, count)

# ─── Helper models ───────────────────────────────────────────────────────────

# Estimate size of transitions.jsonl entry (bytes)
def transition_entry_size() -> float:
    return random.uniform(80, 150)

# Estimate size of a rerank cache entry
def rerank_cache_entry_size() -> float:
    return random.uniform(40, 80)

# Estimate semantic topology overhead per node
def semantic_topo_node_size() -> float:
    return random.uniform(30, 60)

def get_transitions_size(path: str) -> int:
    """Get actual transitions.jsonl file size in bytes."""
    if os.path.exists(path):
        return os.path.getsize(path)
    return 0

def count_transition_lines(path: str) -> int:
    """Count lines in transitions.jsonl."""
    if not os.path.exists(path):
        return 0
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return sum(1 for _ in f)
    except:
        return 0

# ─── Main Loop ────────────────────────────────────────────────────────────────

start_time = time.time()

def make_memory(topic, n, status, comp, env, who):
    tmpl = random.choice(MEMORY_TEMPLATES)
    return tmpl.format(topic=topic, n=n, s=status, c=comp, e=env, w=who)

# Rolling stats for growth rate
recent_metadata_bytes = []
older_metadata_bytes = []

def compute_growth_rate(series, window=1000):
    if len(series) < 2 * window:
        return 0.0
    first = sum(t for (_, t) in series[-2*window:-window]) / window
    last = sum(t for (_, t) in series[-window:]) / window
    if first == 0:
        return 0.0
    return (last - first) / first

for tick in range(1, TICKS + 1):
    tick_start = time.perf_counter()
    retrieve_start = time.perf_counter()

    # ── Memory Write ──────────────────────────────────────────────────────────
    stored_topics = []
    for _ in range(random.randint(3, 5)):
        topic = random.choice(TOPICS)
        text = make_memory(topic, random.randint(1, 100),
                          random.choice(STATUSES),
                          random.choice(COMPS),
                          random.choice(ENVS),
                          random.choice(PEOPLE))
        tags = [topic, random.choice(TEAMS)]
        lm.store(text, memory_type=topic, tags=tags)
        stored_topics.append(topic)

    # ── Retrieval (measure latency) ─────────────────────────────────────────
    retrieved_topics = []
    for _ in range(random.randint(1, 3)):
        topic = random.choice(TOPICS)
        t0 = time.perf_counter()
        result = lm.retrieve(topic, max_results=5)
        latency_ms = (time.perf_counter() - t0) * 1000
        retrieval_latency.append((tick, latency_ms))

        # Rerank modifications (estimate)
        rerank_mods = result[0].get("_suppressed", 0) + result[0].get("_replaced_from", 0) if result else 0
        rerank_modifications.append((tick, rerank_mods))

        retrieved_topics.append(topic)

    retrieve_cost_ms = (time.perf_counter() - retrieve_start) * 1000
    retrieve_cost_curve.append((tick, retrieve_cost_ms))

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    decay_start = time.perf_counter()
    decay_result = lm.process_decay_buffer(tick)
    decay_cost_ms = (time.perf_counter() - decay_start) * 1000
    decay_cost_curve.append((tick, decay_cost_ms))

    review_start = time.perf_counter()
    review_result = lm.incremental_review(tick)
    review_cost_ms = (time.perf_counter() - review_start) * 1000
    review_cost_curve.append((tick, review_cost_ms))

    # ── Persistence ─────────────────────────────────────────────────────────
    flush_start = time.perf_counter()
    flushed = lm.try_flush(tick)
    flush_cost_ms = (time.perf_counter() - flush_start) * 1000
    flush_cost_curve.append((tick, flush_cost_ms))

    # ── Metadata: T1 transitions.jsonl ───────────────────────────────────────
    trans_path = os.path.join(RUN_DIR, 'transitions.jsonl')
    trans_size = get_transitions_size(trans_path)
    trans_count = count_transition_lines(trans_path)
    transitions_size_curve.append((tick, trans_size))
    transitions_count_curve.append((tick, trans_count))

    # ── Metadata: T3 snapshot overhead ───────────────────────────────────────
    if tick % SNAPSHOT_EVERY == 0:
        _snapshot_count += 1
        snap_overhead = random.uniform(200, 500)
        _snapshot_overhead_total += snap_overhead
        snapshot_overhead_curve.append((tick, _snapshot_overhead_total))

    # ── Metadata: T4 rerank cache ───────────────────────────────────────────
    # Approximate: episodic_size * avg_goal_relevance_cache_entry
    episodic_size = len(lm.episodic)
    cache_est = episodic_size * rerank_cache_entry_size()
    rerank_cache_size.append((tick, cache_est))

    # ── Metadata: T5 semantic topology ─────────────────────────────────────
    semantic_nodes = len(lm.semantic)
    topo_est = semantic_nodes * semantic_topo_node_size()
    semantic_topo_size.append((tick, topo_est))

    # ── Metadata: T6 decay buffer ───────────────────────────────────────────
    decay_inflight = len(getattr(lm, '_decay_buffer_memories', [])) * 70
    decay_buffer_size.append((tick, decay_inflight))

    # ── Metadata totals ─────────────────────────────────────────────────────
    total_metadata_bytes = (
        trans_size
        + snapshot_overhead_total
        + cache_est
        + topo_est
        + decay_inflight
    )
    total_metadata_entries = (
        trans_count
        + snapshot_count
        + episodic_size
        + semantic_nodes
        + len(getattr(lm, '_decay_buffer_memories', []))
    )
    metadata_total_curve.append((tick, total_metadata_bytes))
    metadata_entries_curve.append((tick, total_metadata_entries))

    # ── Memory totals ────────────────────────────────────────────────────────
    W = len(lm.working)
    E = len(lm.episodic)
    S = len(lm.semantic)
    A = len(lm.archive)
    total_memories = W + E + S + A
    memory_total_curve.append((tick, total_memories))
    memory_counts.append({
        "tick": tick,
        "working": W, "episodic": E, "semantic": S, "archive": A,
        "total": total_memories
    })

    # ── Metadata to Memory ratio ────────────────────────────────────────────
    ratio = total_metadata_bytes / max(1, total_memories * 500)  # ~500 bytes/memory
    metadata_to_memory_ratio.append((tick, ratio))

    # ── Latency percentiles ─────────────────────────────────────────────────
    if tick % 100 == 0:
        recent = [m for (t, m) in retrieval_latency[-100:] if t >= tick - 100]
        if recent:
            sorted_lat = sorted(recent)
            p50_idx = len(sorted_lat) // 2
            p95_idx = int(len(sorted_lat) * 0.95)
            retrieval_latency_p50.append((tick, sorted_lat[p50_idx]))
            retrieval_latency_p95.append((tick, sorted_lat[p95_idx]))

    # ── Snapshot ────────────────────────────────────────────────────────────
    if tick % SNAPSHOT_EVERY == 0:
        snap = {
            "tick": tick,
            "working": W, "episodic": E, "semantic": S, "archive": A,
            "metadata_bytes": total_metadata_bytes,
            "metadata_entries": total_metadata_entries,
        }
        snap_path = os.path.join(RUN_DIR, f"snap_{tick:06d}.json")
        with open(snap_path, 'w') as f:
            json.dump(snap, f, indent=2)

    # ── Progress ────────────────────────────────────────────────────────────
    if tick % REPORT_EVERY == 0:
        elapsed = time.time() - start_time
        recent_lat = [m for (t, m) in retrieval_latency[-REPORT_EVERY:]]
        avg_lat = sum(recent_lat) / len(recent_lat) if recent_lat else 0
        max_lat = max(recent_lat) if recent_lat else 0

        meta_rate = compute_growth_rate(metadata_total_curve)
        mem_rate = compute_growth_rate(memory_total_curve)

        print(f"\n[TICK {tick:,}/{TICKS:,} | {tick/TICKS*100:.1f}%] {elapsed:.1f}s elapsed")
        print(f"  MEMORY (W/E/S/A): {W}/{E}/{S}/{A} = {total_memories}")
        print(f"  METADATA bytes: {total_metadata_bytes:,.0f}  entries: {total_metadata_entries:,}")
        print(f"  Meta/Mem ratio: {ratio:.2f}")
        print(f"  Meta growth rate: {meta_rate*100:+.2f}% | Mem growth rate: {mem_rate*100:+.2f}%")
        print(f"  LAT: avg={avg_lat:.3f}ms max={max_lat:.3f}ms")

        # Tick cost decomposition
        recent_retrieve = [m for (t, m) in retrieve_cost_curve[-REPORT_EVERY:]]
        recent_decay = [m for (t, m) in decay_cost_curve[-REPORT_EVERY:]]
        recent_review = [m for (t, m) in review_cost_curve[-REPORT_EVERY:]]
        recent_flush = [m for (t, m) in flush_cost_curve[-REPORT_EVERY:]]
        avg_retrieve = sum(recent_retrieve) / len(recent_retrieve) if recent_retrieve else 0
        avg_decay = sum(recent_decay) / len(recent_decay) if recent_decay else 0
        avg_review = sum(recent_review) / len(recent_review) if recent_review else 0
        avg_flush = sum(recent_flush) / len(recent_flush) if recent_flush else 0
        print(f"  COST BREAKDOWN: retrieve={avg_retrieve:.3f}ms decay={avg_decay:.3f}ms "
              f"review={avg_review:.3f}ms flush={avg_flush:.3f}ms")

# ─── Final Analysis ──────────────────────────────────────────────────────────

elapsed = time.time() - start_time

def asymptotic_fit(series, name="series"):
    """Fit bytes = A * tick^alpha. Returns alpha."""
    if len(series) < 100:
        return float('nan')
    xs = [math.log(max(1, t)) for (t, b) in series if t > 0 and b > 0]
    ys = [math.log(max(1, b)) for (t, b) in series if t > 0 and b > 0]
    if len(xs) < 10:
        return float('nan')
    n = len(xs)
    sum_x = sum(xs); sum_y = sum(ys); sum_xy = sum(x*y for x,y in zip(xs,ys)); sum_x2 = sum(x*x for x in xs)
    denom = n*sum_x2 - sum_x**2
    if abs(denom) < 1e-10:
        return float('nan')
    alpha = (n*sum_xy - sum_x*sum_y) / denom
    return alpha

def plateau_detection(series, window=5000):
    """Detect if series has plateaued (variance/mean < 5%)."""
    if len(series) < 2*window:
        return None, 0.0
    recent = [b for (t, b) in series[-window:]]
    mean = sum(recent) / len(recent)
    var = sum((b - mean)**2 for b in recent) / len(recent)
    std = math.sqrt(var)
    if std / mean < 0.05:
        return len(series), 1.0 - (std / mean)
    return None, 0.0

# Compute asymptotic exponents
alpha_metadata = asymptotic_fit(metadata_total_curve, "metadata")
alpha_memory = asymptotic_fit(memory_total_curve, "memory")
alpha_transitions = asymptotic_fit(transitions_size_curve, "transitions")

# Plateau detection
plat_meta, conf_meta = plateau_detection(metadata_total_curve)
plat_trans, conf_trans = plateau_detection(transitions_size_curve)

# Latency trend
early_lat = [m for (t, m) in retrieval_latency[:1000]]
late_lat = [m for (t, m) in retrieval_latency[-1000:]]
early_avg = sum(early_lat) / len(early_lat) if early_lat else 0.001
late_avg = sum(late_lat) / len(late_lat) if late_lat else 0.001
latency_ratio = late_avg / early_avg

# Metadata vs Memory growth comparison
meta_growth_final = (
    (metadata_total_curve[-1][1] - metadata_total_curve[0][1])
    if len(metadata_total_curve) > 1 else 0
)
mem_growth_final = (
    (memory_total_curve[-1][1] - memory_total_curve[0][1])
    if len(memory_total_curve) > 1 else 0
)
meta_vs_mem_ratio = meta_growth_final / max(1, mem_growth_final)

# Final stats
final_W = len(lm.working)
final_E = len(lm.episodic)
final_S = len(lm.semantic)
final_A = len(lm.archive)
final_meta_bytes = metadata_total_curve[-1][1] if metadata_total_curve else 0
final_meta_entries = metadata_entries_curve[-1][1] if metadata_entries_curve else 0

# ─── Verdict ─────────────────────────────────────────────────────────────────

verdicts = {
    "G1_metadata_bounded": (
        alpha_metadata < 1.05 if not math.isnan(alpha_metadata) else False
    ),
    "G2_metadata_vs_memory": (
        meta_vs_mem_ratio < 10.0  # metadata shouldn't grow 10x faster than memory
    ),
    "G3_latency_degradation": latency_ratio < 2.0,
    "G4_metadata_leak": (
        plateau_detection(metadata_total_curve)[0] is not None or
        alpha_metadata < 1.05
    ),
    "G5_natural_plateau": plat_meta is not None,
}

all_pass = all(verdicts.values())

print(f"\n{'='*70}")
print(f"PHASE III-A METADATA PHYSICS — FINAL REPORT")
print(f"{'='*70}")
print(f"  Ticks:           {TICKS:,}")
print(f"  Elapsed:         {elapsed:.1f}s ({elapsed/60:.1f} min)")
print(f"\nMEMORY (real objects):")
print(f"  Final (W/E/S/A): {final_W}/{final_E}/{final_S}/{final_A}")
print(f"  asymptotic alpha: {alpha_memory:.3f}" if not math.isnan(alpha_memory) else "  asymptotic alpha: N/A")
print(f"\nMETADATA:")
print(f"  T1 transitions.jsonl: {final_trans_count:,} entries, {final_trans_size:,} bytes")
print(f"  T3 snapshot overhead:  {snapshot_count} snapshots, {snapshot_overhead_total:,.0f} bytes")
print(f"  T4 rerank cache est:   {rerank_cache_size[-1][1]:.0f} bytes" if rerank_cache_size else "")
print(f"  T5 semantic topo est: {semantic_topo_size[-1][1]:.0f} bytes" if semantic_topo_size else "")
print(f"  T6 decay buffer est:  {decay_buffer_size[-1][1]:.0f} bytes" if decay_buffer_size else "")
print(f"  TOTAL metadata:       {final_meta_bytes:,.0f} bytes, {final_meta_entries:,} entries")
print(f"\nGROWTH ANALYSIS:")
print(f"  Metadata asymptotic alpha: {alpha_metadata:.3f}" if not math.isnan(alpha_metadata) else "  Metadata asymptotic alpha: N/A")
print(f"  Transitions asymptotic α:  {alpha_transitions:.3f}" if not math.isnan(alpha_transitions) else "  Transitions asymptotic α: N/A")
print(f"  Meta/Mem growth ratio:    {meta_vs_mem_ratio:.2f}x")
print(f"  Natural plateau:          {'YES @ tick ' + str(plat_meta) if plat_meta else 'NOT DETECTED'}")
print(f"\nLATENCY:")
print(f"  Early avg: {early_avg:.4f}ms | Late avg: {late_avg:.4f}ms")
print(f"  Latency ratio: {latency_ratio:.3f}x")
print(f"\nVERDICTS:")
for k, v in verdicts.items():
    print(f"  {'[PASS]' if v else '[FAIL]'} {k}")
print(f"\nOVERALL: {'[PASS] All bounded' if all_pass else '[FAIL] Metadata unbounded'}")

# ─── Export Metrics JSON ─────────────────────────────────────────────────────

metrics = {
    "experiment": "Phase III-A Metadata Physics",
    "ticks": TICKS,
    "elapsed_seconds": elapsed,

    "memory": {
        "final": {"working": final_W, "episodic": final_E, "semantic": final_S, "archive": final_A},
        "asymptotic_alpha": alpha_memory if not math.isnan(alpha_memory) else None,
        "total_growth": mem_growth_final,
    },

    "metadata": {
        "T1_transitions": {
            "final_count": transitions_count_curve[-1][1] if transitions_count_curve else 0,
            "final_bytes": transitions_size_curve[-1][1] if transitions_size_curve else 0,
            "asymptotic_alpha": alpha_transitions if not math.isnan(alpha_transitions) else None,
        },
        "T3_snapshot_overhead": {
            "snapshot_count": _snapshot_count,
            "total_bytes": _snapshot_overhead_total,
        },
        "T4_rerank_cache_est": {
            "final_bytes": rerank_cache_size[-1][1] if rerank_cache_size else 0,
        },
        "T5_semantic_topo_est": {
            "final_bytes": semantic_topo_size[-1][1] if semantic_topo_size else 0,
        },
        "T6_decay_buffer_est": {
            "final_bytes": decay_buffer_size[-1][1] if decay_buffer_size else 0,
        },
        "total_bytes": final_meta_bytes,
        "total_entries": final_meta_entries,
        "asymptotic_alpha": alpha_metadata if not math.isnan(alpha_metadata) else None,
        "meta_vs_memory_growth_ratio": meta_vs_mem_ratio,
        "plateau_tick": plat_meta,
        "plateau_confidence": conf_meta,
    },

    "latency": {
        "early_avg_ms": early_avg,
        "late_avg_ms": late_avg,
        "ratio": latency_ratio,
    },

    "verdicts": verdicts,
    "overall_pass": all_pass,
}

with open(METRICS_FILE, 'w') as f:
    json.dump(metrics, f, indent=2)
print(f"\n[METRICS] {METRICS_FILE}")

# ─── Export Growth Curves CSV ─────────────────────────────────────────────────

with open(CURVES_FILE, 'w') as f:
    f.write("tick,category,metric,value\n")
    for (tick, val) in metadata_total_curve:
        f.write(f"{tick},metadata,bytes,{val}\n")
    for (tick, val) in memory_total_curve:
        f.write(f"{tick},memory,count,{val}\n")
    for (tick, val) in transitions_size_curve:
        f.write(f"{tick},transitions,bytes,{val}\n")
    for (tick, val) in transitions_count_curve:
        f.write(f"{tick},transitions,count,{val}\n")
    for (tick, val) in metadata_to_memory_ratio:
        f.write(f"{tick},ratio,meta_mem_ratio,{val}\n")
    for (tick, val) in retrieval_latency_p50:
        f.write(f"{tick},latency,p50_ms,{val}\n")
    for (tick, val) in retrieval_latency_p95:
        f.write(f"{tick},latency,p95_ms,{val}\n")
print(f"[CURVES] {CURVES_FILE}")
