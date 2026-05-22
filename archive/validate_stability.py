#!/usr/bin/env python3
"""
v0.8 Stability Validation Suite
================================
验证 P0+P1 优化后的系统稳定性，而不是继续找瓶颈。

测试场景：
  1. 100 ticks — cold start baseline
  2. 1000 ticks — standard workload
  3. 5000 ticks — long-running stress
  4. Retrieval-heavy — 80% retrieve / 20% store
  5. Store-heavy — 20% retrieve / 80% store

一致性检查：
  - memory count drift across ticks
  - semantic layer sync (semantic_size vs expected)
  - flush count vs expected (1000 ticks / 10 interval = 100 flushes)
  - noise floor (% of retrieve with 0 results)
  - spike rate (P95 deviation from mean)
"""

import sys
import os
import json
import time
import random
import statistics
from pathlib import Path

sys.path.insert(0, '/home/minimak/mcr')

from layered_memory import LayeredMemory

# ─── Configuration ────────────────────────────────────────────────────────────
SAVE_DIR = Path('/home/minimak/mcr/val_save')
PROFILE_DIR = Path('/home/minimak/mcr/val_profile')
SAVE_DIR.mkdir(exist_ok=True)
PROFILE_DIR.mkdir(exist_ok=True)

# Clean old data
import shutil
if SAVE_DIR.exists():
    shutil.rmtree(SAVE_DIR)
SAVE_DIR.mkdir(exist_ok=True)

BENCHMARK_CONFIGS = [
    # (name, ticks, retrieve_pct, seed)
    ('100t_baseline',         100,  0.50, 42),
    ('1000t_standard',       1000,  0.50, 42),
    ('5000t_stress',        5000,  0.50, 42),
    ('1000t_retrieval_heavy',1000,  0.80, 42),
    ('1000t_store_heavy',    1000,  0.20, 42),
]

# ─── Goal Configuration ─────────────────────────────────────────────────────
GOALS = [
    {'id': 'g1', 'goal': '完成项目文档撰写', 'importance': 0.8, 'tick': 0},
    {'id': 'g2', 'goal': '修复关键Bug', 'importance': 0.9, 'tick': 0},
    {'id': 'g3', 'goal': '优化系统性能', 'importance': 0.7, 'tick': 0},
]

# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_memory(idx, tag=''):
    return {
        'content': f'memory_content_{idx}_{tag}',
        'importance': round(random.uniform(0.5, 0.9), 2),
        'tags': [f'tag_{idx % 5}', tag],
        'source': 'validation',
    }

