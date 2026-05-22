#!/usr/bin/env python3
"""
MCR PHASE_VI_PATCH_RUN — Validate 3 Hard Fixes
==============================================
TARGETS:
  T1: Compaction complexity — O(n²) full-graph → O(k²) per-topic
  T2: Archive steady state — no more oscillation, plateau reached
  T3: Semantic promotion — summaries > 0

MECHANISMS PATCHED:
  ✓ CoAccessGraph.edges: int → float (weights now decay)
  ✓ CoAccessGraph.decay_edges(): per-tick decay + cleanup
  ✓ CoAccessGraph.cap_edges(): per-node + global edge cap
  ✓ SemanticCompaction.tick(): runs decay + cap every tick
  ✓ SemanticCompaction.run_compaction(): incremental per-topic (1 topic/call)
  ✓ SemanticCompaction._get_topic_groups(): bounded local subgraph scan

VERIFICATION:
  Compare Phase V (pre-patch) vs Phase VI (post-patch):
    - Overhead trajectory: 7x→13x→19x→27x (linear growth) vs bounded
    - Archive oscillation: 68-364 (wild) vs stable plateau
    - Semantic summaries: 0 vs > 0
    - Coaccess edge count: unbounded vs capped at 500
"""
import sys, os, time, json, random, math, shutil
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, '/home/minimak/mcr')
sys.path.insert(0, '/home/minimax/mcr/stable')
sys.path.insert(0, '/home/minimak/mcr/runtime_phys_observation/phase_IV_B_compaction')
sys.path.insert(0, '/home/minimak/mcr/runtime_phys_observation/phase_IV_B_compaction')

try:
    from layered_memory import LayeredMemory
    from semantic_compaction import SemanticCompaction, CompactionRuntime
except ModuleNotFoundError:
    sys.path[0] = '/home/minimak/mcr/stable'
    from layered_memory import LayeredMemory
    from semantic_compaction import SemanticCompaction, CompactionRuntime

BASE = Path("/home/minimak/mcr/runtime_phys_observation/phase_IV_B_compaction")
RUNS = BASE / "runs"
OUT = RUNS / "phase_VI_patch_validation"
OUT.mkdir(parents=True, exist_ok=True)

TOPICS = [
    "python_gc","sql_query","docker_runtime","wal_replay",
    "semantic_search","crash_recovery","network_protocol","file_system",
]
TEMPLATES = [
    "{topic} operation {n} completed in {ms}ms",
    "{topic} worker thread {n} blocked on lock",
    "{topic} queue depth {n} exceeded threshold",
    "{topic} cache miss rate {pct}% at tick {n}",
    "{topic} batch {n} failed with error code {err}",
]
ENVS = ["prod","staging","dev"]
ERR_CODES = [400,404,500,503,504]
PCT_VALS = [12,23,34,45,67,78,89,91]

def make_content(topic, n):
    tpl = random.choice(TEMPLATES)
    return tpl.format(
        topic=topic, n=n,
        ms=random.randint(1,999),
        err=random.choice(ERR_CODES),
        pct=random.choice(PCT_VALS)
    )

WINDOW_TICKS = 5000
TOTAL_WINDOWS = 6
SNAPSHOT_INTERVAL = 1000

# ── Failure thresholds ──────────────────────────────────────────────────────────
MAX_OVERHEAD_RATIO = 20.0
MAX_ARCHIVE_OSCILLATION = 5.0  # max ratio of max_A / min_A across windows
MIN_SEMANTIC_SUMMARIES = 1     # want at least 1 summary formed

def compute_entropy(memory_list):
    if not memory_list:
        return 0.0
    topic_counts = defaultdict(int)
    for m in memory_list:
        for t in m.get('tags', []):
            if t not in {'compaction_test','general','noise','unknown','untagged','phase_v'}:
                topic_counts[t] += 1
    total = sum(topic_counts.values())
    if total == 0:
        return 0.0
    probs = [c/total for c in topic_counts.values()]
    return -sum(p*math.log2(p) for p in probs if p > 0)

print("=" * 70)
print("PHASE_VI_PATCH_RUN — Validation of Death Mechanisms")
print("=" * 70)

# ── Baseline (no compaction) ──────────────────────────────────────────────────
print(f"\n[BASELINE] {WINDOW_TICKS} ticks no-compaction...", end=" ", flush=True)
ROOT_B = str(OUT / "baseline")
if os.path.exists(ROOT_B): shutil.rmtree(ROOT_B)
lm_b = LayeredMemory(ROOT_B)
t0_b = time.perf_counter()
for tick in range(1, WINDOW_TICKS+1):
    topic = random.choice(TOPICS)
    content = make_content(topic, tick)
    lm_b.store(content, tags=[topic, "phase_vi"], importance=0.5, current_tick=tick)
    if tick % 50 == 0:
        lm_b.process_decay_buffer(tick)
    if tick % 100 == 0:
        lm_b.incremental_review(tick)
    if tick % 200 == 0:
        lm_b.try_flush(tick)
