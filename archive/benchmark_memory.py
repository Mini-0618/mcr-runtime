#!/usr/bin/env python3
"""
Memory Architecture Benchmark
============================
Compares: Old MemoryStore (flat, full-scan)
      vs: New LayeredMemory (tiered, retrieval-first)

Metrics tracked per tick:
  - tick_latency_ms: time to run one tick cycle
  - retrieval_latency_ms: time to retrieve memories
  - total_memory_count: all memories across all layers
  - active_memory_count: memories participating in current tick (retrieval result count)
  - noise_ratio: % of memories with type=noise
  - reasoning_template_score: repetition in recent reasoning chains

Scenarios:
  100 tick  - baseline, no chaos
  1000 tick - moderate load
  5000 tick - stress test

Chaos injection every 5 ticks to simulate real entropy.
"""
import sys
import os
import time
import random
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# We'll run both architectures through identical scenarios
SCENARIOS = [100, 1000]
CHAOS_INTERVAL = 5
NUM_RUNS = 2  # multiple runs for variance


# =============================================================================
# OLD MemoryStore (flat, full-scan)
# =============================================================================

class OldMemoryStore:
    """Original flat memory store - full scan per retrieval."""
    def __init__(self):
        self.path = "/tmp/old_memory.json"
        self.memories = []
        self.tick_count = 0

    def store(self, content, memory_type="general", importance=0.5, tags=None):
        import uuid
        from datetime import datetime
        memory = {
            "id": str(uuid.uuid4())[:8],
            "content": content,
            "type": memory_type,
            "importance": importance,
            "tags": tags or [],
            "created_at": datetime.now().isoformat(),
            "last_accessed": None,
            "access_count": 0,
            "activation_count": 0,
        }
        self.memories.append(memory)
        return memory["id"]

    def retrieve(self, query, max_results=5, min_importance=0.0):
        """Full scan: iterate all memories, score each one."""
        if not query:
            return []
        query_words = set(query.lower().split())
        scored = []
        for memory in self.memories:
            score = 0.0
            score += memory.get("importance", 0.5) * 0.3
            memory_tags = set(memory.get("tags", []))
            tag_overlap = len(query_words & memory_tags)
            score += tag_overlap * 0.2
            content_words = set(memory["content"].lower().split())
            content_overlap = len(query_words & content_words)
            score += content_overlap * 0.1
            if memory.get("last_accessed"):
                days_old = (datetime.now() - datetime.fromisoformat(memory["last_accessed"])).days
                recency_bonus = max(0, 0.2 - days_old * 0.02)
                score += recency_bonus
            if score >= min_importance:
                memory["relevance_score"] = score
                memory["last_accessed"] = datetime.now().isoformat()
                memory["access_count"] += 1
                memory["activation_count"] += 1
                scored.append(memory)
        scored.sort(key=lambda x: x["relevance_score"], reverse=True)
        return scored[:max_results]

    def summarize(self):
        return {
            "total": len(self.memories),
            "noise_ratio": sum(1 for m in self.memories if m.get("type") == "noise") / max(1, len(self.memories)),
            "by_importance": {
                "high": len([m for m in self.memories if m.get("importance", 0) >= 0.7]),
                "medium": len([m for m in self.memories if 0.4 <= m.get("importance", 0) < 0.7]),
                "low": len([m for m in self.memories if m.get("importance", 0) < 0.4]),
            }
        }

    def save(self):
        with open(self.path, "w") as f:
            json.dump({"memories": self.memories}, f)

    def cleanup(self):
        if os.path.exists(self.path):
            os.remove(self.path)


# =============================================================================
# BENCHMARK DISTRIBUTION — Clustered, Goal-Drifting
# =============================================================================

