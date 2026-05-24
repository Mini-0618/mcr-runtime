#!/usr/bin/env python3
"""
Memory Trace Observer v0.9
==========================
Attaches to LayeredMemory and produces structured trace logs for observability.

Trace categories:
  1. state_transition — memory promotion/demotion/exit events
  2. retrieval_trace  — every retrieve() with scores and rerank decisions
  3. promotion_event  — working→episodic, episodic→semantic, etc.
  4. semantic_activation — semantic layer firing, what it did, why
  5. lifecycle_snapshot — periodic memory count per layer + health metrics
  6. anomaly           — spike, noise burst, recovery failure

Output: structured JSON lines to trace file + in-memory ring buffer for summary

Usage:
  from memory_trace import MemoryTracer
  tracer = MemoryTracer('/path/to/layered_memory_base')
  tracer.run(ticks=5000)  # or integrate into agent loop
"""

import json
import os
import sys
import time
import random
import statistics
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Optional

sys.path.insert(0, '.')
from layered_memory import LayeredMemory

TRACE_DIR = Path('./traces')
TRACE_DIR.mkdir(exist_ok=True)

# ─── Trace Event Types ────────────────────────────────────────────────────────

@dataclass
class TransitionTrace:
    tick: int
    memory_id: str
    memory_content: str
    from_state: str
    to_state: str
    reason: str          # promotion_rule, demotion_rule, hard_cap, decay_expire, etc.
    memory_importance: float
    access_count: int

@dataclass
class RetrievalTrace:
    tick: int
    query: str
    current_goal: str
    latency_ms: float
    results_count: int
    results: list       # [{content, layer, retrieval_score, goal_relevance}]
    semantic_fired: bool
    semantic_scored_count: int
    rerank_modified_count: int
    rerank_decisions: list  # [{memory_id, action, reason}]
    spike: bool

@dataclass
class PromotionTrace:
    tick: int
    memory_id: str
    memory_content: str
    from_layer: str
    to_layer: str
    trigger: str         # access_weight, importance, goal_relevance, periodic_review
    trigger_value: float
    threshold: float

@dataclass
class SemanticActivationTrace:
    tick: int
    candidates_considered: int
    candidates_scored: int
    dedup压制_count: int
    low_value_replace_count: int
    long_term_override_count: int
    net_effect: str      # "reordered_1", "suppressed_2", "no_change"
    affected_memory_ids: list

@dataclass
class LifecycleSnapshot:
    tick: int
    working_count: int
    episodic_count: int
    semantic_count: int
    archive_count: int
    decay_buffer_count: int
    total_memories: int
    mean_tick_ms: float
    p95_tick_ms: float
    spike_rate: float
    noise_rate: float

@dataclass
class AnomalyTrace:
    tick: int
    anomaly_type: str    # spike, noise_burst, semantic_conflict, recovery_gap
    details: dict

# ─── Memory Tracer ────────────────────────────────────────────────────────────

