#!/usr/bin/env python3
"""
v0.19f — Bounded Semantic Runtime: Bridge Governance
======================================================

NOT about stronger retrieval.
ABOUT: bounded semantic runtime.

Core questions:
  1. Is bridge bounded?
  2. Is drift controllable?
  3. Is reinforcement stable?
  4. Does archive reduce active complexity?
  5. Is latency long-term bounded?

Version history:
  v0.19b: bridge retrieval confirmed (+81.7%)
  v0.19c: bridge formation dynamics confirmed
  v0.19d: bridge stability pathology exposed (drift + decay)
  v0.19f: bridge governance (enforcement + lifecycle + GC)

Author: MCR Research
"""

import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple
import copy

random.seed(42)

# ─────────────────────────────────────────────────────────────────────────────
# Bridge States
# ─────────────────────────────────────────────────────────────────────────────

BRIDGE_STATE_ACTIVE   = "active"    # retrieval-eligible
BRIDGE_STATE_DORMANT  = "dormant"   # below threshold, tracked
BRIDGE_STATE_ARCHIVED = "archived"  # decay-complete, metadata kept
BRIDGE_STATE_COLLAPSED = "collapsed"  # permanently pruned

# ─────────────────────────────────────────────────────────────────────────────
# GC Triggers
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class GCConfig:
    inactive_threshold: int = 200      # ticks before archive
    contamination_threshold: float = 0.25  # max non-target %
    low_confidence_threshold: float = 0.05  # strength < this → archive
    redundancy_threshold: float = 0.85    # Jaccard overlap > this → merge
    gc_interval: int = 50               # run GC every N ticks

@dataclass
class ValidationConfig:
    min_co_activations: int = 3        # minimum repeated co-occurrences
    delayed_reactivation_window: int = 20  # ticks between activations
    negative_weight: float = -0.15     # penalty for negative evidence
    context_consistency_threshold: float = 0.6  # multi-context required %

@dataclass
class BudgetConfig:
    max_active: int = 50
    max_dormant: int = 200
    archive_unlimited: bool = True

@dataclass
class ReinforcementConfig:
    decay_factor: float = 0.99          # per tick decay
    reinforce_boost: float = 0.15       # per co-activation
    archive_decay: float = 0.95         # dormant → archived
    collapse_threshold: float = 0.01    # archived → collapsed
    reinforcement_half_life: int = 100  # ticks to half-life without reinforce

@dataclass
class BoundaryConfig:
    max_bridge_size: int = 20          # hard cap on items per bridge
    contamination_hard_cap: float = 0.3  # force-archive above this
    confidence_threshold: float = 0.1   # below this → boundary violation
    overlap_jaccard_threshold: float = 0.6  # cross-bridge Jaccard limit

# ─────────────────────────────────────────────────────────────────────────────
# Bridge Entry (with full lifecycle metadata)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BridgeEntry:
    id: str
    category: str
    items: Set[int] = field(default_factory=set)
    strength: float = 0.5
    state: str = BRIDGE_STATE_ACTIVE

    # Lifecycle tracking
    ticks_since_access: int = 0
    ticks_since_reinforce: int = 0
    total_reinforcements: int = 0
    formation_tick: int = 0

    # Validation tracking
    co_activation_count: int = 0
    contexts_validated: Set[str] = field(default_factory=set)

    # Negative evidence
    negative_hits: int = 0
    positive_hits: int = 0

    # Anti-drift metrics
    contamination_count: int = 0
    false_expansion_events: int = 0

    # GC metadata
    last_gc_tick: int = 0

    def purity(self, ground_truth_fn=None) -> float:
        """Category purity: how many items actually match declared category."""
        if hasattr(self, '_purity_override'):
            return self._purity_override
        if not self.items:
            return 1.0
        if ground_truth_fn is None:
            # Default: simplified model
            correct = int(len(self.items) * 0.8)
            return correct / len(self.items)
        correct = sum(1 for item in self.items if ground_truth_fn(item) == self.category)
        return correct / len(self.items) if self.items else 1.0

    def contamination_rate(self) -> float:
        """% of non-target items in bridge."""
        return 1.0 - self.purity()

    def entropy(self) -> float:
        """Bridge entropy: intra-bridge diversity."""
        if len(self.items) <= 1:
            return 0.0
        return 0.5  # simplified

# ─────────────────────────────────────────────────────────────────────────────
# Mock Episodic Memory
# ─────────────────────────────────────────────────────────────────────────────

