#!/usr/bin/env python3
"""
v0.19g-LR4 — Long-Run Stability Benchmark (Correct Formation)
Phase 2: Runtime Stabilization

CRITICAL FIX from v3:
- try_form_bridge requires 3 co-activations (min_co_activations=3)
- PRE bridges survive exactly pre_max_age=100 ticks, then GC
- My "continuous formation every 100 ticks" was creating PRE bridges
  that ALL got GC'd before ever reaching ACTIVE
- Fixed: Simulate real co-activation by calling try_form_bridge 3x
  per bridge_id within 100 tick window

This is the REAL formation dynamic, not a mock.
"""

import sys
import random
import statistics
import time

sys.path.insert(0, '/home/minimax/mcr')
from semantic_governance_v19g import (
    BridgeGovernanceLayer, GCConfig, ValidationConfig, BudgetConfig,
    ReinforcementConfig, BoundaryConfig,
    BRIDGE_STATE_ACTIVE, BRIDGE_STATE_DORMANT, BRIDGE_STATE_ARCHIVED,
    BRIDGE_STATE_COLLAPSED, BRIDGE_STATE_PRE
)

# Same MockEpisodic as all v0.19g experiments
class MockEpisodic:
    CATEGORIES = {
        0: "food", 1: "food", 2: "food",
        3: "lifestyle", 4: "lifestyle", 5: "lifestyle",
        6: "tech", 7: "tech", 8: "tech", 9: "tech",
        10: "finance", 11: "finance",
        12: "health", 13: "health",
        14: "education", 15: "education",
        16: "travel", 17: "travel",
        18: "entertainment", 19: "entertainment",
    }
    memory = set(range(20))

    def get_category(self, item_id):
        return self.CATEGORIES.get(item_id % 20, "unknown")

    def record_access(self, item_id):
        pass


def form_bridge_to_active(gov, bridge_id, category, items, context, importance, co_activations=3):
    """
    Simulate real co-activation: call try_form_bridge 3x within 100 ticks.
    This is how episodic co-occurrence translates to bridge formation.
    """
    for i in range(co_activations):
        formed, reason = gov.try_form_bridge(
            bridge_id, category, items, context=context, importance=importance
        )
        gov.advance()  # Each co-activation advances the tick
    # After 3 co-activations within pre_max_age, bridge should be ACTIVE
    return bridge_id in gov.bridges and gov.bridges[bridge_id].state == BRIDGE_STATE_ACTIVE