class MemoryTracer:
    """
    Wraps LayeredMemory with full observability.
    Produces trace events and live summary statistics.
    """

    def __init__(self, base_path: str, trace_name: str = None):
        self.base_path = base_path
        self.trace_name = trace_name or f"trace_{int(time.time())}"
        self.trace_path = TRACE_DIR / f"{self.trace_name}.jsonl"
        self.snapshot_path = TRACE_DIR / f"{self.trace_name}_snapshots.jsonl"

        # Open trace files
        self._trace_file = open(self.trace_path, 'w', encoding='utf-8')
        self._snap_file = open(self.snapshot_path, 'w', encoding='utf-8')

        # The actual memory system
        self.mem = LayeredMemory(base_path=base_path)

        # Live state tracking
        self._tick = 0
        self._tick_times = []
        self._retrieve_count = 0
        self._store_count = 0
        self._zero_result_retrieves = 0

        # Event buffers (ring buffers to avoid memory bloat)
        self._transitions = []      # all transition events
        self._retrievals = []       # last N retrievals
        self._promotions = []       # all promotion events
        self._semantic_activations = []  # all semantic activations
        self._anomalies = []        # all anomalies

        # Per-memory trace (for flow graph)
        self._memory_lifecycles = defaultdict(list)  # memory_id -> list of states

        # Snapshot interval
        self._snapshot_interval = 100  # every N ticks

        # Pre-populate semantic knowledge
        self._setup_initial_knowledge()

        # Emit header first so analyzer knows base_path
        self._emit('header', {'base_path': self.base_path, 'scenario': self.trace_name})

    def _setup_initial_knowledge(self):
        """Pre-populate semantic layer with domain knowledge."""
        semantic_knowledge = [
            ('完成项目文档撰写', 'planning', 0.8, '项目管理'),
            ('代码架构设计原则', 'architecture', 0.8, '系统设计'),
            ('性能优化方法论', 'optimization', 0.7, '工程实践'),
            ('修复关键Bug', 'debugging', 0.9, '工程实践'),
            ('用户反馈分析', 'user_research', 0.7, '产品设计'),
            ('数据备份策略', 'infrastructure', 0.8, '运维'),
            ('安全审计检查项', 'security', 0.9, '运维'),
            ('API设计规范', 'architecture', 0.8, '系统设计'),
            ('数据库索引优化', 'optimization', 0.7, '工程实践'),
            ('用户访谈技巧', 'user_research', 0.7, '产品设计'),
        ]
        for content, mem_type, importance, tag in semantic_knowledge:
            self.mem.store(content, mem_type, importance, tags=[tag], current_tick=0)

    def _emit(self, event_type: str, data: dict):
        """Write a single trace line."""
        line = json.dumps({'type': event_type, 'ts': time.time(), 'data': data}, ensure_ascii=False)
        self._trace_file.write(line + '\n')
        self._trace_file.flush()  # ensure written for analyzer

    def _emit_snapshot(self, snap: LifecycleSnapshot):
        """Write a lifecycle snapshot."""
        self._snap_file.write(json.dumps(asdict(snap), ensure_ascii=False) + '\n')

    # ── Hooks into LayeredMemory internals ─────────────────────────────────

    def _hook_store(self, content: str, memory_type: str, importance: float,
                    tags: list, current_tick: int) -> str:
        """Intercept store() to capture the new memory."""
        # Store first to get the memory
        mem_id = self.mem.store(content, memory_type, importance, tags=tags,
                                current_tick=current_tick)
        self._store_count += 1
        # Find the stored memory (in working layer)
        stored_mem = next((m for m in self.mem.working if m['id'] == mem_id), None)
        if stored_mem:
            self._memory_lifecycles[mem_id].append({
                'tick': current_tick,
                'state': 'working',
                'event': 'store'
            })
            self._emit('state_transition', {
                'tick': current_tick,
                'memory_id': mem_id,
                'memory_content': content[:80],
                'from_state': '',
                'to_state': 'working',
                'reason': 'store',
                'memory_importance': importance,
                'access_count': 1
            })
        return mem_id

    def _hook_retrieve(self, query: str, current_goal: str,
                       current_tick: int, max_results: int, goal_history: list):
        """Intercept retrieve() to capture full trace."""
        t_start = time.perf_counter()
        results = self.mem.retrieve(query=query, current_goal=current_goal,
                                   current_tick=current_tick, max_results=max_results,
                                   goal_history=goal_history or [])
        t_end = time.perf_counter()
        latency_ms = (t_end - t_start) * 1000

        self._tick_times.append(latency_ms)
        self._retrieve_count += 1

        # Determine spike (5x mean)
        mean_ms = statistics.mean(self._tick_times) if self._tick_times else 0
        spike = latency_ms > mean_ms * 5 if mean_ms > 0 else False

        # Capture semantic activation info
        semantic_fired = False
        semantic_scored_count = 0
        rerank_modified_count = 0
        rerank_decisions = []

        # Extract semantic layer info from results
        if hasattr(self.mem, '_last_semantic_scored'):
            semantic_fired = True
            semantic_scored_count = len(self.mem._last_semantic_scored)

        if hasattr(self.mem, '_last_rerank_decisions'):
            rerank_decisions = self.mem._last_rerank_decisions
            rerank_modified_count = len(rerank_decisions)

        # Emit retrieval trace
        trace = RetrievalTrace(
            tick=current_tick,
            query=query[:60],
            current_goal=current_goal[:60] if current_goal else '',
            latency_ms=round(latency_ms, 4),
            results_count=len(results),
            results=[{
                'content': r.get('content', '')[:60],
                'layer': r.get('state', 'unknown'),
                'retrieval_score': round(r.get('retrieval_score', 0), 3),
                'goal_relevance': round(r.get('goal_relevance', 0), 3)
            } for r in results],
            semantic_fired=semantic_fired,
            semantic_scored_count=semantic_scored_count,
            rerank_modified_count=rerank_modified_count,
            rerank_decisions=rerank_decisions,
            spike=spike
        )
        self._emit('retrieval_trace', asdict(trace))
        self._retrievals.append(trace)

        # Track zero-result noise
        if len(results) == 0:
            self._zero_result_retrieves += 1
            self._emit('anomaly', {
                'tick': current_tick,
                'anomaly_type': 'noise_burst',
                'details': {'query': query[:60], 'goal': current_goal[:60]}
            })

        # Emit spike anomaly
        if spike:
            self._emit('anomaly', {
                'tick': current_tick,
                'anomaly_type': 'spike',
                'details': {'latency_ms': round(latency_ms, 3), 'mean_ms': round(mean_ms, 3), 'ratio': round(latency_ms/mean_ms, 1) if mean_ms > 0 else 0}
            })

        return results

    def _hook_promote(self, memory: dict, from_layer: str, to_layer: str,
                      reason: str, current_tick: int):
        """Capture promotion/demotion events."""
        self._memory_lifecycles[memory['id']].append({
            'tick': current_tick,
            'state': to_layer,
            'event': reason
        })
        self._emit('promotion_event', {
            'tick': current_tick,
            'memory_id': memory['id'],
            'memory_content': memory.get('content', '')[:80],
            'from_layer': from_layer,
            'to_layer': to_layer,
            'trigger': reason,
            'trigger_value': memory.get('access_weight', 0),
            'threshold': 0  # filled by caller
        })

    def _take_snapshot(self):
        """Emit a lifecycle snapshot."""
        tick_times_sorted = sorted(self._tick_times)
        n = len(tick_times_sorted)
        mean_ms = statistics.mean(tick_times_sorted) if tick_times_sorted else 0
        p95_ms = tick_times_sorted[int(n * 0.95)] if n > 0 else 0
        spike_threshold_ms = mean_ms * 5
        spikes = sum(1 for t in tick_times_sorted[-100:] if t > spike_threshold_ms)
        spike_rate = spikes / min(100, n)
        noise_rate = self._zero_result_retrieves / self._retrieve_count if self._retrieve_count > 0 else 0

        decay_buf_len = len(getattr(self.mem, '_decay_buffer_memories', []))

        snap = LifecycleSnapshot(
            tick=self._tick,
            working_count=len(self.mem.working),
            episodic_count=len(self.mem.episodic),
            semantic_count=len(self.mem.semantic),
            archive_count=len(self.mem.archive),
            decay_buffer_count=decay_buf_len,
            total_memories=len(self.mem.working) + len(self.mem.episodic) + len(self.mem.semantic) + len(self.mem.archive) + decay_buf_len,
            mean_tick_ms=round(mean_ms, 4),
            p95_tick_ms=round(p95_ms, 4),
            spike_rate=round(spike_rate, 4),
            noise_rate=round(noise_rate, 4)
        )
        self._emit_snapshot(snap)
        return snap

    # ── Run scenarios ──────────────────────────────────────────────────────

    def run_scenario(self, ticks: int, retrieve_ratio: float = 0.5,
                     goals: list = None, scenario_name: str = ''):
        """
        Run a tracer scenario: interleaved retrieve/store with observability.
        """
        if goals is None:
            goals = [
                {'goal': '完成项目文档', 'importance': 0.8},
                {'goal': '修复系统Bug', 'importance': 0.9},
                {'goal': '优化性能', 'importance': 0.7},
            ]

        print(f"[MemoryTracer] Starting scenario: {scenario_name} ({ticks} ticks, {retrieve_ratio*100:.0f}% retrieve)")

        for t in range(1, ticks + 1):
            self._tick = t
            current_goal = goals[t % len(goals)]

            if random.random() < retrieve_ratio:
                # Retrieval
                query = f'query_{t % 20}'
                self._hook_retrieve(query=query, current_goal=current_goal['goal'],
                                   current_tick=t, max_results=5, goal_history=[])
            else:
                # Store
                content = f'memory_content_{t}'
                importance = round(random.uniform(0.5, 0.9), 2)
                tags = [f'tag_{t % 5}']
                self._hook_store(content, 'general', importance, tags, t)

            # Periodic snapshot
            if t % self._snapshot_interval == 0:
                snap = self._take_snapshot()
                print(f"  [tick {t:5d}] w={snap.working_count} e={snap.episodic_count} "
                      f"s={snap.semantic_count} a={snap.archive_count} | "
                      f"mean={snap.mean_tick_ms:.3f}ms p95={snap.p95_tick_ms:.3f}ms "
                      f"spike={snap.spike_rate:.3f}")

        # Final snapshot only if last tick wasn't already snapshotted
        if (ticks - 1) % self._snapshot_interval != 0:
            snap = self._take_snapshot()
        self._close()

        # Print summary
        self._print_summary(scenario_name, ticks)
        return self._build_summary()

    def run_agent_simulation(self, ticks: int):
        """
        Simulate an agent loop with planning, tool use, and memory.
        More realistic than pure retrieve/store.
        """
        print(f"[MemoryTracer] Agent simulation ({ticks} ticks)")

        # Agent state
        current_plan = [
            {'goal': '设计系统架构', 'status': 'active', 'importance': 0.9},
            {'goal': '编写核心模块', 'status': 'pending', 'importance': 0.8},
            {'goal': '测试验证', 'status': 'pending', 'importance': 0.7},
        ]
        completed_goals = []

        for t in range(1, ticks + 1):
            self._tick = t

            # Agent decides what to do each tick
            action = random.choices(
                ['think', 'plan', 'act', 'reflect', 'retrieve'],
                weights=[0.3, 0.2, 0.3, 0.1, 0.1]
            )[0]

            current_goal = current_plan[t % len(current_plan)]

            if action == 'think':
                # Internal reasoning: store a thought
                thought = f'thought_{t}: 分析当前任务进度'
                self._hook_store(thought, 'thought', 0.6, ['reasoning'], t)

            elif action == 'plan':
                # Planning: store a plan item
                plan_item = f'plan_{t}: {current_goal["goal"]} 的子步骤'
                self._hook_store(plan_item, 'plan', current_goal['importance'], ['planning'], t)

            elif action == 'act':
                # Acting: store an observation
                obs = f'action_result_{t}: 完成了 {current_goal["goal"]} 的部分工作'
                self._hook_store(obs, 'observation', 0.7, ['action'], t)

            elif action == 'reflect':
                # Reflection: retrieve and consolidate
                results = self._hook_retrieve(
                    query=f'reflect_{current_goal["goal"]}',
                    current_goal=current_goal['goal'],
                    current_tick=t, max_results=5, goal_history=[]
                )
                if results:
                    reflection = f'reflection_{t}: 基于 {len(results)} 条记忆反思 {current_goal["goal"]}'
                    self._hook_store(reflection, 'reflection', 0.8, ['meta'], t)

            else:  # retrieve
                self._hook_retrieve(
                    query=current_goal['goal'],
                    current_goal=current_goal['goal'],
                    current_tick=t, max_results=5, goal_history=[]
                )

            # Snapshot
            if t % self._snapshot_interval == 0:
                snap = self._take_snapshot()
                print(f"  [tick {t:5d}] w={snap.working_count} e={snap.episodic_count} "
                      f"s={snap.semantic_count} a={snap.archive_count} | "
                      f"mean={snap.mean_tick_ms:.3f}ms p95={snap.p95_tick_ms:.3f}ms")

        snap = self._take_snapshot()
        self._close()
        self._print_summary('agent_simulation', ticks)
        return self._build_summary()

    def _print_summary(self, scenario_name: str, ticks: int):
        """Print trace summary."""
        tick_times_sorted = sorted(self._tick_times)
        n = len(tick_times_sorted)
        mean_ms = statistics.mean(tick_times_sorted) if tick_times_sorted else 0
        p50 = tick_times_sorted[n // 2] if n > 0 else 0
        p95 = tick_times_sorted[int(n * 0.95)] if n > 0 else 0
        p99 = tick_times_sorted[int(n * 0.99)] if n > 0 else 0
        max_ms = max(tick_times_sorted) if tick_times_sorted else 0
        spike_threshold = mean_ms * 5
        spikes = sum(1 for t in tick_times_sorted if t > spike_threshold)
        spike_rate = spikes / n if n > 0 else 0
        noise_rate = self._zero_result_retrieves / self._retrieve_count if self._retrieve_count > 0 else 0

        print(f"\n{'='*60}")
        print(f"  Trace Summary: {scenario_name}")
        print(f"{'='*60}")
        print(f"  Total ticks: {ticks}")
        print(f"  Operations: {self._retrieve_count} retrieve + {self._store_count} store")
        print(f"  Latency: mean={mean_ms:.4f}ms p50={p50:.4f}ms p95={p95:.4f}ms p99={p99:.4f}ms max={max_ms:.4f}ms")
        print(f"  Stability: spike_rate={spike_rate:.4f} noise_rate={noise_rate:.4f}")
        print(f"  Trace file: {self.trace_path}")
        print(f"  Snapshots:  {self.snapshot_path}")
        print(f"{'='*60}")

    def _build_summary(self) -> dict:
        """Build summary dict for programmatic use."""
        tick_times_sorted = sorted(self._tick_times)
        n = len(tick_times_sorted)
        mean_ms = statistics.mean(tick_times_sorted) if tick_times_sorted else 0
        return {
            'trace_name': self.trace_name,
            'trace_path': str(self.trace_path),
            'snapshot_path': str(self.snapshot_path),
            'total_ticks': self._tick,
            'retrieve_count': self._retrieve_count,
            'store_count': self._store_count,
            'mean_ms': round(mean_ms, 4),
            'p95_ms': round(tick_times_sorted[int(n * 0.95)], 4) if n > 0 else 0,
            'spike_rate': round(sum(1 for t in tick_times_sorted if t > mean_ms * 5) / n, 4) if n > 0 else 0,
            'noise_rate': round(self._zero_result_retrieves / self._retrieve_count, 4) if self._retrieve_count > 0 else 0,
        }

    def _close(self):
        """Close trace files."""
        self._trace_file.flush()
        self._snap_file.flush()

    def close(self):
        """Public close."""
        self._close()


# ─── Trace Analyzer ──────────────────────────────────────────────────────────

class TraceAnalyzer:
    """
    Analyzes trace files and produces human-readable observability reports.
    """

    def __init__(self, trace_path: str, snapshot_path: str):
        self.trace_path = trace_path
        self.snapshot_path = snapshot_path
        self.events = []
        self.snapshots = []

    def load(self):
        """Load trace files."""
        with open(self.trace_path) as f:
            for line in f:
                if line.strip():
                    self.events.append(json.loads(line))
        with open(self.snapshot_path) as f:
            for line in f:
                if line.strip():
                    self.snapshots.append(json.loads(line))

        # Load transitions.jsonl for complete lifecycle graph
        # First line may be a header with base_path
        base_path = None
        if self.events and self.events[0].get('type') == 'header':
            base_path = self.events[0].get('data', {}).get('base_path')

        if not base_path:
            # Try to find transitions.jsonl in common locations
            possible = [
                os.path.join(os.path.dirname(self.trace_path), 'transitions.jsonl'),
                os.path.join(os.path.dirname(self.snapshot_path), 'transitions.jsonl'),
            ]
            for p in possible:
                if os.path.exists(p):
                    base_path = os.path.dirname(p)
                    break

        if base_path:
            trans_path = os.path.join(base_path, 'transitions.jsonl')
            if os.path.exists(trans_path):
                count = 0
                with open(trans_path) as f:
                    for line in f:
                        if line.strip():
                            try:
                                ev = json.loads(line)
                                self.events.append({'type': 'log_transition', 'ts': 0, 'data': ev})
                                count += 1
                            except json.JSONDecodeError:
                                continue
                print(f"Loaded {count} transitions from transitions.jsonl")

        print(f"Loaded {len(self.events)} events, {len(self.snapshots)} snapshots")

    def report_lifecycle_graph(self):
        """Print memory lifecycle flow graph."""
        # Group events by memory_id
        by_memory = defaultdict(list)
        for ev in self.events:
            if ev['type'] == 'state_transition':
                by_memory[ev['data']['memory_id']].append(ev['data'])
            elif ev['type'] == 'log_transition':
                # transitions.jsonl entry: memory_id, from, to, reason, tick
                d = ev['data']
                by_memory[d.get('memory_id', '')].append({
                    'from_state': d.get('from', ''),
                    'to_state': d.get('to', ''),
                    'reason': d.get('reason', ''),
                    'tick': d.get('tick', 0),
                    'memory_content': ''
                })

        print(f"\n{'='*60}")
        print("  Memory Lifecycle Flow Graph")
        print(f"{'='*60}")

        # Count transitions per type
        transition_counts = defaultdict(int)
        for mem_id, transitions in by_memory.items():
            for tr in transitions:
                key = f"{tr['from_state']}→{tr['to_state']}"
                transition_counts[key] += 1

        print("\n  Transition counts:")
        for k, v in sorted(transition_counts.items(), key=lambda x: -x[1]):
            print(f"    {k or '(init)':>20}: {v:>6}")

        # Show sample lifecycles
        print("\n  Sample memory lifecycles (first 5):")
        for mem_id, transitions in list(by_memory.items())[:5]:
            path = ' → '.join([(t['to_state'] or 'new') for t in transitions])
            content = transitions[0]['memory_content'][:50] if transitions else ''
            print(f"    [{mem_id[:8]}] {content}: {path}")

    def report_retrieval_analysis(self):
        """Analyze retrieval patterns."""
        retrievals = [e['data'] for e in self.events if e['type'] == 'retrieval_trace']

        print(f"\n{'='*60}")
        print("  Retrieval Trace Analysis")
        print(f"{'='*60}")
        print(f"  Total retrievals: {len(retrievals)}")

        if not retrievals:
            return

        # Semantic activation rate
        semantic_fired = sum(1 for r in retrievals if r.get('semantic_fired'))
        rerank_modified = sum(1 for r in retrievals if r.get('rerank_modified_count', 0) > 0)
        spikes = sum(1 for r in retrievals if r.get('spike'))
        zero_results = sum(1 for r in retrievals if r['results_count'] == 0)

        print(f"  Semantic activations: {semantic_fired}/{len(retrievals)} ({100*semantic_fired/len(retrievals):.1f}%)")
        print(f"  Rerank modifications: {rerank_modified}/{len(retrievals)} ({100*rerank_modified/len(retrievals):.1f}%)")
        print(f"  Spikes: {spikes} ({100*spikes/len(retrievals):.1f}%)")
        print(f"  Zero-result retrievals: {zero_results} ({100*zero_results/len(retrievals):.1f}%)")

        # Latency distribution
        latencies = [r['latency_ms'] for r in retrievals]
        print(f"\n  Latency (ms):")
        print(f"    mean={statistics.mean(latencies):.4f} median={statistics.median(latencies):.4f}")
        print(f"    p95={sorted(latencies)[int(len(latencies)*0.95)]:.4f} max={max(latencies):.4f}")

        # Show rerank decisions
        all_reranks = []
        for r in retrievals:
            all_reranks.extend(r.get('rerank_decisions', []))
        if all_reranks:
            print(f"\n  Rerank decision types:")
            action_counts = defaultdict(int)
            for rd in all_reranks:
                action_counts[rd.get('action', 'unknown')] += 1
            for k, v in sorted(action_counts.items(), key=lambda x: -x[1])[:5]:
                print(f"    {k}: {v}")

        # Show sample retrievals
        print(f"\n  Sample retrievals (first 5):")
        for r in retrievals[:5]:
            print(f"    tick={r['tick']} query='{r['query'][:30]}' "
                  f"results={r['results_count']} semantic={r['semantic_fired']} "
                  f"latency={r['latency_ms']:.3f}ms")

    def report_semantic_timeline(self):
        """Show semantic activation timeline."""
        activations = [e['data'] for e in self.events if e['type'] == 'retrieval_trace' and e['data'].get('semantic_fired')]

        print(f"\n{'='*60}")
        print("  Semantic Activation Timeline")
        print(f"{'='*60}")
        print(f"  Total semantic activations: {len(activations)}")

        if not activations:
            print("  (no semantic activations)")
            return

        # Count by effect type
        effects = defaultdict(int)
        for a in activations:
            effects[a.get('net_effect', 'unknown')] += 1
        print("\n  Net effects:")
        for k, v in sorted(effects.items(), key=lambda x: -x[1]):
            print(f"    {k}: {v}")

        # Show timeline
        print(f"\n  Timeline (first 10 activations):")
        for a in activations[:10]:
            print(f"    tick={a['tick']:5d} scored={a['semantic_scored_count']:2d} "
                  f"modified={a['rerank_modified_count']} net={a.get('net_effect','?')}")

    def report_anomalies(self):
        """Show all anomalies."""
        anomalies = [e['data'] for e in self.events if e['type'] == 'anomaly']

        print(f"\n{'='*60}")
        print("  Anomaly Report")
        print(f"{'='*60}")
        print(f"  Total anomalies: {len(anomalies)}")

        by_type = defaultdict(int)
        for a in anomalies:
            by_type[a['anomaly_type']] += 1

        for k, v in sorted(by_type.items(), key=lambda x: -x[1]):
            print(f"    {k}: {v}")

        if anomalies:
            print(f"\n  Recent anomalies (last 5):")
            for a in anomalies[-5:]:
                print(f"    tick={a['tick']} {a['anomaly_type']}: {str(a['details'])[:80]}")

    def report_lifecycle_snapshots(self):
        """Show lifecycle metrics over time."""
        if not self.snapshots:
            print("\nNo snapshots available")
            return

        print(f"\n{'='*60}")
        print("  Memory Lifecycle Snapshots")
        print(f"{'='*60}")
        print(f"{'Tick':>6} {'Work':>5} {'Epis':>5} {'Sem':>5} {'Arch':>5} {'DBuf':>5} {'Total':>6} {'Mean':>8} {'P95':>8} {'Spike':>7}")
        print("-" * 70)

        for snap in self.snapshots:
            print(f"{snap['tick']:>6} {snap['working_count']:>5} {snap['episodic_count']:>5} "
                  f"{snap['semantic_count']:>5} {snap['archive_count']:>5} "
                  f"{snap['decay_buffer_count']:>5} {snap['total_memories']:>6} "
                  f"{snap['mean_tick_ms']:>8.4f} {snap['p95_tick_ms']:>8.4f} {snap['spike_rate']:>7.4f}")

        # Growth chart
        print(f"\n  Layer sizes over time:")
        ticks = [s['tick'] for s in self.snapshots]
        for layer in ['working_count', 'episodic_count', 'semantic_count', 'archive_count']:
            vals = [s[layer] for s in self.snapshots]
            first, last = vals[0], vals[-1]
            print(f"    {layer:>20}: {first} → {last} (Δ={last-first:+d})")

    def full_report(self):
        """Generate complete observability report."""
        print(f"\n{'#'*60}")
        print(f"#  OBSERVABILITY REPORT")
        print(f"#  Trace: {self.trace_path}")
        print(f"{'#'*60}")

        self.report_lifecycle_snapshots()
        self.report_lifecycle_graph()
        self.report_retrieval_analysis()
        self.report_semantic_timeline()
        self.report_anomalies()

        print(f"\n{'#'*60}")
        print(f"#  END OF REPORT")
        print(f"{'#'*60}")


# ─── CLI Entry Points ────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Memory Trace Observer v0.9')
    parser.add_argument('command', choices=['run', 'analyze', 'demo'],
                       help='run: execute tracer scenario, analyze: parse trace file, demo: run all scenarios')
    parser.add_argument('--scenario', default='standard', help='Scenario name')
    parser.add_argument('--ticks', type=int, default=1000, help='Number of ticks')
    parser.add_argument('--retrieve-ratio', type=float, default=0.5, help='Retrieve ratio 0-1')
    parser.add_argument('--agent-sim', action='store_true', help='Run agent simulation')
    parser.add_argument('--trace-name', help='Custom trace name')
    parser.add_argument('--trace-file', help='Trace file to analyze')
    parser.add_argument('--snapshot-file', help='Snapshot file to analyze')
    parser.add_argument('--base-path', default='/tmp/trace_mem', help='Memory base path')
    args = parser.parse_args()

    if args.command == 'run':
        import shutil
        if os.path.exists(args.base_path):
            shutil.rmtree(args.base_path)

        tracer = MemoryTracer(args.base_path, trace_name=args.trace_name)

        if args.agent_sim:
            tracer.run_agent_simulation(ticks=args.ticks)
        else:
            tracer.run_scenario(ticks=args.ticks, retrieve_ratio=args.retrieve_ratio,
                              scenario_name=args.scenario)

    elif args.command == 'analyze':
        if not args.trace_file:
            # Find latest trace
            traces = sorted(TRACE_DIR.glob('trace_*.jsonl'))
            if not traces:
                print("No trace files found")
                return
            args.trace_file = traces[-1]
            args.snapshot_file = str(traces[-1]).replace('.jsonl', '_snapshots.jsonl')

        analyzer = TraceAnalyzer(args.trace_file, args.snapshot_file)
        analyzer.load()
        analyzer.full_report()

    elif args.command == 'demo':
        import shutil
        if os.path.exists(args.base_path):
            shutil.rmtree(args.base_path)

        scenarios = [
            ('baseline_100', 100, 0.5),
            ('standard_1000', 1000, 0.5),
            ('retrieval_heavy_1000', 1000, 0.8),
            ('store_heavy_1000', 1000, 0.2),
            ('agent_simulation_1000', 1000, 0.5),
        ]

        for name, ticks, ratio in scenarios:
            is_agent = 'agent' in name
            import shutil as sh
            if os.path.exists(args.base_path):
                sh.rmtree(args.base_path)

            tracer = MemoryTracer(args.base_path, trace_name=name)
            if is_agent:
                tracer.run_agent_simulation(ticks=ticks)
            else:
                tracer.run_scenario(ticks=ticks, retrieve_ratio=ratio, scenario_name=name)

            # Analyze immediately
            analyzer = TraceAnalyzer(str(tracer.trace_path), str(tracer.snapshot_path))
            analyzer.load()
            analyzer.full_report()


if __name__ == '__main__':
    main()