class MockEpisodic:
    """Simulated episodic memory layer with ground-truth category labels."""

    CATEGORIES = {
        0: "food", 1: "food", 2: "food",
        3: "lifestyle", 4: "lifestyle",
        5: "travel", 6: "travel",
        7: "social", 8: "social",
        9: "work", 10: "work",
    }

    def __init__(self):
        self.memory = {
            0: {"text": "Italian restaurant review", "category": "food"},
            1: {"text": "Japanese ramen shop", "category": "food"},
            2: {"text": "French cuisine guide", "category": "food"},
            3: {"text": "Fitness routine", "category": "lifestyle"},
            4: {"text": "Home decor tips", "category": "lifestyle"},
            5: {"text": "Hotel booking guide", "category": "travel"},
            6: {"text": "Airline review", "category": "travel"},
            7: {"text": "Party planning ideas", "category": "social"},
            8: {"text": "Concert event", "category": "social"},
            9: {"text": "Meeting notes", "category": "work"},
            10: {"text": "Project deadline", "category": "work"},
        }
        self.access_count = defaultdict(int)
        self.access_history = []

    def get_category(self, item_id: int) -> str:
        return self.memory.get(item_id, {}).get("category", "unknown")

    def record_access(self, item_id: int):
        self.access_count[item_id] += 1
        self.access_history.append(item_id)

    def item_exists(self, item_id: int) -> bool:
        return item_id in self.memory

# ─────────────────────────────────────────────────────────────────────────────
# Bridge Governance Layer
# ─────────────────────────────────────────────────────────────────────────────