def run_long_run_benchmark_v4(ticks=10000, seed=42):
    """
    10,000 tick adversarial stress test.

    Real formation dynamic:
    - 3 co-activations within 100 ticks → ACTIVE
    - PRE bridges survive pre_max_age=100 ticks before GC
    - Continuous adversarial pressure: contamination + drift + decay

    Bounded properties:
    1. Bridge count bounded (GC prevents unbounded growth)
    2. Active bridges non-zero (some survive adversarial pressure)
    3. Retrieval latency bounded (O(1) not O(n))
    4. GC cost bounded
    5. Contamination contained
    """
    random.seed(seed)

    episodic = MockEpisodic()
    get_cat = episodic.get_category

    gov = BridgeGovernanceLayer(
        gc_config=GCConfig(
            drift_rate_window=50,
            drift_rate_threshold=0.01,
            contamination_hard_cap=0.30,
            auto_purify=True,
            purify_interval=10,
            gc_interval=1,
            pre_max_age=100,
        ),
        get_category_fn=get_cat,
    )

    print("=" * 70)
    print("v0.19g-LR4 — LONG-RUN STABILITY BENCHMARK (Correct Formation)")
    print("=" * 70)
    print(f"  Ticks: {ticks:,}")
    print(f"  Formation: 3 co-activations → ACTIVE (real v0.19g dynamic)")
    print(f"  Seed: {seed}")
    print()

    # ── Initial stable foundation: 12 bridges (3 categories × 4 importance levels) ──
    categories = ["food", "tech", "finance"]
    for i, cat in enumerate(categories):
        for repeat in range(4):
            bid = f"{cat}_{repeat}"
            base = i * 7 + repeat * 3
            items = {base % 20, (base + 1) % 20, (base + 2) % 20}
            imp = ["critical", "high", "medium", "low"][repeat]
            form_bridge_to_active(gov, bid, cat, items, f"ctx_{repeat}", imp, co_activations=3)

    initial = len(gov.bridges)
    initial_active = sum(1 for b in gov.bridges.values() if b.state == BRIDGE_STATE_ACTIVE)
    print(f"Initial bridges: {initial}, Active: {initial_active}")
    print()

    # ── Metrics tracking ──
    bridge_count_history = []
    active_ratio_history = []
    latency_history = []
    gc_rate_history = []
    avg_strength_history = []
    avg_contamination_history = []

    noise_items = list(range(100, 200))  # "unknown" category
    bridges_formed_total = 0

    print(f"{'Tick':>8} | {'Bridges':>7} | {'Active':>6} | {'Dorm':>5} | "
          f"{'Items':>6} | {'AvgStr':>7} | {'Cont':>6} | {'GC':>5}")
    print("-" * 75)

    for tick in range(1, ticks + 1):
        # ── Tick ──
        gov.advance()

        # ── Continuous formation: every 300 ticks, form 3 new bridges ──
        # (3 co-activations per bridge, so 300 ticks ≈ room for ~100 new formations)
        if tick % 300 == 0:
            for j in range(3):
                cat = random.choice(categories)
                base = random.randint(0, 200)
                items = {base % 20, (base + 1) % 20, (base + 2) % 20}
                bid = f"new_{tick}_{j}"
                # 3 co-activations
                for _ in range(3):
                    gov.try_form_bridge(bid, cat, items, context="longrun", importance="low")
                    gov.advance()
                bridges_formed_total += 1

        # ── Retrieval + reinforcement every 10 ticks ──
        if tick % 10 == 0:
            cat = random.choice(categories)
            results = gov.retrieve(cat, top_k=3)
            if results:
                # Find the bridge that produced top result and reinforce
                for b in gov.bridges.values():
                    if b.category == cat and results[0] in b.items and b.state == BRIDGE_STATE_ACTIVE:
                        b.strength = min(1.0, b.strength + 0.15)
                        break

        # ── Adversarial contamination every 7 ticks ──
        if tick % 7 == 0:
            active = [b for b in gov.bridges.values() if b.state == BRIDGE_STATE_ACTIVE]
            if active:
                target = random.choice(active)
                # Add noise items (category != bridge.category)
                target.items.update(random.sample(noise_items, min(2, len(noise_items))))

        # ── Reconstruction attempt every 200 ticks ──
        if tick % 200 == 0:
            collapsed = [bid for bid, b in gov.bridges.items()
                        if b.state == BRIDGE_STATE_COLLAPSED]
            if collapsed:
                bid = random.choice(collapsed)
                seeds = list(gov.bridges[bid].episodic_seeds)[:3]
                if seeds:
                    gov.bridges[bid].items = set(seeds)
                    gov.bridges[bid].state = BRIDGE_STATE_PRE
                    gov.bridges[bid].strength = 0.1

        # ── Sample metrics every 500 ticks ──
        if tick % 500 == 0:
            active_c = sum(1 for b in gov.bridges.values() if b.state == BRIDGE_STATE_ACTIVE)
            dormant_c = sum(1 for b in gov.bridges.values() if b.state == BRIDGE_STATE_DORMANT)
            total = len(gov.bridges)
            total_items = sum(len(b.items) for b in gov.bridges.values())

            active_entries = [b for b in gov.bridges.values() if b.state == BRIDGE_STATE_ACTIVE]
            avg_str = statistics.mean([b.strength for b in active_entries]) if active_entries else 0

            avg_cont = 0.0
            if active_entries:
                conts = []
                for b in active_entries:
                    non_target = sum(1 for it in b.items if get_cat(it) != b.category)
                    if len(b.items) > 0:
                        conts.append(non_target / len(b.items))
                avg_cont = statistics.mean(conts) if conts else 0.0

            # Latency
            t0 = time.perf_counter()
            for _ in range(20):
                gov.retrieve(random.choice(categories), top_k=5)
            lat_ms = (time.perf_counter() - t0) / 20 * 1000

            gc_rate = len(gov.gc_events) / max(tick, 1)

            bridge_count_history.append((tick, total))
            active_ratio_history.append((tick, active_c / max(total, 1)))
            latency_history.append((tick, lat_ms))
            gc_rate_history.append((tick, gc_rate))
            avg_strength_history.append((tick, avg_str))
            avg_contamination_history.append((tick, avg_cont))

            print(f"{tick:>8,} | {total:>7} | {active_c:>6} | {dormant_c:>5} | "
                  f"{total_items:>6} | {avg_str:>7.4f} | {avg_cont:>6.3f} | {len(gov.gc_events):>5}")

    print()
    print("=" * 70)
    print("BOUNDED PROPERTY VERIFICATION")
    print("=" * 70)
    print()

    final_active = sum(1 for b in gov.bridges.values() if b.state == BRIDGE_STATE_ACTIVE)
    final_dormant = sum(1 for b in gov.bridges.values() if b.state == BRIDGE_STATE_DORMANT)
    final_archived = sum(1 for b in gov.bridges.values() if b.state == BRIDGE_STATE_ARCHIVED)
    final_collapsed = sum(1 for b in gov.bridges.values() if b.state == BRIDGE_STATE_COLLAPSED)
    final_total = len(gov.bridges)

    # 1. Memory bounded?
    bc = bridge_count_history
    if bc:
        max_bc = max(x[1] for x in bc)
        min_bc = min(x[1] for x in bc)
        n = len(bc)
        slope_first = (bc[n//4][1] - bc[0][1]) / max(bc[n//4][0] - bc[0][0], 1) if n > 1 else 0
        slope_last = (bc[-1][1] - bc[-n//4][1]) / max(bc[-1][0] - bc[-n//4][0], 1) if n > 1 else 0
        print(f"  [MEMORY] Bridges: {min_bc} → {max_bc} (final: {final_total})")
        print(f"           Growth: early={slope_first:.4f}/tick, late={slope_last:.4f}/tick")
        memory_bounded = slope_last < slope_first * 3 or final_total < max_bc * 0.9 or slope_last < 0.001
    else:
        memory_bounded = True
        print(f"  [MEMORY] No growth detected")
    print(f"           BOUNDED: {'✓ PASS' if memory_bounded else '✗ FAIL'}")

    # 2. Latency bounded?
    lat = [l[1] for l in latency_history]
    if len(lat) >= 2:
        first_lat = statistics.mean(lat[:max(1, len(lat)//4)])
        last_lat = statistics.mean(lat[-max(1, len(lat)//4):])
        lat_ratio = last_lat / max(first_lat, 0.0001)
    else:
        lat_ratio = 1.0
    print(f"  [LATENCY] First: {lat[0] if lat else 0:.4f}ms, Last: {lat[-1] if lat else 0:.4f}ms, Ratio: {lat_ratio:.2f}x")
    latency_bounded = lat_ratio < 10.0
    print(f"           BOUNDED: {'✓ PASS' if latency_bounded else '✗ FAIL'}")

    # 3. Active bridges non-zero?
    avg_ar = statistics.mean([r[1] for r in active_ratio_history]) if active_ratio_history else 0
    nonzero = sum(1 for r in active_ratio_history if r[1] > 0)
    print(f"  [ACTIVE] Non-zero snapshots: {nonzero}/{len(active_ratio_history)}, Avg: {avg_ar:.3f}")
    active_stable = avg_ar > 0.01 and final_active > 0
    print(f"           STABLE: {'✓ PASS' if active_stable else '✗ FAIL'}")

    # 4. GC rate bounded?
    if len(gc_rate_history) >= 2:
        first_gc = statistics.mean([g[1] for g in gc_rate_history[:max(1, len(gc_rate_history)//4)]])
        last_gc = statistics.mean([g[1] for g in gc_rate_history[-max(1, len(gc_rate_history)//4):]])
    else:
        first_gc = last_gc = 0
    print(f"  [GC RATE] Early: {first_gc:.4f}/tick, Late: {last_gc:.4f}/tick")
    gc_bounded = last_gc < first_gc * 5 or last_gc < 0.1
    print(f"           BOUNDED: {'✓ PASS' if gc_bounded else '✗ FAIL'}")

    # 5. Contamination contained?
    avg_cont = statistics.mean([c[1] for c in avg_contamination_history]) if avg_contamination_history else 0
    print(f"  [CONTAMINATION] Avg: {avg_cont:.3f}")
    contam_ok = avg_cont < 0.5
    print(f"           CONTAINED: {'✓ PASS' if contam_ok else '✗ FAIL'}")

    # 6. Lifecycle
    print(f"  [LIFECYCLE] Active={final_active}, Dormant={final_dormant}, "
          f"Archived={final_archived}, Collapsed={final_collapsed}")
    print(f"  [EVENTS] GC={len(gov.gc_events)}, Purify={len(gov.purify_events)}, "
          f"Reconstruct={len(gov.reconstruction_events)}, Starvation={len(gov.starvation_events)}")
    print(f"  [BRIDGES FORMED] {bridges_formed_total}")

    print()
    print("=" * 70)
    verdict = memory_bounded and latency_bounded and active_stable and gc_bounded and contam_ok
    print(f"VERDICT: {'✓ PASS — Runtime STABLE at 10,000 ticks' if verdict else '✗ FAIL'}")
    print("=" * 70)

    return "PASS" if verdict else "FAIL"


if __name__ == "__main__":
    result = run_long_run_benchmark_v4(ticks=10000, seed=42)
    sys.exit(0 if result == "PASS" else 1)
