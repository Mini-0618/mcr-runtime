#!/usr/bin/env python3
"""
Snapshot Compare Tool v1.0
===========================
Compares two runtime snapshots and outputs a diff report.

Usage:
  python snapshot_compare.py --a snapshot_a.json --b snapshot_b.json
  python snapshot_compare.py --dir ./snapshots/
"""

import json
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import statistics

@dataclass
class SnapshotDiff:
    """Difference between two snapshots."""
    tick_a: int
    tick_b: int
    latency_diff_ms: float
    active_diff: int
    dormant_diff: int
    archived_diff: int
    collapsed_diff: int
    semantic_diff: int
    promotion_diff: int
    starvation_diff: int
    memory_growth_diff: float


def load_snapshot(path: str) -> dict:
    """Load a snapshot JSON file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Snapshot not found: {path}")

    with open(p, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Handle single snapshot vs list
    if isinstance(data, list):
        if not data:
            raise ValueError(f"Empty snapshot list: {path}")
        return data[-1]  # latest tick
    return data


def compare_snapshots(a: dict, b: dict) -> SnapshotDiff:
    """Compare two snapshots."""
    return SnapshotDiff(
        tick_a=a.get('tick', 0),
        tick_b=b.get('tick', 0),
        latency_diff_ms=b.get('retrieval_latency_ms', 0) - a.get('retrieval_latency_ms', 0),
        active_diff=b.get('active_count', 0) - a.get('active_count', 0),
        dormant_diff=b.get('dormant_count', 0) - a.get('dormant_count', 0),
        archived_diff=b.get('archived_count', 0) - a.get('archived_count', 0),
        collapsed_diff=b.get('collapsed_count', 0) - b.get('collapsed_count', 0),
        semantic_diff=b.get('semantic_activation_count', 0) - a.get('semantic_activation_count', 0),
        promotion_diff=b.get('promotion_count', 0) - a.get('promotion_count', 0),
        starvation_diff=b.get('starvation_events', 0) - a.get('starvation_events', 0),
        memory_growth_diff=b.get('memory_growth_rate', 0) - a.get('memory_growth_rate', 0),
    )


def generate_diff_report(diff: SnapshotDiff, a: dict, b: dict, output_path: str = None):
    """Generate a human-readable diff report."""
    lines = []
    lines.append("# Snapshot Diff Report")
    lines.append("")
    lines.append(f"**Snapshot A**: tick {diff.tick_a}")
    lines.append(f"**Snapshot B**: tick {diff.tick_b}")
    lines.append(f"**Tick Delta**: {diff.tick_b - diff.tick_a}")
    lines.append("")

    # Latency
    lines.append("## Retrieval Latency")
    latency_a = a.get('retrieval_latency_ms', 0)
    latency_b = b.get('retrieval_latency_ms', 0)
    diff_val = diff.latency_diff_ms
    sign = "+" if diff_val > 0 else ""
    status = "⚠️ SPIKE" if abs(diff_val) > latency_a * 2 else "✅ OK"
    lines.append(f"- A: {latency_a:.4f}ms")
    lines.append(f"- B: {latency_b:.4f}ms")
    lines.append(f"- Diff: {sign}{diff_val:.4f}ms {status}")
    lines.append("")

    # Bridge counts
    lines.append("## Bridge Counts")
    lines.append(f"| Layer | A | B | Diff |")
    lines.append(f"|-------|---|---|------|")
    lines.append(f"| active | {a.get('active_count', 0)} | {b.get('active_count', 0)} | {diff.active_diff:+d} |")
    lines.append(f"| dormant | {a.get('dormant_count', 0)} | {b.get('dormant_count', 0)} | {diff.dormant_diff:+d} |")
    lines.append(f"| archived | {a.get('archived_count', 0)} | {b.get('archived_count', 0)} | {diff.archived_diff:+d} |")
    lines.append(f"| collapsed | {a.get('collapsed_count', 0)} | {b.get('collapsed_count', 0)} | {diff.collapsed_diff:+d} |")
    lines.append("")

    # Lifecycle events
    lines.append("## Lifecycle Events")
    lines.append(f"| Event | A | B | Diff |")
    lines.append(f"|-------|---|---|------|")
    lines.append(f"| semantic_activation | {a.get('semantic_activation_count', 0)} | {b.get('semantic_activation_count', 0)} | {diff.semantic_diff:+d} |")
    lines.append(f"| promotion | {a.get('promotion_count', 0)} | {b.get('promotion_count', 0)} | {diff.promotion_diff:+d} |")
    lines.append(f"| starvation | {a.get('starvation_events', 0)} | {b.get('starvation_events', 0)} | {diff.starvation_diff:+d} |")
    lines.append("")

    # Memory growth
    lines.append("## Memory Growth")
    growth_a = a.get('memory_growth_rate', 0)
    growth_b = b.get('memory_growth_rate', 0)
    lines.append(f"- A: {growth_a:.4f}/tick")
    lines.append(f"- B: {growth_b:.4f}/tick")
    lines.append(f"- Diff: {diff.memory_growth_diff:+.4f}/tick")
    lines.append("")

    # Bounded property check
    lines.append("## Bounded Property Check")
    latency_ok = abs(diff.latency_diff_ms) < a.get('retrieval_latency_ms', 1) * 3
    active_bounded = b.get('active_count', 0) <= 150
    dormant_ok = b.get('dormant_count', 0) >= 0
    lines.append(f"- Latency bounded: {'✅' if latency_ok else '⚠️ CHECK'}")
    lines.append(f"- Active bridges <= 150: {'✅' if active_bounded else '⚠️ EXCEEDED'}")
    lines.append(f"- Dormant state active: {'✅' if dormant_ok else '⚠️ ISSUE'}")
    lines.append("")

    # Verdict
    lines.append("## Verdict")
    if abs(diff.latency_diff_ms) < latency_a * 2 and active_bounded:
        lines.append("✅ No significant drift detected.")
    else:
        lines.append("⚠️ Potential drift or anomaly detected. Review required.")

    report = "\n".join(lines)

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"[INFO] Report saved to {output_path}")

    return report


def main():
    parser = argparse.ArgumentParser(description='MCR Snapshot Compare Tool')
    parser.add_argument('--a', type=str, required=True, help='Snapshot A (JSON)')
    parser.add_argument('--b', type=str, required=True, help='Snapshot B (JSON)')
    parser.add_argument('--output', type=str, help='Output report path (Markdown)')
    args = parser.parse_args()

    print(f"[INFO] Loading snapshot A: {args.a}")
    snap_a = load_snapshot(args.a)
    print(f"[INFO] Loading snapshot B: {args.b}")
    snap_b = load_snapshot(args.b)

    print("[INFO] Computing diff...")
    diff = compare_snapshots(snap_a, snap_b)

    print("[INFO] Generating report...")
    report = generate_diff_report(diff, snap_a, snap_b, args.output)
    print(report)


if __name__ == '__main__':
    main()
