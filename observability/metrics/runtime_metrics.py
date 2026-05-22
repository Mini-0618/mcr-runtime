#!/usr/bin/env python3
"""
Runtime Metrics Collector v1.0
================================
Reads trace files from MemoryTracer and produces time-series metrics.

Usage:
  python runtime_metrics.py --trace /home/minimak/mcr/traces/trace_XXXX.jsonl
  python runtime_metrics.py --dir /home/minimak/mcr/traces/
"""

import json
import argparse
import statistics
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Optional

# ─── Metrics Dataclasses ──────────────────────────────────────────────────────

@dataclass
class RuntimeMetrics:
    """All time-series metrics for a run."""
    tick: int

    # Bridge counts (from layered_memory)
    active_count: int = 0
    dormant_count: int = 0
    archived_count: int = 0
    collapsed_count: int = 0
    reconstruct_count: int = 0

    # Retrieval latency
    retrieval_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0

    # Retrieval quality
    retrieval_noise_ratio: float = 0.0
    zero_result_rate: float = 0.0

    # Semantic layer
    semantic_override_count: int = 0
    semantic_replace_count: int = 0
    semantic_dedup_count: int = 0
    semantic_activation_count: int = 0
    semantic_suppression_count: int = 0

    # Lifecycle events
    gc_events: int = 0
    promotion_count: int = 0
    demotion_count: int = 0
    decay_count: int = 0
    starvation_events: int = 0

    # Memory growth
    memory_growth_rate: float = 0.0  # per tick
    working_count: int = 0
    episodic_count: int = 0

    # Activation entropy
    activation_entropy: float = 0.0  # distribution of access across memories