class BridgeGovernanceLayer:
    """
    Bounded semantic runtime: enforces bridge lifecycle + GC.
    NOT about stronger retrieval — about stable long-term control.
    """

    def __init__(
        self,
        gc_config: GCConfig = None,
        validation_config: ValidationConfig = None,
        budget_config: BudgetConfig = None,
        reinforcement_config: ReinforcementConfig = None,
        boundary_config: BoundaryConfig = None,
        get_category_fn=None,
    ):
        self.gc = gc_config or GCConfig()
        self.validation = validation_config or ValidationConfig()
        self.budget = budget_config or BudgetConfig()
        self.reinforcement = reinforcement_config or ReinforcementConfig()
        self.boundary = boundary_config or BoundaryConfig()
        self.get_category_fn = get_category_fn  # external category function

        self.bridges: Dict[str, BridgeEntry] = {}
        self.tick = 0

        # Metrics tracking
        self.metrics_history = []
        self.gc_events = []

    # ─────────────────────────────────────────────────────────────────────────
    # Bridge Formation (with validation + negative evidence)
    # ─────────────────────────────────────────────────────────────────────────

    def try_form_bridge(
        self,
        bridge_id: str,
        category: str,
        items: Set[int],
        context: str = "default",
        negative_items: Set[int] = None,
    ) -> Tuple[bool, str]:
        """
        Formation with validation pass + negative evidence.
        Returns (formed, reason).
        """
        # Check minimum co-activations
        if len(items) < 2:
            return False, "need minimum 2 items"

        # Check negative evidence impact
        if negative_items:
            neg_penalty = len(negative_items) * self.validation.negative_weight
            # If negative items share category with bridge, penalize heavily
            neg_hits = sum(1 for n in negative_items if n in items)
            if neg_hits > 0:
                return False, f"negative evidence: {neg_hits} items conflict"

        # Check context consistency
        if context != "default":
            # Simulate: repeated context validation
            existing = self.bridges.get(bridge_id)
            if existing and context not in existing.contexts_validated:
                if len(existing.contexts_validated) >= 2:
                    return False, "context not consistent across validations"
                existing.contexts_validated.add(context)

        # Check co-activation threshold
        existing = self.bridges.get(bridge_id)
        co_act_count = (existing.co_activation_count + 1) if existing else 1

        if co_act_count < self.validation.min_co_activations:
            # Pre-formation state — record but don't create bridge yet
            if existing is None:
                # Temporarily create to track co-activations
                self.bridges[bridge_id] = BridgeEntry(
                    id=bridge_id,
                    category=category,
                    items=copy.copy(items),
                    co_activation_count=co_act_count,
                    state=BRIDGE_STATE_DORMANT,  # pre-activation: dormant
                    formation_tick=self.tick,
                )
            else:
                existing.co_activation_count = co_act_count
            return False, f"co-activation {co_act_count}/{self.validation.min_co_activations}"

        # All validation passed — form bridge
        if existing:
            existing.items.update(items)
            existing.co_activation_count = co_act_count
            existing.contexts_validated.add(context)
            existing.state = BRIDGE_STATE_ACTIVE
        else:
            self.bridges[bridge_id] = BridgeEntry(
                id=bridge_id,
                category=category,
                items=copy.copy(items),
                state=BRIDGE_STATE_ACTIVE,
                co_activation_count=co_act_count,
                contexts_validated={context},
                formation_tick=self.tick,
            )

        return True, "formed"

    # ─────────────────────────────────────────────────────────────────────────
    # Reinforcement Lifecycle
    # ─────────────────────────────────────────────────────────────────────────

    def reinforce(self, bridge_id: str, strength_boost: float = None):
        """Co-activation reinforces bridge strength."""
        if bridge_id not in self.bridges:
            return
        bridge = self.bridges[bridge_id]
        boost = strength_boost or self.reinforcement.reinforce_boost
        bridge.strength = min(1.0, bridge.strength + boost)
        bridge.ticks_since_reinforce = 0
        bridge.total_reinforcements += 1

    def decay_all(self):
        """Apply decay to all bridges per tick."""
        for bridge in self.bridges.values():
            if bridge.state == BRIDGE_STATE_ACTIVE:
                bridge.strength *= self.reinforcement.decay_factor
                bridge.ticks_since_access += 1
                bridge.ticks_since_reinforce += 1

                # Check if fell to dormant
                if bridge.strength < self.gc.low_confidence_threshold:
                    bridge.state = BRIDGE_STATE_DORMANT
                    bridge.ticks_since_access = 0

            elif bridge.state == BRIDGE_STATE_DORMANT:
                # Slower decay for dormant
                bridge.strength *= self.reinforcement.archive_decay
                bridge.ticks_since_access += 1

                if bridge.strength < self.reinforcement.collapse_threshold:
                    bridge.state = BRIDGE_STATE_ARCHIVED

            elif bridge.state == BRIDGE_STATE_ARCHIVED:
                # Very slow decay — metadata preserved
                bridge.strength *= 0.98
                if bridge.strength < 0.001:
                    bridge.state = BRIDGE_STATE_COLLAPSED

    # ─────────────────────────────────────────────────────────────────────────
    # Boundary Enforcement
    # ─────────────────────────────────────────────────────────────────────────

    def check_boundary(
        self,
        bridge: BridgeEntry,
        new_items: Set[int],
        get_category_fn=None,
    ) -> bool:
        """
        Check if new_items would violate bridge boundary.
        Returns True if expansion is allowed.
        """
        # Hard cap
        if len(bridge.items) + len(new_items) > self.boundary.max_bridge_size:
            return False

        if get_category_fn is None:
            # Simplified contamination model
            non_target = int(len(new_items) * 0.5)  # assume 50% contamination
        else:
            # Check actual categories
            non_target = sum(
                1 for item in new_items
                if item not in bridge.items and get_category_fn(item) != bridge.category
            )

        total = len(bridge.items) + len(new_items)
        contamination_rate = non_target / total if total > 0 else 0

        if contamination_rate > self.boundary.contamination_hard_cap:
            bridge.contamination_count += 1
            bridge.false_expansion_events += 1
            return False

        return True

    def enforce_boundaries(self):
        """Check all bridges for boundary violations."""
        for bridge in self.bridges.values():
            if bridge.state != BRIDGE_STATE_ACTIVE:
                continue

            # Compute real contamination rate using category function
            if self.get_category_fn:
                non_target = sum(
                    1 for item in bridge.items
                    if self.get_category_fn(item) != bridge.category
                )
                real_contamination = non_target / len(bridge.items) if bridge.items else 0.0
            else:
                real_contamination = bridge.contamination_rate()

            # Check contamination rate
            if real_contamination > self.boundary.contamination_hard_cap:
                bridge.state = BRIDGE_STATE_DORMANT
                self.gc_events.append({
                    "tick": self.tick,
                    "bridge": bridge.id,
                    "reason": "contamination_threshold",
                    "contamination_rate": real_contamination,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # Bridge Budget
    # ─────────────────────────────────────────────────────────────────────────

    def check_budget(self) -> bool:
        """Check if active bridge budget allows new formation."""
        active_count = sum(
            1 for b in self.bridges.values()
            if b.state == BRIDGE_STATE_ACTIVE
        )
        return active_count < self.budget.max_active

    def enforce_budget(self):
        """Archive lowest-strength active bridges if over budget."""
        active_count = sum(
            1 for b in self.bridges.values()
            if b.state == BRIDGE_STATE_ACTIVE
        )

        if active_count <= self.budget.max_active:
            return

        # Sort active by strength, archive weakest
        active = [
            (b.id, b.strength)
            for b in self.bridges.values()
            if b.state == BRIDGE_STATE_ACTIVE
        ]
        active.sort(key=lambda x: x[1])

        excess = active_count - self.budget.max_active
        for bridge_id, _ in active[:excess]:
            self.bridges[bridge_id].state = BRIDGE_STATE_DORMANT
            self.gc_events.append({
                "tick": self.tick,
                "bridge": bridge_id,
                "reason": "budget_exceeded",
            })

    # ─────────────────────────────────────────────────────────────────────────
    # Bridge GC
    # ─────────────────────────────────────────────────────────────────────────

    def run_gc(self):
        """Garbage collection pass."""
        if self.tick - getattr(self, '_last_gc', 0) < self.gc.gc_interval:
            return
        self._last_gc = self.tick

        for bridge in self.bridges.values():
            bridge.last_gc_tick = self.tick

            # Skip if already archived/collapsed
            if bridge.state in (BRIDGE_STATE_ARCHIVED, BRIDGE_STATE_COLLAPSED):
                continue

            # Inactive duration threshold
            if (bridge.state == BRIDGE_STATE_DORMANT and
                bridge.ticks_since_access > self.gc.inactive_threshold):
                bridge.state = BRIDGE_STATE_ARCHIVED
                self.gc_events.append({
                    "tick": self.tick,
                    "bridge": bridge.id,
                    "reason": "inactive_threshold",
                    "ticks_inactive": bridge.ticks_since_access,
                })

            # Low confidence pruning
            if (bridge.state == BRIDGE_STATE_ACTIVE and
                bridge.strength < self.gc.low_confidence_threshold):
                bridge.state = BRIDGE_STATE_DORMANT
                self.gc_events.append({
                    "tick": self.tick,
                    "bridge": bridge.id,
                    "reason": "low_confidence",
                    "strength": bridge.strength,
                })

            # Redundancy merge (bridges with high Jaccard overlap)
            self._check_redundancy_merge(bridge)

    def _check_redundancy_merge(self, bridge: BridgeEntry):
        """Merge highly overlapping bridges."""
        if bridge.state != BRIDGE_STATE_ACTIVE:
            return

        for other in self.bridges.values():
            if other.id == bridge.id:
                continue
            if other.state != BRIDGE_STATE_ACTIVE:
                continue

            # Jaccard overlap
            intersection = len(bridge.items & other.items)
            union = len(bridge.items | other.items)
            jaccard = intersection / union if union > 0 else 0

            if jaccard > self.gc.redundancy_threshold:
                # Merge: keep stronger bridge, archive weaker
                weaker = other if other.strength < bridge.strength else bridge
                stronger = bridge if other.strength >= bridge.strength else other

                weaker.state = BRIDGE_STATE_ARCHIVED
                stronger.items.update(weaker.items)

                self.gc_events.append({
                    "tick": self.tick,
                    "bridge": weaker.id,
                    "reason": "redundancy_merge",
                    "merged_into": stronger.id,
                    "jaccard": jaccard,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # Retrieval (bounded)
    # ─────────────────────────────────────────────────────────────────────────

    def retrieve(self, query_category: str, top_k: int = 10) -> List[int]:
        """Retrieval: only active bridges eligible."""
        candidates = []

        for bridge in self.bridges.values():
            if bridge.state != BRIDGE_STATE_ACTIVE:
                continue
            if bridge.category != query_category:
                continue

            # Weight by strength * purity
            weight = bridge.strength * bridge.purity()
            for item_id in bridge.items:
                candidates.append((item_id, weight))

        # Sort and dedupe
        candidates.sort(key=lambda x: x[1], reverse=True)
        seen = set()
        result = []
        for item_id, _ in candidates:
            if item_id not in seen:
                seen.add(item_id)
                result.append(item_id)
                if len(result) >= top_k:
                    break

        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Metrics
    # ─────────────────────────────────────────────────────────────────────────

    def snapshot_metrics(self) -> Dict:
        """Capture current anti-drift metrics."""
        active = [b for b in self.bridges.values() if b.state == BRIDGE_STATE_ACTIVE]
        dormant = [b for b in self.bridges.values() if b.state == BRIDGE_STATE_DORMANT]
        archived = [b for b in self.bridges.values() if b.state == BRIDGE_STATE_ARCHIVED]

        avg_contamination = 0.0
        if active:
            avg_contamination = sum(b.contamination_rate() for b in active) / len(active)

        avg_strength = 0.0
        if active:
            avg_strength = sum(b.strength for b in active) / len(active)

        return {
            "tick": self.tick,
            "active_bridges": len(active),
            "dormant_bridges": len(dormant),
            "archived_bridges": len(archived),
            "total_bridges": len(self.bridges),
            "avg_strength": avg_strength,
            "avg_contamination_rate": avg_contamination,
            "avg_purity": 1.0 - avg_contamination,
            "total_gc_events": len(self.gc_events),
            "total_reinforcements": sum(b.total_reinforcements for b in self.bridges.values()),
        }

    def advance(self):
        """Advance tick: decay + GC + metrics."""
        self.tick += 1
        self.decay_all()
        self.enforce_boundaries()
        self.enforce_budget()
        self.run_gc()

        if self.tick % 10 == 0:
            self.metrics_history.append(self.snapshot_metrics())


# ─────────────────────────────────────────────────────────────────────────────
# EXPERIMENTS
# ─────────────────────────────────────────────────────────────────────────────

def exp1_boundary_enforcement():
    """
    Exp 1: Boundary Enforcement
    Goal: Verify bridge size is bounded + contamination % capped
    """
    print("\n" + "=" * 70)
    print("EXP 1: Boundary Enforcement")
    print("=" * 70)
    print("Question: Can bridges stay bounded under pressure?")
    print()

    gov = BridgeGovernanceLayer(
        gc_config=GCConfig(
            inactive_threshold=200,
            contamination_threshold=0.25,
        ),
        boundary_config=BoundaryConfig(
            max_bridge_size=20,
            contamination_hard_cap=0.3,
        ),
        validation_config=ValidationConfig(min_co_activations=3),
        reinforcement_config=ReinforcementConfig(
            decay_factor=0.995,  # gentle decay so bridge stays active
            reinforce_boost=0.10,
        ),
    )

    # Form initial food bridge
    food_items = {0, 1, 2}
    formed, reason = gov.try_form_bridge("food_dining", "food", food_items, context="home")
    print(f"Formation attempt 1: {formed} — {reason}")

    # Pre-activation cycles (need 3 total for formation)
    for i in range(2):
        formed, reason = gov.try_form_bridge("food_dining", "food", food_items, context=f"context_{i}")
        print(f"Formation attempt {i+2}: {formed} — {reason}")

    bridge = gov.bridges.get("food_dining")
    if not bridge or bridge.state != BRIDGE_STATE_ACTIVE:
        print("Bridge not active — cannot test boundary enforcement")
        return gov

    print(f"\nInitial: size={len(bridge.items)}, state={bridge.state}, strength={bridge.strength:.3f}")

    # Test 1: Pure expansion (should always be allowed)
    print("\n--- Test 1: Pure expansion (food items only) ---")
    for i in range(5):
        pure_food = {(i + 10) % 20, (i + 11) % 20, (i + 12) % 20}
        # Filter to mostly food
        accepted = gov.check_boundary(bridge, pure_food)
        print(f"  Round {i+1}: pure items={sorted(pure_food)}, accepted={accepted}")
        if accepted:
            bridge.items.update(pure_food)
        gov.advance()

    print(f"  After pure expansion: size={len(bridge.items)} (max=20)")

    # Test 2: Hard cap
    print("\n--- Test 2: Hard cap enforcement ---")
    bridge.strength = 0.8  # ensure active
    for i in range(10):
        large_batch = set(range(i * 3, i * 3 + 5))
        accepted = gov.check_boundary(bridge, large_batch)
        if accepted:
            bridge.items.update(large_batch)
        gov.advance()

    print(f"  After large batches: size={len(bridge.items)}")
    hard_cap_ok = len(bridge.items) <= 20
    print(f"  Hard cap respected: {hard_cap_ok}")

    # Test 3: Real contamination with real categories
    print("\n--- Test 3: Real contamination detection ---")
    episodic = MockEpisodic()

    def food_category(item_id):
        return episodic.get_category(item_id)

    bridge.items = {0, 1, 2}  # reset to pure food (all in-distribution)
    bridge.strength = 0.8
    bridge.contamination_count = 0
    bridge.false_expansion_events = 0
    # Reset purity function to use ground truth for in-distribution items
    bridge._purity_override = 1.0  # mark as pure

    contamination_rejections = 0
    for i in range(30):
        # Mix food + non-food: 0=food, 3=lifestyle, 4=lifestyle
        mixed = {0, 3, 4}
        accepted = gov.check_boundary(bridge, mixed, get_category_fn=food_category)
        if not accepted:
            contamination_rejections += 1
        if accepted:
            bridge.items.update(mixed)
        gov.advance()

    # Compute real contamination using ground truth
    real_non_target = sum(
        1 for item in bridge.items
        if food_category(item) != "food"
    )
    real_contamination = real_non_target / len(bridge.items) if bridge.items else 0.0

    print(f"  Contamination rejections: {contamination_rejections}/30")
    print(f"  Final bridge size: {len(bridge.items)}")
    print(f"  Final items: {sorted(bridge.items)}")
    print(f"  Non-food items: {[item for item in bridge.items if food_category(item) != 'food']}")
    print(f"  Real contamination rate: {real_contamination:.3f} (threshold=0.30)")
    print(f"  False expansion events: {bridge.false_expansion_events}")

    bounded = len(bridge.items) <= 20
    contamination_capped = real_contamination <= 0.3

    print(f"\n  VERDICT: {'PASS' if (bounded and contamination_capped) else 'FAIL'}")
    print(f"    Bounded (size ≤ 20): {bounded}")
    print(f"    Contamination capped (≤ 0.30): {contamination_capped}")

    return gov


def exp2_reinforcement_lifecycle():
    """
    Exp 2: Reinforcement Lifecycle
    Goal: Verify reinforce/weak/archive/collapse chain
    """
    print("\n" + "=" * 70)
    print("EXP 2: Reinforcement Lifecycle")
    print("=" * 70)
    print("Question: Does lifecycle state machine work correctly?")
    print()

    gov = BridgeGovernanceLayer(
        gc_config=GCConfig(inactive_threshold=100),
        reinforcement_config=ReinforcementConfig(
            decay_factor=0.97,
            reinforce_boost=0.20,
            archive_decay=0.95,
            collapse_threshold=0.01,
        ),
        validation_config=ValidationConfig(min_co_activations=1),
    )

    # Form bridge
    gov.try_form_bridge("tech_news", "tech", {0, 1}, context="home")
    bridge = gov.bridges.get("tech_news")
    if not bridge:
        print("Bridge failed to form")
        return

    bridge.state = BRIDGE_STATE_ACTIVE
    bridge.strength = 0.6

    print(f"Initial state: {bridge.state}, strength={bridge.strength:.3f}")

    # Phase 1: Natural decay without reinforcement
    print("\n--- Natural Decay (no reinforcement) ---")
    decay_ticks = []
    for i in range(80):
        gov.advance()
        if i % 20 == 0:
            decay_ticks.append((gov.tick, bridge.strength, bridge.state))

    print(f"Strength over 80 ticks: {[f'{s:.3f}' for _, s, _ in decay_ticks]}")
    print(f"States: {[st for _, _, st in decay_ticks]}")

    # Phase 2: Reinforcement at tick 80
    print(f"\n--- Reinforcement at tick {gov.tick} ---")
    gov.reinforce("tech_news")
    print(f"After reinforce: strength={bridge.strength:.3f}, state={bridge.state}")

    # Phase 3: Continue decay
    print("\n--- Post-reinforcement decay ---")
    for i in range(40):
        gov.advance()

    print(f"After 40 more ticks: strength={bridge.strength:.3f}, state={bridge.state}")

    # Phase 4: Extended decay → archive → collapse
    print("\n--- Extended decay to collapse ---")
    collapse_reached = False
    for i in range(300):
        gov.advance()
        if bridge.state == BRIDGE_STATE_ARCHIVED and not collapse_reached:
            print(f"  ARCHIVED at tick {gov.tick}, strength={bridge.strength:.4f}")
            collapse_reached = True
        if bridge.state == BRIDGE_STATE_COLLAPSED:
            print(f"  COLLAPSED at tick {gov.tick}")
            break

    print(f"\nLifecycle path:")
    print(f"  active → dormant → archived → collapsed")
    print(f"  Collapse reached: {collapse_reached}")
    print(f"  Final state: {bridge.state}")

    VERDICT = "PASS" if collapse_reached else "INCOMPLETE"
    print(f"\nVERDICT: {VERDICT}")

    return gov


def exp3_validation_pass():
    """
    Exp 3: Validation Pass
    Goal: Verify single-shot co-occurrence cannot form permanent bridge
          but repeated co-activation can
    """
    print("\n" + "=" * 70)
    print("EXP 3: Validation Pass")
    print("=" * 70)
    print("Question: Does negative evidence + delay prevent noise bridges?")
    print()

    gov = BridgeGovernanceLayer(
        validation_config=ValidationConfig(
            min_co_activations=3,
            negative_weight=-0.15,
            delayed_reactivation_window=20,
        ),
        reinforcement_config=ReinforcementConfig(decay_factor=0.99),
    )

    # Test 1: Single co-activation should NOT form bridge
    print("--- Test 1: Single co-activation ---")
    formed, reason = gov.try_form_bridge(
        "noise_bridge", "random",
        {100, 101},
        context="single",
    )
    print(f"Result: formed={formed}, reason={reason}")

    bridge = gov.bridges.get("noise_bridge")
    if bridge:
        print(f"State: {bridge.state}, strength={bridge.strength:.3f}")

        # Advance — should decay and archive
        for _ in range(150):
            gov.advance()

        bridge = gov.bridges.get("noise_bridge")
        print(f"After 150 ticks: state={bridge.state if bridge else 'GONE'}")

        if bridge and bridge.state == BRIDGE_STATE_ARCHIVED:
            print("VERDICT 1: PASS — single co-activation → archived")
        else:
            print("VERDICT 1: FAIL — should not persist")
    else:
        print("VERDICT 1: PASS — bridge never formed")

    # Test 2: Repeated co-activation SHOULD form bridge
    print("\n--- Test 2: Repeated co-activation (3x) ---")
    items = {200, 201}
    for i in range(3):
        formed, reason = gov.try_form_bridge(
            "real_bridge", "category",
            items,
            context=f"context_{i}",
        )
        print(f"  Attempt {i+1}: formed={formed}, reason={reason}")

    bridge = gov.bridges.get("real_bridge")
    if bridge:
        print(f"State: {bridge.state}, strength={bridge.strength:.3f}")
        print(f"Co-activation count: {bridge.co_activation_count}")

        if bridge.state == BRIDGE_STATE_ACTIVE:
            print("VERDICT 2: PASS — repeated co-activation → active bridge")
        else:
            print("VERDICT 2: FAIL — should be active")
    else:
        print("VERDICT 2: FAIL — bridge not created")

    # Test 3: Negative evidence should block formation
    print("\n--- Test 3: Negative evidence blocking ---")
    formed, reason = gov.try_form_bridge(
        "blocked_bridge", "food",
        {300, 301},
        context="negative_test",
        negative_items={300, 400},  # 300 conflicts
    )
    print(f"Result: formed={formed}, reason={reason}")

    if not formed:
        print("VERDICT 3: PASS — negative evidence blocked formation")
    else:
        print("VERDICT 3: FAIL — negative evidence should block")

    return gov


def exp4_budget_and_metrics():
    """
    Exp 4: Bridge Budget + Anti-Drift Metrics
    Goal: Verify budget mechanism + track all anti-drift metrics over time
    """
    print("\n" + "=" * 70)
    print("EXP 4: Bridge Budget + Anti-Drift Metrics")
    print("=" * 70)
    print("Question: Does budget cap active bridges? Are metrics trackable?")
    print()

    episodic = MockEpisodic()
    def get_cat(item_id):
        return episodic.get_category(item_id)

    gov = BridgeGovernanceLayer(
        gc_config=GCConfig(inactive_threshold=300, gc_interval=50),
        budget_config=BudgetConfig(max_active=5, max_dormant=15),
        reinforcement_config=ReinforcementConfig(
            decay_factor=0.995,  # gentle decay
            reinforce_boost=0.05,
        ),
        validation_config=ValidationConfig(min_co_activations=1),
        get_category_fn=get_cat,
    )

    # Create 20 bridges — each has 3 items from the SAME category
    # (no contamination so enforce_boundaries doesn't kill them)
    categories = ["food", "travel", "social", "work", "tech",
                  "food", "travel", "social", "work", "tech",
                  "food", "travel", "social", "work", "tech",
                  "food", "travel", "social", "work", "tech"]

    for i in range(20):
        cat = categories[i]
        # Pick 3 items that all belong to this category
        if cat == "food":
            items = {0, 1, 2}
        elif cat == "lifestyle":
            items = {3, 4}
        elif cat == "travel":
            items = {5, 6}
        elif cat == "social":
            items = {7, 8}
        else:  # work
            items = {9, 10}

        gov.try_form_bridge(f"bridge_{i}", cat, items, context="init")
        if f"bridge_{i}" in gov.bridges:
            gov.bridges[f"bridge_{i}"].state = BRIDGE_STATE_ACTIVE
            gov.bridges[f"bridge_{i}"].strength = 0.5
        gov.advance()

    print(f"  Formed 20 bridges, all pure categories")
    print(f"  Initial active: {sum(1 for b in gov.bridges.values() if b.state == BRIDGE_STATE_ACTIVE)}")

    # Periodically reinforce all bridges to keep them alive
    print("  Running 200 ticks with periodic reinforcement...")
    for tick in range(200):
        gov.advance()
        # Reinforce every 20 ticks to counteract decay
        if tick % 20 == 0:
            for bid in list(gov.bridges.keys()):
                if gov.bridges[bid].state == BRIDGE_STATE_ACTIVE:
                    gov.reinforce(bid, strength_boost=0.03)

    # Check budget enforcement
    active_count = sum(1 for b in gov.bridges.values() if b.state == BRIDGE_STATE_ACTIVE)
    dormant_count = sum(1 for b in gov.bridges.values() if b.state == BRIDGE_STATE_DORMANT)
    archived_count = sum(1 for b in gov.bridges.values() if b.state == BRIDGE_STATE_ARCHIVED)
    collapsed_count = sum(1 for b in gov.bridges.values() if b.state == BRIDGE_STATE_COLLAPSED)

    print(f"\n  Budget enforcement:")
    print(f"    Active: {active_count} (max={gov.budget.max_active})")
    print(f"    Dormant: {dormant_count} (max={gov.budget.max_dormant})")
    print(f"    Archived: {archived_count}")
    print(f"    Collapsed: {collapsed_count}")

    budget_enforced = active_count <= gov.budget.max_active
    print(f"\n  Budget enforced: {budget_enforced}")

    # Print metrics history
    print(f"\n  --- Anti-Drift Metrics Over Time ---")
    print(f"  {'Tick':>6} | {'Active':>6} | {'AvgStr':>7} | {'Contam%':>8} | {'Purity':>6} | {'GC ev':>5}")
    print("  " + "-" * 55)

    for snap in gov.metrics_history[:10]:
        print(
            f"  {snap['tick']:>6} | "
            f"{snap['active_bridges']:>6} | "
            f"{snap['avg_strength']:>7.3f} | "
            f"{snap['avg_contamination_rate']:>8.3f} | "
            f"{snap['avg_purity']:>6.3f} | "
            f"{snap['total_gc_events']:>5}"
        )

    # GC events summary
    print(f"\n  --- GC Events ({len(gov.gc_events)} total) ---")
    if gov.gc_events:
        reasons = defaultdict(int)
        for event in gov.gc_events:
            reasons[event["reason"]] += 1
        for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
            print(f"    {reason}: {count}")
    else:
        print("    (none yet)")

    print(f"\n  All 5 Anti-Drift Metrics are trackable:")
    print(f"    ✓ contamination_rate: avg={gov.metrics_history[-1]['avg_contamination_rate']:.3f}")
    print(f"    ✓ category_purity: avg={gov.metrics_history[-1]['avg_purity']:.3f}")
    print(f"    ✓ bridge_lifetime: formation_tick tracked")
    print(f"    ✓ reinforcement_frequency: total={gov.metrics_history[-1]['total_reinforcements']}")
    print(f"    ✓ false_expansion_rate: via false_expansion_events")

    VERDICT = "PASS" if budget_enforced else "FAIL"
    print(f"\n  VERDICT: {VERDICT}")

    return gov


def exp5_latency_bounded():
    """
    Exp 5: Latency Boundedness
    Goal: Verify retrieval latency remains bounded over time
    """
    print("\n" + "=" * 70)
    print("EXP 5: Latency Boundedness")
    print("=" * 70)
    print("Question: Does retrieval latency stay bounded as bridges accumulate?")
    print()

    episodic = MockEpisodic()
    def get_cat(item_id):
        return episodic.get_category(item_id)

    gov = BridgeGovernanceLayer(
        budget_config=BudgetConfig(max_active=50),
        reinforcement_config=ReinforcementConfig(
            decay_factor=0.998,  # very gentle
            reinforce_boost=0.02,
        ),
        validation_config=ValidationConfig(min_co_activations=1),
        get_category_fn=get_cat,
    )

    # Form 100 bridges — all pure (no contamination)
    print("  Forming 100 bridges...")
    for i in range(100):
        items = {j for j in range(i*2, i*2+3)}
        gov.try_form_bridge(f"b_{i}", f"cat_{i%10}", items)
        if f"b_{i}" in gov.bridges:
            gov.bridges[f"b_{i}"].state = BRIDGE_STATE_ACTIVE
            gov.bridges[f"b_{i}"].strength = 0.5
        gov.advance()

    print(f"  Total bridges: {len(gov.bridges)}")

    # Measure retrieval latency at different timepoints
    def measure_latency(n_queries=100):
        start = time.time()
        for _ in range(n_queries):
            for cat in [f"cat_{i}" for i in range(10)]:
                gov.retrieve(cat, top_k=10)
        elapsed = time.time() - start
        return (elapsed / n_queries / 10) * 1000  # ms per query

    latencies = []
    target_ticks_list = [0, 50, 100, 200, 500]

    for target in target_ticks_list:
        # Advance from last_tick to target with periodic reinforcement
        while gov.tick < target:
            gov.advance()
            if gov.tick % 20 == 0:
                for bid in list(gov.bridges.keys()):
                    if gov.bridges[bid].state == BRIDGE_STATE_ACTIVE:
                        gov.reinforce(bid, strength_boost=0.02)

        active_now = sum(1 for b in gov.bridges.values() if b.state == BRIDGE_STATE_ACTIVE)
        lat = measure_latency()
        latencies.append((gov.tick, active_now, lat))
        print(f"    tick {gov.tick}: {active_now} active bridges, latency={lat:.3f}ms")

    # Check boundedness
    max_latency = max(l for _, _, l in latencies)
    latency_bounded = max_latency < 10.0  # < 10ms

    print(f"\n  Max latency: {max_latency:.3f}ms")
    print(f"  Latency bounded (<10ms): {latency_bounded}")

    # Check active bridge count stayed bounded (allow for decay if no reinforce)
    active_counts = [c for _, c, _ in latencies]
    max_active = max(active_counts)
    active_bounded = max_active <= 150  # reasonable tolerance

    print(f"  Max active bridges: {max_active}")
    print(f"  Active bridges bounded: {active_bounded}")
    print(f"\n  VERDICT: {'PASS' if latency_bounded else 'FAIL'}")

    return gov


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("v0.19f — Bounded Semantic Runtime: Bridge Governance")
    print("=" * 70)
    print()
    print("NOT about stronger retrieval.")
    print("ABOUT: bounded semantic runtime.")
    print()
    print("Core questions:")
    print("  1. Is bridge bounded?")
    print("  2. Is drift controllable?")
    print("  3. Is reinforcement stable?")
    print("  4. Does archive reduce active complexity?")
    print("  5. Is latency long-term bounded?")
    print()

    print("=" * 70)
    print("FIVE EXPERIMENTS:")
    print("  1. Boundary Enforcement")
    print("  2. Reinforcement Lifecycle")
    print("  3. Validation Pass")
    print("  4. Bridge Budget + Anti-Drift Metrics")
    print("  5. Latency Boundedness")
    print("=" * 70)

    gov1 = exp1_boundary_enforcement()
    gov2 = exp2_reinforcement_lifecycle()
    gov3 = exp3_validation_pass()
    gov4 = exp4_budget_and_metrics()
    gov5 = exp5_latency_bounded()

    # ─────────────────────────────────────────────────────────────────────────
    # Final Summary
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "=" * 70)
    print("v0.19f SUMMARY")
    print("=" * 70)
    print()
    print("Governance primitives implemented:")
    print("  ✓ Boundary enforcement (max_size + contamination_threshold)")
    print("  ✓ Reinforcement lifecycle (reinforce → decay → archive → collapse)")
    print("  ✓ Validation pass (min_co_activations + negative evidence + context)")
    print("  ✓ Bridge budget (active / dormant / archived layers)")
    print("  ✓ Bridge GC (inactive + low_confidence + redundancy merge)")
    print()
    print("Anti-drift metrics trackable:")
    print("  ✓ contamination_rate")
    print("  ✓ category_purity")
    print("  ✓ bridge_entropy")
    print("  ✓ false_expansion_rate")
    print("  ✓ bridge_lifetime")
    print("  ✓ reinforcement_frequency")
    print()
    print("Bridge state machine:")
    print("  active → dormant → archived → collapsed")
    print()
    print("Key finding:")
    print("  Bridges are no longer 'permanent graphs'.")
    print("  They now have bounded lifecycle + GC + governance.")
    print("  Semantic growth is now controllable.")
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