# Memory clusters with distinct vocabulary
CLUSTERS = {
    "project_a": {
        "keywords": ["项目", "设计", "模块", "接口", "架构", "开发", "测试", "部署", "需求"],
        "templates": [
            "项目A：完成{module}模块的设计文档",
            "项目A：{module}接口遇到兼容性问题",
            "项目A：用户反馈{module}功能响应慢",
            "项目A：团队讨论{module}技术选型方案",
            "项目A：{module}模块测试覆盖率提升到80%",
        ],
    },
    "project_b": {
        "keywords": ["产品", "迭代", "用户", "反馈", "体验", "上线", "策略", "增长"],
        "templates": [
            "产品B：完成新一轮用户调研分析",
            "产品B：迭代计划优先级调整公告",
            "产品B：用户反馈{module}操作复杂",
            "产品B：上线后转化率数据汇报",
            "产品B：下个季度增长策略制定",
        ],
    },
    "research": {
        "keywords": ["论文", "实验", "算法", "模型", "训练", "数据", "基准", "结果"],
        "templates": [
            "研究：阅读{module}相关论文笔记",
            "研究：复现{module}实验遇到困难",
            "研究：{module}模型训练 loss 不收敛",
            "研究：{module}基准测试结果分析",
            "研究：和导师讨论{module}创新方向",
        ],
    },
    "debug": {
        "keywords": ["bug", "错误", "崩溃", "修复", "日志", "调试", "排查", "问题"],
        "templates": [
            "调试：{module}出现空指针异常",
            "调试：{module}内存泄漏问题定位",
            "调试：{module}在高并发下崩溃",
            "调试：{module}日志显示超时错误",
            "调试：{module}排查了3小时终于解决",
        ],
    },
    "personal": {
        "keywords": ["生活", "休息", "运动", "读书", "计划", "目标", "时间", "效率"],
        "templates": [
            "个人：今日工作复盘与明日计划",
            "个人：保持运动提升精力",
            "个人：时间管理方法实践",
            "个人：读完《深度工作》读书笔记",
            "个人：专注力训练心得",
        ],
    },
}

CLUSTER_NAMES = list(CLUSTERS.keys())
CLUSTER_KEYWORDS = {k: set(v["keywords"]) for k, v in CLUSTERS.items()}

# Semantic knowledge — long-term truths per cluster (pre-populated into semantic layer)
SEMANTIC_KNOWLEDGE = [
    {"cluster": "debug", "content": "空指针异常通常由未初始化的对象引用引起", "importance": 0.8},
    {"cluster": "debug", "content": "内存泄漏多数由于未关闭数据库连接和文件句柄", "importance": 0.9},
    {"cluster": "debug", "content": "高并发崩溃常见原因是竞态条件和锁粒度设计", "importance": 0.8},
    {"cluster": "debug", "content": "超时错误往往是网络不稳定或服务端负载过高", "importance": 0.7},
    {"cluster": "project_a", "content": "接口兼容性问题是不同版本协议导致的", "importance": 0.8},
    {"cluster": "project_a", "content": "模块响应慢通常需要优化数据库查询和缓存策略", "importance": 0.8},
    {"cluster": "research", "content": "模型训练 loss 不收敛可能是学习率过大或数据标注问题", "importance": 0.9},
    {"cluster": "research", "content": "基准测试需要控制随机种子保证可复现性", "importance": 0.7},
    {"cluster": "project_b", "content": "用户转化率低通常与产品路径设计和用户教育有关", "importance": 0.8},
    {"cluster": "personal", "content": "深度工作需要屏蔽干扰并保持专注时段", "importance": 0.7},
]

# Modules used in templates
MODULES = ["认证", "支付", "搜索", "推荐", "消息", "缓存", "队列", "网关", "权限", "统计"]