class MetricsCollector:
    """Collects and computes time-series metrics from trace files."""

    def __init__(self, trace_path: str):
        self.trace_path = Path(trace_path)
        self.events = []
        self.metrics_history = []
        self._load_events()

    def _load_events(self):
        """Load all events from trace file."""
        if not self.trace_path.exists():
            print(f"[WARN] Trace file not found: {self.trace_path}")
            return

        with open(self.trace_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    self.events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        print(f"[INFO] Loaded {len(self.events)} events from {self.trace_path.name}")

    def compute_metrics(self, tick: int) -> RuntimeMetrics:
        """Compute metrics for a specific tick."""
        m = RuntimeMetrics(tick=tick)

        # All latencies
        latencies = [e['data']['latency_ms'] for e in self.events
                     if e['type'] == 'retrieval_trace' and e['data']['tick'] == tick]
        if latencies:
            m.retrieval_latency_ms = latencies[0]
            sorted_lat = sorted(latencies)
            n = len(sorted_lat)
            m.p50_latency_ms = sorted_lat[n // 2]
            m.p95_latency_ms = sorted_lat[int(n * 0.95)] if n >= 20 else sorted_lat[-1]
            m.p99_latency_ms = sorted_lat[int(n * 0.99)] if n >= 100 else sorted_lat[-1]

        # All retrieval counts
        all_retrievals = [e['data'] for e in self.events if e['type'] == 'retrieval_trace']
        m.zero_result_rate = sum(1 for r in all_retrievals if r['results_count'] == 0) / max(len(all_retrievals), 1)

        # Lifecycle snapshot
        snapshots = [e['data'] for e in self.events if e['type'] == 'lifecycle_snapshot' and e['data']['tick'] == tick]
        if snapshots:
            s = snapshots[0]
            m.working_count = s.get('working_count', 0)
            m.episodic_count = s.get('episodic_count', 0)
            m.active_count = s.get('semantic_count', 0)  # semantic_count = active bridges

        # Bridge state counts (from bridge lifecycle events)
        bridge_events = [e['data'] for e in self.events if e['type'] in ('bridge_state_change', 'bridge_gc')]
        for be in bridge_events:
            if be.get('tick', 0) == tick:
                if be.get('to_state') == 'active':
                    m.active_count += 1
                elif be.get('to_state') == 'dormant':
                    m.dormant_count += 1
                elif be.get('to_state') == 'archived':
                    m.archived_count += 1
                elif be.get('to_state') == 'collapsed':
                    m.collapsed_count += 1
                elif be.get('action') == 'reconstruct':
                    m.reconstruct_count += 1

        # Semantic activations
        sem_events = [e['data'] for e in self.events if e['type'] == 'semantic_activation']
        for se in sem_events:
            if se.get('tick', 0) == tick:
                m.semantic_activation_count += 1
                m.semantic_dedup_count += se.get('dedup压制_count', 0)
                m.semantic_replace_count += se.get('low_value_replace_count', 0)
                m.semantic_override_count += se.get('long_term_override_count', 0)

        # Promotion / Demotion
        transitions = [e['data'] for e in self.events if e['type'] == 'promotion_event']
        for t in transitions:
            if t.get('tick', 0) == tick:
                m.promotion_count += 1

        # Anomalies
        anomalies = [e['data'] for e in self.events if e['type'] == 'anomaly']
        for a in anomalies:
            if a.get('tick', 0) == tick:
                if a.get('anomaly_type') == 'spike':
                    pass  # captured in latency
                elif a.get('anomaly_type') == 'starvation':
                    m.starvation_events += 1

        return m

    def compute_all_metrics(self) -> list:
        """Compute metrics for all ticks."""
        ticks = sorted(set(e['data'].get('tick', 0) for e in self.events if 'data' in e and 'tick' in e['data']))
        print(f"[INFO] Computing metrics for {len(ticks)} ticks")
        return [self.compute_metrics(t) for t in ticks]

    def export_timeseries(self, output_path: str = None):
        """Export metrics as JSON time-series."""
        metrics = self.compute_all_metrics()
        if not metrics:
            print("[WARN] No metrics to export")
            return

        output = [asdict(m) for m in metrics]

        if output_path:
            out_file = Path(output_path)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            with open(out_file, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            print(f"[INFO] Exported to {out_file}")
        else:
            print(json.dumps(output, indent=2, ensure_ascii=False))

        return metrics

    def summary_stats(self) -> dict:
        """Compute summary statistics across all ticks."""
        metrics = self.compute_all_metrics()
        if not metrics:
            return {}

        latencies = [m.retrieval_latency_ms for m in metrics if m.retrieval_latency_ms > 0]
        active_counts = [m.active_count for m in metrics]
        semantic_counts = [m.semantic_activation_count for m in metrics]
        collapsed = [m.collapsed_count for m in metrics]
        reconstructs = [m.reconstruct_count for m in metrics]
        starvation = [m.starvation_events for m in metrics]

        return {
            'total_ticks': len(metrics),
            'latency': {
                'mean_ms': round(statistics.mean(latencies), 4) if latencies else 0,
                'p50_ms': round(statistics.median(latencies), 4) if latencies else 0,
                'p95_ms': round(statistics.quantiles(latencies, n=20)[18], 4) if len(latencies) >= 20 else max(latencies, default=0),
                'p99_ms': round(statistics.quantiles(latencies, n=100)[98], 4) if len(latencies) >= 100 else max(latencies, default=0),
                'max_ms': round(max(latencies), 4) if latencies else 0,
            },
            'active_bridges': {
                'mean': round(statistics.mean(active_counts), 2) if active_counts else 0,
                'max': max(active_counts, default=0),
                'min': min(active_counts, default=0),
            },
            'semantic_activations': {
                'total': sum(semantic_counts),
                'per_tick_avg': round(statistics.mean(semantic_counts), 2) if semantic_counts else 0,
            },
            'collapses': {
                'total': sum(collapsed),
                'per_tick_avg': round(statistics.mean(collapsed), 2) if collapsed else 0,
            },
            'reconstructs': {
                'total': sum(reconstructs),
            },
            'starvation_events': {
                'total': sum(starvation),
            },
            'zero_result_rate': round(sum(1 for m in metrics if m.zero_result_rate > 0) / len(metrics), 4),
        }


def main():
    parser = argparse.ArgumentParser(description='MCR Runtime Metrics Collector')
    parser.add_argument('--trace', type=str, help='Path to trace JSONL file')
    parser.add_argument('--dir', type=str, help='Directory containing trace files')
    parser.add_argument('--output', type=str, help='Output JSON path')
    parser.add_argument('--summary', action='store_true', help='Print summary stats')
    args = parser.parse_args()

    if args.trace:
        collector = MetricsCollector(args.trace)
        if args.summary:
            stats = collector.summary_stats()
            print("\n=== SUMMARY STATS ===")
            print(json.dumps(stats, indent=2, ensure_ascii=False))
        else:
            collector.export_timeseries(args.output)
    elif args.dir:
        trace_dir = Path(args.dir)
        for trace_file in sorted(trace_dir.glob('*.jsonl')):
            print(f"\n--- {trace_file.name} ---")
            collector = MetricsCollector(str(trace_file))
            if args.summary:
                stats = collector.summary_stats()
                print(json.dumps(stats, indent=2, ensure_ascii=False))
            else:
                collector.export_timeseries(str(trace_file.with_suffix('.metrics.json')))
    else:
        print("[ERROR] Must provide --trace or --dir")


if __name__ == '__main__':
    main()