b_elapsed = time.perf_counter() - t0_b
baseline_mem = {
    "working": len(lm_b.working),
    "episodic": len(lm_b.episodic),
    "semantic": len(lm_b.semantic),
    "archive": len(lm_b.archive),
    "total": sum([len(lm_b.working), len(lm_b.episodic), len(lm_b.semantic), len(lm_b.archive)]),
    "elapsed_s": b_elapsed,
}
print(f"done. {b_elapsed:.2f}s  mem={baseline_mem}")

# ── PATCHED run with death mechanisms ────────────────────────────────────────
print(f"\n[PHASE_VI_PATCHED] {TOTAL_WINDOWS} × {WINDOW_TICKS} ticks with decay+cap+incremental...", flush=True)
ROOT_C = str(OUT / "patched")
if os.path.exists(ROOT_C): shutil.rmtree(ROOT_C)
cr = CompactionRuntime(ROOT_C)

window_data = []
total_ticks = 0
start_time = time.time()
stopped_early = False
stop_reason = None

# Verify coaccess params
edge_cap = cr._compaction._coaccess.MAX_TOTAL_EDGES
decay_factor = cr._compaction._coaccess.DECAY_FACTOR
print(f"  Coaccess params: global_cap={edge_cap}, decay={decay_factor}")

for wn in range(1, TOTAL_WINDOWS+1):
    w_start = time.perf_counter()
    w_tick_start = total_ticks + 1
    w_snapshots = []
    w_latencies = []
    w_compaction_ops = 0
    w_summaries = 0

    for tick in range(w_tick_start, w_tick_start + WINDOW_TICKS):
        total_ticks = tick
        tick_start = time.perf_counter()

        topic = random.choice(TOPICS)
        content = make_content(topic, tick)
        cr.store(content, tags=[topic, "phase_vi"], importance=0.5, current_tick=tick)

        if tick % 3 == 0:
            q = random.choice(TOPICS)
            cr.retrieve(q, current_tick=tick, max_results=5)

        cr.tick()  # ← runs decay + cap

        tick_elapsed = (time.perf_counter() - tick_start) * 1000
        w_latencies.append(tick_elapsed)

        if tick % SNAPSHOT_INTERVAL == 0:
            W, E, S, A = len(cr.working), len(cr.episodic), len(cr.semantic), len(cr.archive)
            ent = compute_entropy(cr.episodic + cr.working)
            edge_count = cr._compaction._coaccess.get_edge_count()
            w_snapshots.append({
                "tick": tick, "W": W, "E": E, "S": S, "A": A,
                "entropy": ent, "coaccess_edges": edge_count,
            })

        if tick % 500 == 0:
            result = cr._compaction.run_compaction()
            w_compaction_ops += result.get("compaction_count", 0)
            w_summaries += result.get("summaries_created", 0)

        if tick % 1000 == 0:
            cr._lm.incremental_review(tick)

    w_elapsed = time.perf_counter() - w_start

    W, E, S, A = len(cr.working), len(cr.episodic), len(cr.semantic), len(cr.archive)
    total_mem_now = W + E + S + A
    overhead = w_elapsed / max(b_elapsed, 0.001)
    avg_lat = sum(w_latencies) / len(w_latencies)
    p99_lat = sorted(w_latencies)[int(len(w_latencies)*0.99)]
    ent = compute_entropy(cr.episodic + cr.working)
    cm = cr.get_compaction_metrics()
    edge_count = cr._compaction._coaccess.get_edge_count()

    wd = {
        "window": wn,
        "tick_start": w_tick_start,
        "tick_end": total_ticks,
        "elapsed_s": w_elapsed,
        "W": W, "E": E, "S": S, "A": A, "total": total_mem_now,
        "compaction_ops": w_compaction_ops,
        "summaries_this_window": w_summaries,
        "total_summaries": cm.get("total_summaries_created", 0),
        "avg_latency_ms": avg_lat,
        "p99_latency_ms": p99_lat,
        "entropy": ent,
        "overhead_ratio": overhead,
        "coaccess_edges": edge_count,
        "snapshots": w_snapshots,
        "entropy_timeline": [s["entropy"] for s in w_snapshots],
        "edge_timeline": [s["coaccess_edges"] for s in w_snapshots],
    }
    window_data.append(wd)

    elapsed_total = time.time() - start_time
    print(f"  [{wn}/{TOTAL_WINDOWS}] {w_elapsed:.1f}s | "
          f"W={W} E={E} S={S} A={A} | "
          f"LAT={avg_lat:.2f}ms p99={p99_lat:.2f}ms | "
          f"ENT={ent:.3f} | "
          f"EDGES={edge_count} | "
          f"OVERHEAD={overhead:.2f}x | "
          f"SUM={cm.get('total_summaries_created',0)} | "
          f"{elapsed_total/60:.1f}m total")

    # Check overhead failure
    if overhead > MAX_OVERHEAD_RATIO:
        stopped_early = True
        stop_reason = f"Window {wn}: OVERHEAD {overhead:.2f}x > {MAX_OVERHEAD_RATIO}"
        print(f"\n  !!! STOPPING: {stop_reason}")
        break

elapsed_total = time.time() - start_time