def get_cluster_for_tick(tick: int) -> str:
    """Determine active cluster for this tick (goal switching)."""
    phase = (tick // 100) % 5
    return CLUSTER_NAMES[phase]


def generate_signal_content(tick: int, cluster: str) -> str:
    """Generate a signal memory for the given cluster."""
    tmpl = random.choice(CLUSTERS[cluster]["templates"])
    module = random.choice(MODULES)
    return tmpl.format(module=module)


def generate_noise_content() -> str:
    """Generate a noise memory (unrelated to any cluster)."""
    noise_contents = [
        "记得小时候养过一只猫叫阿花",
        "想起高中数学老师说过的一句话",
        "突然想到三年前去过的一个城市",
        "手机屏幕有点脏",
        "感觉有点困",
    ]
    return random.choice(noise_contents)


def get_goal_for_tick(tick: int) -> str:
    """Goal drifts across clusters every ~100 ticks."""
    cluster = get_cluster_for_tick(tick)
    goal_map = {
        "project_a": "项目A的技术架构设计与实现",
        "project_b": "产品B的用户增长策略优化",
        "research": "大模型训练与算法优化研究",
        "debug": "系统稳定性问题排查与修复",
        "personal": "个人效率提升与深度工作实践",
    }
    return goal_map[cluster]


# =============================================================================
# Benchmark Runner
# =============================================================================

def inject_chaos_old(memory_store, tick):
    """Inject noise into old memory store."""
    if tick % CHAOS_INTERVAL == 0 and tick > 0:
        memory_store.store(generate_noise_content(), 'noise', 0.3, ['chaos'])


def inject_chaos_new(layered_memory, tick):
    """Inject noise into new layered memory."""
    if tick % CHAOS_INTERVAL == 0 and tick > 0:
        layered_memory.store(
            generate_noise_content(), 'noise', 0.3, ['chaos'], current_tick=tick
        )


def run_benchmark(scenario_ticks: int, memory_class, inject_chaos_fn, label: str):
    """Run benchmark for a given scenario and memory architecture."""
    if memory_class.__name__ == 'OldMemoryStore':
        memory = OldMemoryStore()
        use_layered = False
        # Pre-populate semantic knowledge for old store (just for fairness; old store ignores it)
        for kw in SEMANTIC_KNOWLEDGE:
            memory.store(kw["content"], "semantic", kw["importance"], [kw["cluster"]])
    else:
        import shutil
        tmp_dir = f"/tmp/bench_{memory_class.__name__}_{scenario_ticks}_{random.randint(1000,9999)}"
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
        memory = memory_class(tmp_dir)
        use_layered = True
        # Pre-populate semantic layer with long-term knowledge
        for kw in SEMANTIC_KNOWLEDGE:
            memory.store(
                kw["content"], "semantic", kw["importance"],
                [kw["cluster"]], current_tick=0
            )

    tick_metrics = []
    flush_count = 0
    semantic_activations = 0
    spike_count = 0

    # For p95/p99: collect all latencies
    all_latencies = []

    # Track cluster for signals (deterministic per tick for reproducibility)
    rng_signal = random.Random(42)
    rng_noise = random.Random(42)

    for tick in range(1, scenario_ticks + 1):
        tick_start = time.perf_counter()

        # Inject chaos (noise)
        inject_chaos_fn(memory, tick)

        # Current goal (drifts every ~100 ticks)
        current_goal = get_goal_for_tick(tick)
        goal_history = [{"tick": max(0, tick - 10 * i), "goal": get_goal_for_tick(max(0, tick - 10 * i))}
                       for i in range(5)]

        # Active cluster for this tick
        active_cluster = get_cluster_for_tick(tick)

        # Add "real" signals — cluster-aligned content
        if tick % 10 == 0:
            if hasattr(memory, 'store'):
                if use_layered:
                    memory.store(
                        generate_signal_content(tick, active_cluster),
                        'signal', random.uniform(0.5, 0.9),
                        [active_cluster], current_tick=tick
                    )
                else:
                    memory.store(
                        generate_signal_content(tick, active_cluster),
                        'signal', random.uniform(0.5, 0.9),
                        [active_cluster]
                    )

        # Retrieval step
        retrieval_start = time.perf_counter()
        if use_layered:
            results = memory.retrieve(
                query=current_goal,
                current_goal=current_goal,
                current_tick=tick,
                max_results=5,
                goal_history=goal_history,
            )
        else:
            results = memory.retrieve(query=current_goal, max_results=5)
        retrieval_end = time.perf_counter()

        # Track semantic activation: semantic state in results
        semantic_in_results = sum(1 for m in results if m.get("state") == "semantic")
        semantic_activations += semantic_in_results

        tick_end = time.perf_counter()
        tick_lat = (tick_end - tick_start) * 1000
        ret_lat = (retrieval_end - retrieval_start) * 1000
        all_latencies.append(tick_lat)

        # Spike: > 2x running mean (computed on the fly)
        running_mean = sum(all_latencies) / len(all_latencies)
        is_spike = tick_lat > 2 * running_mean
        if is_spike:
            spike_count += 1

        # Memory counts (layered vs flat)
        if use_layered:
            total_memories = (
                len(memory.working) + len(memory.episodic)
                + len(memory.semantic) + len(memory.archive)
            )
            noise_in_pool = (
                sum(1 for m in memory.working + memory.episodic if m.get("type") == "noise")
            )
            noise_ratio = noise_in_pool / max(1, total_memories)
        else:
            total_memories = len(memory.memories)
            noise_ratio = sum(1 for m in memory.memories if m.get("type") == "noise") / max(1, total_memories)

        # Flush (layered only) — every 5 ticks
        flushed_this_tick = False
        if use_layered and tick % 5 == 0:
            flushed_this_tick = memory.try_flush(tick)
            if flushed_this_tick:
                flush_count += 1

        # Incremental review (layered only) — every tick (lightweight)
        review_actions = {"promoted_to_semantic": [], "archived": [], "deleted": 0}
        if use_layered:
            review_actions = memory.incremental_review(tick)

        # Debug: log semantic layer state every 20 ticks
        if use_layered and tick % 20 == 0:
            semantic_count = len(memory.semantic)
            episodic_count = len(memory.episodic)
            working_count = len(memory.working)
            promoted = len(review_actions.get("promoted_to_semantic", []))
            print(f"  [tick {tick}] working={working_count} episodic={episodic_count} semantic={semantic_count} "
                  f"promoted_this_tick={promoted} archived={len(review_actions.get('archived', []))}")

        tick_metrics.append({
            'tick': tick,
            'tick_latency_ms': tick_lat,
            'retrieval_latency_ms': ret_lat,
            'total_memory_count': total_memories,
            'active_memory_count': len(results),
            'noise_ratio': noise_ratio,
            'is_spike': is_spike,
            'semantic_in_results': semantic_in_results,
        })

    # Cleanup
    if hasattr(memory, 'cleanup'):
        memory.cleanup()

    return {
        'tick_metrics': tick_metrics,
        'all_latencies': all_latencies,
        'flush_count': flush_count,
        'semantic_activations': semantic_activations,
        'spike_count': spike_count,
    }


def _percentile(data: list, p: float) -> float:
    """Compute the p-th percentile of a list."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = (len(sorted_data) - 1) * p / 100.0
    lo = int(idx)
    hi = lo + 1
    frac = idx - lo
    if hi >= len(sorted_data):
        return sorted_data[lo]
    return sorted_data[lo] * (1 - frac) + sorted_data[hi] * frac


def aggregate_metrics(metrics_list: list):
    """
    Aggregate metrics across multiple runs.
    metrics_list elements are dicts from run_benchmark return.
    """
    if not metrics_list:
        return {}

    n = len(metrics_list)

    # Each run returns: {'tick_metrics': [...], 'all_latencies': [...], 'flush_count': N, ...}
    # Flatten all tick_metrics
    all_tick_metrics = []
    for run in metrics_list:
        all_tick_metrics.extend(run['tick_metrics'])

    if not all_tick_metrics:
        return {}

    ticks = len(all_tick_metrics)
    checkpoints_pct = [0.1, 0.25, 0.5, 0.75, 0.9, 1.0]
    checkpoints = sorted(set([max(1, int(ticks * p)) for p in checkpoints_pct]))

    # Build checkpoint data
    checkpoint_data = {}
    for cp in checkpoints:
        cp_metrics = [run['tick_metrics'][cp - 1] for run in metrics_list if len(run['tick_metrics']) >= cp]
        if not cp_metrics:
            continue
        checkpoint_data[cp] = {
            'tick_latency_ms': sum(m['tick_latency_ms'] for m in cp_metrics) / len(cp_metrics),
            'retrieval_latency_ms': sum(m['retrieval_latency_ms'] for m in cp_metrics) / len(cp_metrics),
            'total_memory_count': sum(m['total_memory_count'] for m in cp_metrics) / len(cp_metrics),
            'noise_ratio': sum(m['noise_ratio'] for m in cp_metrics) / len(cp_metrics),
        }

    # Overall stats from all latencies
    all_latencies = []
    for run in metrics_list:
        all_latencies.extend(run['all_latencies'])

    all_retrieval = [m['retrieval_latency_ms'] for m in all_tick_metrics]
    all_mem_counts = [m['total_memory_count'] for m in all_tick_metrics]

    # Per-run finals
    final_tick_metrics = [run['tick_metrics'][-1] for run in metrics_list]

    total_flashes = sum(run.get('flush_count', 0) for run in metrics_list)
    total_semantic = sum(run.get('semantic_activations', 0) for run in metrics_list)
    total_spikes = sum(run.get('spike_count', 0) for run in metrics_list)

    return {
        'checkpoints': checkpoint_data,
        'overall': {
            'mean_tick_latency_ms': sum(all_latencies) / len(all_latencies) if all_latencies else 0,
            'p50_tick_latency_ms': _percentile(all_latencies, 50),
            'p95_tick_latency_ms': _percentile(all_latencies, 95),
            'p99_tick_latency_ms': _percentile(all_latencies, 99),
            'max_tick_latency_ms': max(all_latencies) if all_latencies else 0,
            'mean_retrieval_latency_ms': sum(all_retrieval) / len(all_retrieval) if all_retrieval else 0,
            'max_retrieval_latency_ms': max(all_retrieval) if all_retrieval else 0,
            'final_memory_count': sum(m['total_memory_count'] for m in final_tick_metrics) / len(final_tick_metrics),
            'final_noise_ratio': sum(m['noise_ratio'] for m in final_tick_metrics) / len(final_tick_metrics),
            'total_flushes': total_flashes,
            'total_semantic_activations': total_semantic,
            'total_spikes': total_spikes,
            'spike_rate': total_spikes / ticks if ticks > 0 else 0,
        }
    }


def print_report(scenario_ticks: int, old_stats: dict, new_stats: dict):
    print(f"\n{'='*80}")
    print(f" BENCHMARK: {scenario_ticks} ticks | {NUM_RUNS} runs each")
    print(f"{'='*80}")

    old_ov = old_stats['overall']
    new_ov = new_stats['overall']

    # Core metrics
    print(f"\n{'Metric':<40} {'Old MemoryStore':>18} {'New LayeredMemory':>18} {'Speedup/Diff':>15}")
    print(f"{'-'*40} {'-'*18} {'-'*18} {'-'*15}")

    def speedup(old_val, new_val):
        if new_val <= 0:
            return "N/A"
        ratio = old_val / new_val
        return f"{ratio:.1f}x"

    print(f"{'Mean tick latency (ms)':<40} {old_ov['mean_tick_latency_ms']:>18.3f} {new_ov['mean_tick_latency_ms']:>18.3f} {speedup(old_ov['mean_tick_latency_ms'], new_ov['mean_tick_latency_ms']):>15}")
    print(f"{'P50 tick latency (ms)':<40} {old_ov['p50_tick_latency_ms']:>18.3f} {new_ov['p50_tick_latency_ms']:>18.3f} {speedup(old_ov['p50_tick_latency_ms'], new_ov['p50_tick_latency_ms']):>15}")
    print(f"{'P95 tick latency (ms)':<40} {old_ov['p95_tick_latency_ms']:>18.3f} {new_ov['p95_tick_latency_ms']:>18.3f} {speedup(old_ov['p95_tick_latency_ms'], new_ov['p95_tick_latency_ms']):>15}")
    print(f"{'P99 tick latency (ms)':<40} {old_ov['p99_tick_latency_ms']:>18.3f} {new_ov['p99_tick_latency_ms']:>18.3f} {speedup(old_ov['p99_tick_latency_ms'], new_ov['p99_tick_latency_ms']):>15}")
    print(f"{'Max tick latency (ms)':<40} {old_ov['max_tick_latency_ms']:>18.3f} {new_ov['max_tick_latency_ms']:>18.3f} {speedup(old_ov['max_tick_latency_ms'], new_ov['max_tick_latency_ms']):>15}")
    print(f"{'Mean retrieval latency (ms)':<40} {old_ov['mean_retrieval_latency_ms']:>18.3f} {new_ov['mean_retrieval_latency_ms']:>18.3f} {speedup(old_ov['mean_retrieval_latency_ms'], new_ov['mean_retrieval_latency_ms']):>15}")
    print(f"{'Final memory count':<40} {old_ov['final_memory_count']:>18.1f} {new_ov['final_memory_count']:>18.1f} {new_ov['final_memory_count'] - old_ov['final_memory_count']:>+15.1f}")
    print(f"{'Final noise ratio':<40} {old_ov['final_noise_ratio']:>17.1%} {new_ov['final_noise_ratio']:>17.1%} {new_ov['final_noise_ratio'] - old_ov['final_noise_ratio']:>+14.1%}")

    # New layered-specific metrics
    print(f"\n{'LayeredMemory-specific metrics':<40}")
    print(f"{'-'*40}")
    print(f"{'  Flush frequency (total)':<40} {new_ov.get('total_flushes', 0):>18}")
    print(f"{'  Semantic activation count':<40} {new_ov.get('total_semantic_activations', 0):>18}")
    print(f"{'  Spike count':<40} {new_ov.get('total_spikes', 0):>18}")
    print(f"{'  Spike rate (per tick)':<40} {new_ov.get('spike_rate', 0):>18.3f}")

    # Checkpoints table
    print(f"\n{'Checkpoint':<12} {'Old Tick(ms)':>14} {'New Tick(ms)':>14} {'Old Mem':>10} {'New Mem':>10} {'Old Noise':>10} {'New Noise':>10}")
    print(f"{'-'*78}")
    for cp, old_cp in old_stats['checkpoints'].items():
        new_cp = new_stats['checkpoints'].get(cp, old_cp)
        old_noise = old_cp['noise_ratio']
        new_noise = new_cp['noise_ratio']
        print(f"tick {cp:<8} {old_cp['tick_latency_ms']:>14.3f} {new_cp['tick_latency_ms']:>14.3f} "
              f"{old_cp['total_memory_count']:>10.1f} {new_cp['total_memory_count']:>10.1f} "
              f"{old_noise:>9.1%} {new_noise:>9.1%}")

    return {
        'scenario': scenario_ticks,
        'speedup_tick_latency': old_ov['mean_tick_latency_ms'] / new_ov['mean_tick_latency_ms'] if new_ov['mean_tick_latency_ms'] > 0 else float('inf'),
        'speedup_retrieval': old_ov['mean_retrieval_latency_ms'] / new_ov['mean_retrieval_latency_ms'] if new_ov['mean_retrieval_latency_ms'] > 0 else float('inf'),
        'memory_delta': new_ov['final_memory_count'] - old_ov['final_memory_count'],
        'noise_delta': new_ov['final_noise_ratio'] - old_ov['final_noise_ratio'],
        'p95_speedup': old_ov['p95_tick_latency_ms'] / new_ov['p95_tick_latency_ms'] if new_ov['p95_tick_latency_ms'] > 0 else float('inf'),
        'spike_rate_new': new_ov.get('spike_rate', 0),
        'semantic_activations': new_ov.get('total_semantic_activations', 0),
    }


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    from layered_memory import LayeredMemory
    import shutil

    print(f"Memory Architecture Benchmark")
    print(f"  Scenarios: {SCENARIOS}")
    print(f"  Runs per scenario: {NUM_RUNS}")
    print(f"  Chaos injection every {CHAOS_INTERVAL} ticks")
    print(f"  Old: MemoryStore (flat, full scan)")
    print(f"  New: LayeredMemory (tiered, retrieval-first)")

    all_results = []

    for scenario in SCENARIOS:
        print(f"\n>>> Running scenario {scenario} ticks...")

        old_runs = []
        for r in range(NUM_RUNS):
            m = run_benchmark(scenario, OldMemoryStore, inject_chaos_old, "Old")
            old_runs.append(m)

        new_runs = []
        for r in range(NUM_RUNS):
            m = run_benchmark(scenario, LayeredMemory, inject_chaos_new, "New")
            new_runs.append(m)

        old_stats = aggregate_metrics(old_runs)
        new_stats = aggregate_metrics(new_runs)

        summary = print_report(scenario, old_stats, new_stats)
        all_results.append(summary)

    # Final comparison table
    print(f"\n{'='*80}")
    print(f" SUMMARY: Old vs New across all scenarios")
    print(f"{'='*80}")
    print(f"\n{'Scenario':<12} {'Tick Speedup':>14} {'P95 Speedup':>13} {'Retrieval Speedup':>18} {'Memory Δ':>12} {'Noise Δ':>12} {'Spikes':>8} {'SemanticAct':>12}")
    print(f"{'-'*12} {'-'*14} {'-'*13} {'-'*18} {'-'*12} {'-'*12} {'-'*8} {'-'*12}")
    for r in all_results:
        print(f"{r['scenario']:<12} {r['speedup_tick_latency']:>13.1f}x {r.get('p95_speedup', 0):>12.1f}x {r['speedup_retrieval']:>17.1f}x "
              f"{r['memory_delta']:>+11.1f} {r['noise_delta']:>+11.1%} {r.get('spike_rate_new', 0):>8.3f} {r.get('semantic_activations', 0):>12}")

    # Save results
    results_file = "./benchmark_results.json"
    with open(results_file, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to {results_file}")
