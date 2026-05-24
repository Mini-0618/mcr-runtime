#!/usr/bin/env python3
"""
Metadata Compaction Physics Simulation v1.1 (Fast)
=================================================
Uses numpy-free vectorized math for speed.
Tests 5 strategies at 10k ticks each (fast sanity run).
"""

import json
import math
import random
from dataclasses import dataclass
from typing import List, Tuple

COMPACTION_STRATEGIES = {
    "NONE":        {"enabled": False, "interval": None,      "level_factor": None, "tombstone_gc": False},
    "PERIODIC_10K": {"enabled": True,  "interval": 10_000,  "level_factor": None, "tombstone_gc": False},
    "PERIODIC_5K":  {"enabled": True,  "interval": 5_000,   "level_factor": None, "tombstone_gc": False},
    "LEVELED_L2":   {"enabled": True,  "interval": 5_000,   "level_factor": 2.0,  "tombstone_gc": True},
    "TIERED_L3":    {"enabled": True,  "interval": 2_000,   "level_factor": 3.0,  "tombstone_gc": True},
}

@dataclass
class SimState:
    entries: int = 0
    bytes_: float = 0.0
    tombstones: int = 0
    compactions: int = 0
    cpu_cost: float = 0.0
    bytes_compacted: float = 0.0

def metadata_per_tick() -> float:
    return random.gauss(4.5, 0.5)  # T1-T6 combined

def run_sim(name: str, strat: dict, max_tick: int) -> Tuple[SimState, List[Tuple[int, int]], List[Tuple[int, float]]]:
    state = SimState()
    entry_curve: List[Tuple[int, int]] = []
    byte_curve: List[Tuple[int, float]] = []

    # For compaction efficiency: track entries as simple counters, not objects
    total_ever_created = 0
    total_ever_tombstoned = 0
    live_bytes = 0.0

    for tick in range(1, max_tick + 1):
        # Generate new entries
        n_new = max(0, int(round(metadata_per_tick())))
        total_ever_created += n_new
        new_bytes = n_new * random.uniform(70, 120)
        live_bytes += new_bytes

        # Tombstone ~3% per tick
        n_tomb = int(live_bytes / 500 * 0.03) if live_bytes > 0 else 0
        n_tomb = min(n_tomb, int(state.entries * 0.1))
        total_ever_tombstoned += n_tomb
        state.tombstones += n_tomb

        state.entries = total_ever_created - total_ever_tombstoned
        state.bytes_ = live_bytes

        # Compaction
        if strat["enabled"] and tick % strat["interval"] == 0:
            state.compactions += 1

            if strat["level_factor"] is None:
                # Simple periodic: discard tombstones + old entries
                discarded = int(state.entries * 0.2)
            else:
                lf = strat["level_factor"]
                # Leveled: each level 10x the previous in capacity
                # Compaction discards tombstones + dead entries
                gc_ratio = 0.15 if strat["tombstone_gc"] else 0.05
                discarded = int(state.entries * gc_ratio)

            state.entries = max(0, state.entries - discarded)
            live_bytes = max(0, live_bytes - discarded * 80)
            state.bytes_compacted += discarded * 80
            state.bytes_ = live_bytes
            if strat["level_factor"] is not None:
                state.cpu_cost += state.entries * math.log(max(2, strat["level_factor"])) * 0.05

        # Record every 100 ticks
        if tick % 100 == 0:
            entry_curve.append((tick, state.entries))
            byte_curve.append((tick, state.bytes_))

        if tick % 2000 == 0:
            print(f"  [{name}] tick={tick:,} entries={state.entries:,} bytes={state.bytes_:,.0f}")

    return state, entry_curve, byte_curve

def asymptotic_alpha(curve: List[Tuple[int, float]]) -> float:
    if len(curve) < 20:
        return float('nan')
    xs = [math.log(max(1, t)) for (t, b) in curve if t > 0 and b > 0]
    ys = [math.log(max(1, b)) for (t, b) in curve if t > 0 and b > 0]
    if len(xs) < 10:
        return float('nan')
    n = len(xs)
    sum_x = sum(xs); sum_y = sum(ys); sum_xy = sum(x*y for x,y in zip(xs,ys)); sum_x2 = sum(x*x for x in xs)
    denom = n*sum_x2 - sum_x**2
    if abs(denom) < 1e-10:
        return float('nan')
    return (n*sum_xy - sum_x*sum_y) / denom

MAX_TICK = 10_000
results = {}

print("=" * 60)
print("COMPACTION PHYSICS SIMULATION (10k ticks x 5 strategies)")
print("=" * 60)

for strat_name, strat in COMPACTION_STRATEGIES.items():
    print(f"\n[strat: {strat_name}]")
    state, entries_curve, bytes_curve = run_sim(strat_name, strat, MAX_TICK)
    alpha = asymptotic_alpha(bytes_curve)
    results[strat_name] = {
        "entries": state.entries,
        "bytes": state.bytes_,
        "compactions": state.compactions,
        "cpu_cost": state.cpu_cost,
        "bytes_compacted": state.bytes_compacted,
        "alpha": alpha,
    }
    print(f"  => entries={state.entries:,} bytes={state.bytes_:,.0f} alpha={alpha:.4f} compactions={state.compactions}")

print("\n" + "=" * 60)
print("SUMMARY TABLE")
print("=" * 60)
print(f"{'Strategy':<16} {'Entries':>9} {'Bytes':>12} {'Alpha':>8} {'Compactions':>12} {'CPU Cost':>10}")
print("-" * 60)
for name, r in results.items():
    alpha_str = f"{r['alpha']:.4f}" if not math.isnan(r['alpha']) else "N/A"
    print(f"{name:<16} {r['entries']:>9,} {r['bytes']:>12,.0f} {alpha_str:>8} {r['compactions']:>12} {r['cpu_cost']:>10,.0f}")

# Key findings
none = results["NONE"]
print(f"\nKEY FINDINGS:")
print(f"  NONE strategy: alpha={none['alpha']:.4f} (1.0 = linear, >1.0 = superlinear)")
for name, r in results.items():
    if name == "NONE":
        continue
    alpha_diff = r['alpha'] - none['alpha']
    compaction_benefit = (none['bytes'] - r['bytes']) / none['bytes'] * 100 if none['bytes'] > 0 else 0
    print(f"  {name}: alpha_diff={alpha_diff:+.4f} bytes_reduced={compaction_benefit:.1f}% cpu_cost={r['cpu_cost']:.0f}")

# Export
OUTPUT_DIR = "./runtime_phys_observation/phase_III_A_metadata"
data = {
    "max_tick": MAX_TICK,
    "strategies": results,
    "conclusion": (
        "superlinear" if none['alpha'] > 1.05
        else "linear" if none['alpha'] > 0.95
        else "sublinear"
    )
}
with open(f"{OUTPUT_DIR}/compaction_metrics.json", 'w') as f:
    json.dump(data, f, indent=2)
print(f"\n[SAVED] {OUTPUT_DIR}/compaction_metrics.json")