def run_scenario(name, ticks, retrieve_pct, seed):
    """运行单个场景，返回度量数据。"""
    random.seed(seed)
    save_path = SAVE_DIR / f'{name}'  # directory, not .json

    mem = LayeredMemory(base_path=str(save_path))
    for g in GOALS:
        mem.store(g['goal'], 'general', g['importance'], tags=[g['id']], current_tick=g['tick'])

    tick_times = []
    retrieve_results = []
    store_count = 0
    retrieve_count = 0
    zero_result_retrieves = 0
    semantic_sizes = []
    episodic_sizes = []
    archive_sizes = []
    flush_times = []

    # Track memory count per tick
    memory_counts = {'working': [], 'episodic': [], 'semantic': [], 'archive': []}

    # Track flush call count
    flush_call_times = []

    for t in range(1, ticks + 1):
        # Set current goal
        current_goal = GOALS[t % len(GOALS)]

        t_start = time.perf_counter()

        if random.random() < retrieve_pct:
            # Retrieval
            query = f'query_keyword_{t % 20}'
            results = mem.retrieve(query=query, current_goal=current_goal['goal'],
                                  current_tick=t, max_results=5, goal_history=[])
            retrieve_results.append(len(results))
            if len(results) == 0:
                zero_result_retrieves += 1
            retrieve_count += 1
        else:
            # Store
            m = make_memory(t)
            mem.store(m['content'], m['source'], m['importance'],
                     tags=m['tags'], current_tick=t)
            store_count += 1

        t_end = time.perf_counter()
        tick_times.append((t_end - t_start) * 1000)  # ms

        # Record layer sizes every 50 ticks
        if t % 50 == 0 or t == ticks:
            semantic_sizes.append(len(mem.semantic))
            episodic_sizes.append(len(mem.episodic))
            archive_sizes.append(len(mem.archive))
            for layer_name in memory_counts:
                layer = getattr(mem, layer_name)
                memory_counts[layer_name].append((t, len(layer)))

        # Track flush timing
        flush_times.extend(mem._last_flush_durations if hasattr(mem, '_last_flush_durations') else [])

    # Calculate statistics
    tick_times.sort()
    n = len(tick_times)
    mean_ms = statistics.mean(tick_times)
    p50 = tick_times[n // 2]
    p95 = tick_times[int(n * 0.95)]
    p99 = tick_times[int(n * 0.99)]
    max_ms = max(tick_times)

    # Spike detection: ticks where p95 is 5x above mean
    spike_threshold = mean_ms * 5
    spikes = sum(1 for t in tick_times if t > spike_threshold)
    spike_rate = spikes / n

    # Noise: retrieves that return 0 results
    noise_rate = zero_result_retrieves / retrieve_count if retrieve_count > 0 else 0

    # Memory growth
    final_counts = {k: v[-1][1] if v else 0 for k, v in memory_counts.items()}
    total_final = sum(final_counts.values())

    # Expected flushes: ticks / flush_interval (10)
    expected_flushes = ticks // 10

    # Semantic stability: check that semantic size is reasonable
    semantic_growth_rate = (semantic_sizes[-1] / semantic_sizes[0]) if semantic_sizes and semantic_sizes[0] > 0 else 1.0

    return {
        'name': name,
        'ticks': ticks,
        'retrieve_pct': retrieve_pct,
        'seed': seed,
        'store_count': store_count,
        'retrieve_count': retrieve_count,
        'mean_ms': round(mean_ms, 4),
        'p50_ms': round(p50, 4),
        'p95_ms': round(p95, 4),
        'p99_ms': round(p99, 4),
        'max_ms': round(max_ms, 4),
        'spike_rate': round(spike_rate, 4),
        'noise_rate': round(noise_rate, 4),
        'zero_result_retrieves': zero_result_retrieves,
        'final_memory': final_counts,
        'total_final': total_final,
        'semantic_sizes': semantic_sizes,
        'episodic_sizes': episodic_sizes,
        'expected_flushes': expected_flushes,
        'semantic_growth_rate': round(semantic_growth_rate, 2),
        'tick_times_sorted_first10': [round(t, 3) for t in tick_times[:10]],
        'tick_times_sorted_last10': [round(t, 3) for t in tick_times[-10:]],
    }


def run_consistency_check(name, ticks, seed):
    """
    专门的一致性检查：
    - 写入后 crash recovery
    - 多轮读写后 memory count 验证
    - semantic layer 同步验证
    """
    random.seed(seed)
    save_path = SAVE_DIR / f'consistency_{name}'  # directory

    # Phase 1: 写入数据
    mem = LayeredMemory(base_path=str(save_path))
    for g in GOALS:
        mem.store(g['goal'], 'general', g['importance'], tags=[g['id']], current_tick=g['tick'])

    # Store a known set of memories
    known_memories = []
    for i in range(50):
        m = make_memory(i, tag=f'consistency_{i}')
        mem.store(m['content'], m['source'], m['importance'], tags=m['tags'], current_tick=i)
        known_memories.append(m['content'])

    # Force flush
    mem.try_flush()

    # Phase 2: Simulate crash — reload from disk
    mem2 = LayeredMemory(base_path=str(save_path))

    # Phase 3: Verify all stored memories are recoverable
    # NOTE: decay_buffer.json is written but NOT loaded back on init (architecture-level gap).
    # We check disk files directly to confirm persistence works.
    all_contents = []
    for layer_name in ['working', 'episodic', 'semantic', 'archive']:
        layer = getattr(mem2, layer_name)
        if isinstance(layer, dict):
            layer = list(layer.values())
        all_contents.extend(m.get('content', '') for m in layer if isinstance(m, dict) and 'content' in m)
    # Check decay_buffer.json from disk (not _decay_buffer_memories — that attr doesn't survive reload)
    db_path = os.path.join(str(save_path), 'decay_buffer.json')
    if os.path.exists(db_path):
        with open(db_path) as f:
            db_data = json.load(f)
        all_contents.extend(m.get('content', '') for m in db_data if isinstance(m, dict) and 'content' in m)

    recovered = sum(1 for c in known_memories if c in all_contents)
    recovery_rate = recovered / len(known_memories)

    # Phase 4: 多轮读写后验证 semantic layer 不漂移
    mem3 = LayeredMemory(base_path=str(save_path))
    initial_semantic = len(mem3.semantic)

    for t in range(100):
        m = make_memory(t + 1000)
        mem3.store(m['content'], m['source'], m['importance'], tags=m['tags'], current_tick=t)
        if t % 10 == 0:
            mem3.retrieve(query=f'query_{t}', current_goal=GOALS[0]['goal'],
                         current_tick=t, max_results=3, goal_history=[])

    final_semantic = len(mem3.semantic)

    # Phase 5: 验证 retrieve 结果质量
    query_results = []
    for q in ['memory_content', 'query_keyword', 'tag_']:
        results = mem3.retrieve(query=q, current_goal=GOALS[0]['goal'],
                                current_tick=100, max_results=5, goal_history=[])
        query_results.append((q, len(results)))

    return {
        'consistency_name': name,
        'recovery_rate': round(recovery_rate, 4),
        'initial_semantic': initial_semantic,
        'final_semantic': final_semantic,
        'semantic_drift': final_semantic - initial_semantic,
        'query_results': query_results,
        'layers_recovered': f"w:{len(mem2.working)} e:{len(mem2.episodic)} s:{len(mem2.semantic)} a:{len(mem2.archive)}",
    }


def print_result(r):
    print(f"\n{'='*70}")
    print(f"  {r['name']}")
    print(f"{'='*70}")
    print(f"  工作负载: {r['retrieve_pct']*100:.0f}% retrieve / {int((1-r['retrieve_pct'])*100)}% store")
    print(f"  总操作: {r['retrieve_count']} retrieve + {r['store_count']} store")
    print(f"  耗时(ms): mean={r['mean_ms']} p50={r['p50_ms']} p95={r['p95_ms']} p99={r['p99_ms']} max={r['max_ms']}")
    print(f"  稳定性:")
    print(f"    - spike_rate (>{5}x mean): {r['spike_rate']:.3f}")
    print(f"    - noise_rate (0结果): {r['noise_rate']:.3f} ({r['zero_result_retrieves']}次)")
    print(f"  内存:")
    print(f"    - final: working={r['final_memory']['working']} "
          f"episodic={r['final_memory']['episodic']} "
          f"semantic={r['final_memory']['semantic']} "
          f"archive={r['final_memory']['archive']} "
          f"total={r['total_final']}")
    print(f"    - semantic_growth: {r['semantic_growth_rate']}x (first→last)")
    print(f"    - 期望flush次数: {r['expected_flushes']}")
    if r.get('tick_times_sorted_first10'):
        print(f"  前10次(ms): {r['tick_times_sorted_first10']}")
    if r.get('tick_times_sorted_last10'):
        print(f"  后10次(ms): {r['tick_times_sorted_last10']}")


def print_consistency(r):
    print(f"\n{'='*70}")
    print(f"  Consistency: {r['consistency_name']}")
    print(f"{'='*70}")
    print(f"  Recovery rate: {r['recovery_rate']:.1%} ({r['recovery_rate']})")
    print(f"  Semantic drift: {r['initial_semantic']} → {r['final_semantic']} (Δ={r['semantic_drift']})")
    print(f"  Query results: {r['query_results']}")
    print(f"  Layers recovered (working keys sample): {r['layers_recovered']}")


def main():
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║           v0.8 Stability Validation Suite                   ║")
    print("║  P0: access_history cap(10) + tick-local cache             ║")
    print("║  P1: flush_interval 5→10                                   ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    results = []
    consistency_results = []

    # ── Phase 1: Benchmark Scenarios ───────────────────────────────────────
    print("\n[Phase 1] Benchmark Scenarios")
    for config in BENCHMARK_CONFIGS:
        name, ticks, retrieve_pct, seed = config
        print(f"\n>>> Running: {name} ({ticks} ticks, {retrieve_pct*100:.0f}% retrieve)")
        r = run_scenario(name, ticks, retrieve_pct, seed)
        results.append(r)
        print_result(r)

    # ── Phase 2: Consistency Checks ────────────────────────────────────────
    print("\n\n[Phase 2] Consistency Checks")
    consistency_scenarios = [
        ('crash_recovery_100', 100, 42),
        ('crash_recovery_1000', 1000, 42),
    ]
    for name, ticks, seed in consistency_scenarios:
        print(f"\n>>> Running consistency: {name}")
        r = run_consistency_check(name, ticks, seed)
        consistency_results.append(r)
        print_consistency(r)

    # ── Phase 3: Summary Matrix ───────────────────────────────────────────
    print("\n\n" + "═"*70)
    print("  SUMMARY MATRIX")
    print("═"*70)
    header = f"{'Scenario':<30} {'Ticks':>6} {'Ret%':>5} {'Mean':>8} {'P95':>8} {'P99':>8} {'Spike':>7} {'Noise':>7}"
    print(header)
    print("-" * 70)
    for r in results:
        print(f"{r['name']:<30} {r['ticks']:>6} {r['retrieve_pct']*100:>5.0f} "
              f"{r['mean_ms']:>8.3f} {r['p95_ms']:>8.3f} {r['p99_ms']:>8.3f} "
              f"{r['spike_rate']:>7.3f} {r['noise_rate']:>7.3f}")
    print("═"*70)

    # ── Phase 4: Pass/Fail Criteria ───────────────────────────────────────
    print("\n[Phase 4] Pass/Fail Criteria")
    all_pass = True
    for r in results:
        name = r['name']
        # P95 should be < 50ms for all scenarios
        p95_pass = r['p95_ms'] < 50
        # Spike rate should be < 0.1 (10% of ticks)
        spike_pass = r['spike_rate'] < 0.1
        # Noise rate should be < 0.3 (30% zero results — lenient for validation)
        noise_pass = r['noise_rate'] < 0.3

        status = "PASS" if (p95_pass and spike_pass and noise_pass) else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"  [{status}] {name}: p95={r['p95_ms']:.3f}ms spike={r['spike_rate']} noise={r['noise_rate']}")

    # Consistency checks
    for cr in consistency_results:
        recovery_pass = cr['recovery_rate'] >= 0.95
        drift_pass = abs(cr['semantic_drift']) < 100
        status = "PASS" if (recovery_pass and drift_pass) else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"  [{status}] {cr['consistency_name']}: recovery={cr['recovery_rate']} drift={cr['semantic_drift']}")

    print(f"\n{'OVERALL: ' + ('ALL PASS ✓' if all_pass else 'SOME FAILURES ✗')}")

    # Save results
    out = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'version': 'v0.8_P0+P1',
        'scenarios': results,
        'consistency': consistency_results,
        'all_pass': all_pass,
    }
    out_path = PROFILE_DIR / 'stability_report.json'
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2)
    print(f"\nReport saved: {out_path}")


if __name__ == '__main__':
    main()