# ── VERIFICATION ───────────────────────────────────────────────────────────────
print(f"\n{'='*70}")
print("PHASE_VI_PATCH_RUN — VERIFICATION RESULTS")
print(f"{'='*70}")

# T1: Compaction complexity — overhead should be bounded
overheads = [w["overhead_ratio"] for w in window_data]
overhead_growth = overheads[-1] / max(overheads[0], 0.001)
T1_PASS = overhead_growth < 3.0  # overhead shouldn't grow 4x like before

# T2: Archive steady state — oscillation should be bounded
all_A = [w["A"] for w in window_data]
max_A = max(all_A)
min_A = min(all_A)
oscillation_ratio = max_A / max(min_A, 1)
T2_PASS = oscillation_ratio < MAX_ARCHIVE_OSCILLATION

# T3: Semantic promotion — at least MIN_SEMANTIC_SUMMARIES
total_summaries = window_data[-1]["total_summaries"] if window_data else 0
T3_PASS = total_summaries >= MIN_SEMANTIC_SUMMARIES

# Coaccess edge cap — should be bounded at 500
all_edges = [w["coaccess_edges"] for w in window_data]
max_edges = max(all_edges)
T_EDGES_PASS = max_edges <= edge_cap * 1.1  # allow 10% tolerance

print()
print(f"T1 — Compaction Complexity (overhead growth):")
print(f"    Overhead trajectory: {' → '.join(f'{o:.1f}x' for o in overheads)}")
print(f"    Growth ratio: {overhead_growth:.2f}x (last/first)")
print(f"    Phase V comparison: 7x→13x→19x→27x (4x growth)")
print(f"    [{'PASS' if T1_PASS else 'FAIL'}] {'Bounded' if T1_PASS else 'Still growing'}")

print()
print(f"T2 — Archive Steady State (oscillation):")
print(f"    Archive per window: {all_A}")
print(f"    Oscillation ratio: {oscillation_ratio:.1f}x (max/min)")
print(f"    Phase V comparison: 68-364 (5.4x oscillation)")
print(f"    [{'PASS' if T2_PASS else 'FAIL'}] {'Stable' if T2_PASS else 'Still oscillating'}")

print()
print(f"T3 — Semantic Promotion (summaries > 0):")
print(f"    Total summaries: {total_summaries}")
print(f"    Phase V comparison: 0")
print(f"    [{'PASS' if T3_PASS else 'FAIL'}] {'Promotion active' if T3_PASS else 'Still stalled'}")

print()
print(f"T4 — Coaccess Edge Cap (bounded at {edge_cap}):")
print(f"    Edge count per window: {all_edges}")
print(f"    Max edges: {max_edges}")
print(f"    [{'PASS' if T_EDGES_PASS else 'FAIL'}] {'Edge cap working' if T_EDGES_PASS else 'Unbounded edges'}")

# Overall verdict
verdicts = {
    "T1_compaction_complexity": T1_PASS,
    "T2_archive_steady_state": T2_PASS,
    "T3_semantic_promotion": T3_PASS,
    "T4_coaccess_edge_cap": T_EDGES_PASS,
}
overall_pass = all(verdicts.values())
print()
print(f"OVERALL: {'✓ ALL PASS' if overall_pass else '✗ PARTIAL FAILURE'}")
for k, v in verdicts.items():
    print(f"  {'[PASS]' if v else '[FAIL]'} {k}")

# ── Save results ────────────────────────────────────────────────────────────────
results = {
    "phase": "PHASE_VI_PATCH_RUN",
    "lkq": "637a11c907e8a889b909513522dfab8c",
    "total_ticks": total_ticks,
    "elapsed_s": elapsed_total,
    "windows_run": len(window_data),
    "stopped_early": stopped_early,
    "stop_reason": stop_reason,
    "baseline": baseline_mem,
    "windows": window_data,
    "thresholds": {
        "MAX_OVERHEAD_RATIO": MAX_OVERHEAD_RATIO,
        "MAX_ARCHIVE_OSCILLATION": MAX_ARCHIVE_OSCILLATION,
        "MIN_SEMANTIC_SUMMARIES": MIN_SEMANTIC_SUMMARIES,
        "EDGE_CAP": edge_cap,
    },
    "verification": {
        "T1_compaction_complexity": {
            "overhead_trajectory": overheads,
            "growth_ratio": overhead_growth,
            "pass": T1_PASS,
        },
        "T2_archive_steady_state": {
            "archive_values": all_A,
            "oscillation_ratio": oscillation_ratio,
            "pass": T2_PASS,
        },
        "T3_semantic_promotion": {
            "total_summaries": total_summaries,
            "pass": T3_PASS,
        },
        "T4_coaccess_edge_cap": {
            "edge_counts": all_edges,
            "max_edges": max_edges,
            "cap": edge_cap,
            "pass": T_EDGES_PASS,
        },
        "overall_pass": overall_pass,
        "verdicts": verdicts,
    },
}
path = OUT / "phase_VI_validation_results.json"
with open(path, "w") as f:
    json.dump(results, f, indent=2, default=str)
print(f"\n[SAVED] phase_VI_validation_results.json")
print(f"[DONE] Phase VI patch validation complete.")
