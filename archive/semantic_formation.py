#!/usr/bin/env python3
"""
Semantic Formation Experiment v0.10
====================================
Tests whether semantic memory emerges naturally from repeated experience,
or requires explicit consolidation mechanisms.

Two routes under test:
  Route A (Emergence):   repeated retrieval → episodic pattern → natural semantic
  Route B (Consolidation): episodic accumulation → offline distillation → semantic

Key observables:
  1. episodic redundancy    — does similar episodic count decrease?
  2. retrieval abstraction  — does retrieval shift toward semantic?
  3. semantic stability     — does semantic persist across time?
  4. self-reinforcement    — does semantic dominate retrieval?
  5. compression ratio     — does 3 episodic → 1 semantic emerge?
  6. consolidation trigger  — does semantic form without explicit trigger?

Output format:
  {
    "route": "emergence | consolidation | mixed | dead_layer",
    "signals": { episodic_redundancy, retrieval_abstraction, ... },
    "formation_trigger": "implicit | explicit | hybrid",
    "verdict": "semantic_exists | semantic_dead_layer"
  }
"""

import json
import os
import sys
import time
import random
import statistics
import argparse
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Optional

sys.path.insert(0, '/home/minimak/mcr')
from layered_memory import LayeredMemory
from memory_trace import TRACE_DIR

# ─── Experiment Config ────────────────────────────────────────────────────────

FORM_EXP_DIR = Path('/home/minimak/mcr/sem_exp')
FORM_EXP_DIR.mkdir(exist_ok=True)


# ─── Formation Metrics ────────────────────────────────────────────────────────

@dataclass
class FormationMetrics:
    """Tracks semantic formation signals over experiment lifetime."""
    tick: int = 0

    # Layer counts over time
    episodic_counts: list = field(default_factory=list)
    semantic_counts: list = field(default_factory=list)
    archive_counts: list = field(default_factory=list)

    # Redundancy tracking
    episodic_content_similarity: list = field(default_factory=list)  # avg pairwise overlap
    semantic_redundancy_ratio: list = field(default_factory=list)   # semantic/3 episodic (compression)

    # Retrieval abstraction
    retrieval_layer_sources: dict = field(default_factory=lambda: defaultdict(list))  # tick → {layer: count}
    abstraction_shift: list = field(default_factory=list)  # semantic contribution ratio over time

    # Stability
    semantic_age_distribution: list = field(default_factory=list)
    semantic_access_frequency: list = field(default_factory=list)

    # Self-reinforcement
    semantic_retrieval_share: list = field(default_factory=list)  # what % of top-K are semantic

    # Consolidation events
    episodic_promotions: list = field(default_factory=list)  # ticks when episodic→semantic happened
    consolidation_count: int = 0

    def to_dict(self):
        d = asdict(self)
        # Convert defaultdict to dict for JSON
        d['retrieval_layer_sources'] = dict(self.retrieval_layer_sources)
        return d


# ─── Experiment Scenarios ─────────────────────────────────────────────────────

class ExperimentScenario:
    """Base class for formation experiment scenarios."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    def generate_loop(self, ticks: int):
        """
        Generate a sequence of (tick, operation, params) tuples.
        operation: 'store' | 'retrieve' | 'review' | 'sleep'
        """
        raise NotImplementedError

    def expected_formation_route(self) -> str:
        """Hypothesis: which route should form semantic?"""
        raise NotImplementedError


class RepeatedGoalScenario(ExperimentScenario):
    """
    Route A test: Repeated same goal behavior.

    Hypothesis: Repeated retrieval of similar goals should naturally
    elevate episodic patterns into semantic.

    Loop:
      tick 1-100:  store "solving project task A", goal="project"
      tick 1-100:  retrieve "project task", goal="project"  (same goal repeated)
      tick 101-200: store "solving project task B", goal="project"
      tick 101-200: retrieve "project task", goal="project"
      tick 201-300: store "solving project task C", goal="project"
      tick 201-300: retrieve "project task", goal="project"

    If Route A (emergence): after ~100 retrievals, similar episodic should
    consolidate into a semantic pattern like "user prioritizes project work".

    If nothing forms: semantic remains dead layer.
    """

    def __init__(self):
        super().__init__(
            "repeated_goal",
            "Repeated same-goal behavior: store+retrieve same topic 300x"
        )

    def generate_loop(self, ticks: int):
        loop = []

        # Store project tasks + retrieve them with same goal
        for tick in range(1, ticks + 1):
            phase = (tick - 1) // 100  # 0,1,2,3
            task_id = phase + 1

            if tick % 10 == 1:  # store every 10th tick
                loop.append((
                    tick, 'store',
                    f"solving project task {task_id} — debugging issue {task_id}"
                ))

            # Always retrieve the project topic
            loop.append((
                tick, 'retrieve',
                "project task",
                "project_management"  # stable goal
            ))

            # Call periodic_review every 50 ticks
            if tick % 50 == 0:
                loop.append((tick, 'review'))

        return loop

    def expected_formation_route(self):
        return "emergence"


class PeriodicBehaviorScenario(ExperimentScenario):
    """
    Route A test: Periodic recurring behavior.

    Hypothesis: Stable periodic patterns should be recognized and
    compressed into semantic.

    Loop:
      Every 50 ticks: same pattern of store+retrieve
      After 500 ticks: system has seen 10 cycles of same behavior

    If Route A (emergence): "user has weekly review pattern" should form.
    If Route B (consolidation): nothing forms without explicit clustering.
    """

    def __init__(self):
        super().__init__(
            "periodic_behavior",
            "Stable periodic behavior: same 50-tick pattern repeated 10x"
        )

    def generate_loop(self, ticks: int):
        loop = []
        cycle_len = 50
        num_cycles = ticks // cycle_len

        for cycle in range(num_cycles):
            for offset in range(cycle_len):
                tick = cycle * cycle_len + offset + 1

                # Same pattern every cycle
                if offset % 10 == 1:
                    loop.append((
                        tick, 'store',
                        f"weekly review: organizing cycle {cycle+1}, planning next sprint"
                    ))

                loop.append((
                    tick, 'retrieve',
                    "weekly review planning",
                    "routine_management"
                ))

                if tick % 50 == 0:
                    loop.append((tick, 'review'))

        return loop

    def expected_formation_route(self):
        return "emergence"


class MultiContextScenario(ExperimentScenario):
    """
    Route B test: Multi-context reuse.

    Hypothesis: True semantic formation requires cross-context pattern
    detection, which doesn't happen naturally.

    Loop:
      tick 1-200:   context A (project work)
      tick 201-400: context B (debugging)
      tick 401-600: context A + context B both active

    If Route A (emergence): cross-context patterns compress into semantic.
    If Route B (consolidation): nothing forms without explicit clustering.
    """

    def __init__(self):
        super().__init__(
            "multi_context",
            "Multi-context behavior: same pattern across 2 contexts, then merged"
        )

    def generate_loop(self, ticks: int):
        loop = []

        for tick in range(1, ticks + 1):
            if tick <= 200:
                context = "project"
                loop.append((tick, 'store', f"completed {context} milestone {tick}"))
            elif tick <= 400:
                context = "debugging"
                loop.append((tick, 'store', f"fixed bug in {context} sprint {tick-200}"))
            else:
                context = "mixed"
                loop.append((tick, 'store', f"project and debugging overlap task"))

            loop.append((tick, 'retrieve', f"{context} status update", context))

            if tick % 50 == 0:
                loop.append((tick, 'review'))

        return loop

    def expected_formation_route(self):
        return "consolidation"


class ExplicitConsolidationScenario(ExperimentScenario):
    """
    Route B test: Explicit consolidation trigger.

    Hypothesis: Semantic ONLY forms when consolidation is explicitly triggered.
    Without consolidation calls, semantic remains empty.

    This is the control experiment.
    """

    def __init__(self):
        super().__init__(
            "explicit_consolidation",
            "Explicit consolidation: same data, but WITH periodic_review"
        )

    def generate_loop(self, ticks: int):
        loop = []

        # Same data as repeated_goal but WITH review calls
        for tick in range(1, ticks + 1):
            phase = (tick - 1) // 100
            task_id = phase + 1

            if tick % 10 == 1:
                loop.append((
                    tick, 'store',
                    f"solving project task {task_id} — high priority issue"
                ))

            loop.append((
                tick, 'retrieve',
                "project task",
                "project_management"
            ))

            # Explicit consolidation trigger EVERY 50 ticks
            if tick % 50 == 0:
                loop.append((tick, 'review'))

        return loop

    def expected_formation_route(self):
        return "consolidation"


class HighFrequencyRetrievalScenario(ExperimentScenario):
    """
    Route A stress test: Very high retrieval frequency on same memory.

    Hypothesis: Extreme repetition (same query 500x) should naturally
    cause the memory to be promoted to semantic via access_count mechanism.

    Loop:
      Single memory "user focuses on project work" stored once.
      Retrieved 500 times with same goal.
      periodic_review called every 50 ticks.

    Promotion rule requires: importance>=0.7 AND access_count>=3.
    With 500 retrievals, access_count should far exceed 3.
    """

    def __init__(self):
        super().__init__(
            "high_freq_retrieval",
            "Single memory: stored once, retrieved 500x with same goal"
        )

    def generate_loop(self, ticks: int):
        loop = []

        # Store the key memory at tick 1
        loop.append((1, 'store',
            "user focuses on project work — consistently prioritizes over other tasks"))

        # Retrieve it every tick
        for tick in range(1, ticks + 1):
            loop.append((
                tick, 'retrieve',
                "project work priority",
                "project_management"
            ))

            if tick % 50 == 0:
                loop.append((tick, 'review'))

        return loop

    def expected_formation_route(self):
        return "emergence"


SCENARIOS = {
    'repeated_goal': RepeatedGoalScenario,
    'periodic_behavior': PeriodicBehaviorScenario,
    'multi_context': MultiContextScenario,
    'explicit_consolidation': ExplicitConsolidationScenario,
    'high_freq_retrieval': HighFrequencyRetrievalScenario,
}


# ─── Core Formation Experiment ────────────────────────────────────────────────

class SemanticFormationExperiment:
    """
    Runs a formation experiment and collects metrics.

    Key design:
      - periodic_review is called explicitly (it's never auto-triggered)
      - We test BOTH with and without consolidation calls
      - We track every signal listed in the formation framework
    """

    def __init__(self, scenario: ExperimentScenario, base_path: str):
        self.scenario = scenario
        self.base_path = base_path
        self.mem = LayeredMemory(base_path)
        self.metrics = FormationMetrics()
        self._retrieval_traces = []
        self._start_time = None

    def run(self, ticks: int, verbose: bool = True):
        """Run the formation experiment for N ticks."""
        self._start_time = time.time()
        loop = self.scenario.generate_loop(ticks)

        if verbose:
            print(f"\n{'='*60}")
            print(f"  Semantic Formation Experiment: {self.scenario.name}")
            print(f"  {self.scenario.description}")
            print(f"  Hypothesis: {self.scenario.expected_formation_route()}")
            print(f"  Total operations: {len(loop)}")
            print(f"{'='*60}\n")

        for tick, op, *args in loop:
            self.metrics.tick = tick

            if op == 'store':
                content = args[0]
                importance = 0.5 + random.random() * 0.4  # 0.5-0.9
                self.mem.store(content, "general", importance=importance,
                             tags=['formation'], current_tick=tick)

            elif op == 'retrieve':
                query = args[0]
                goal = args[1] if len(args) > 1 else ""
                results = self.mem.retrieve(query, current_goal=goal,
                                           max_results=5, current_tick=tick)

                # Track which layers contributed to top results
                layers = [r.get('layer', 'unknown') for r in results]
                self.metrics.retrieval_layer_sources[tick] = {
                    'working': layers.count('working'),
                    'episodic': layers.count('episodic'),
                    'semantic': layers.count('semantic'),
                    'archive': layers.count('archive'),
                }

                # Semantic retrieval share (top-K contribution)
                if layers:
                    sem_share = layers.count('semantic') / len(layers)
                    self.metrics.semantic_retrieval_share.append(sem_share)

                # Abstraction shift metric
                if self.metrics.retrieval_layer_sources:
                    recent = list(self.metrics.retrieval_layer_sources.items())[-50:]
                    if recent:
                        total_sem = sum(v.get('semantic', 0) for _, v in recent)
                        total_all = sum(sum(v.values()) for _, v in recent)
                        self.metrics.abstraction_shift.append(
                            total_sem / total_all if total_all > 0 else 0.0
                        )

                self._retrieval_traces.append({
                    'tick': tick, 'query': query, 'goal': goal,
                    'results': results, 'layers': layers
                })

            elif op == 'review':
                actions = self.mem.periodic_review(tick)

                # Track consolidation events
                promoted = actions.get('promoted_to_semantic', [])
                if promoted:
                    self.metrics.consolidation_count += len(promoted)
                    self.metrics.episodic_promotions.append(tick)

            # Snapshot metrics every 25 ticks
            if tick % 25 == 0:
                self._snapshot_metrics()

        # Final snapshot
        self._snapshot_metrics()
        self._compute_formation_signals()

        if verbose:
            self._print_report()

        return self.metrics

    def _snapshot_metrics(self):
        """Take a snapshot of current layer state."""
        t = self.metrics.tick
        self.metrics.episodic_counts.append((t, len(self.mem.episodic)))
        self.metrics.semantic_counts.append((t, len(self.mem.semantic)))
        self.metrics.archive_counts.append((t, len(self.mem.archive)))

        # Episodic content similarity (character-level Jaccard sample)
        if len(self.mem.episodic) >= 2:
            sample = random.sample(self.mem.episodic,
                                   min(10, len(self.mem.episodic)))
            similarities = []
            for i, m1 in enumerate(sample):
                for m2 in sample[i+1:]:
                    c1 = set(m1.get('content', ''))
                    c2 = set(m2.get('content', ''))
                    if c1 and c2:
                        jaccard = len(c1 & c2) / len(c1 | c2)
                        similarities.append(jaccard)
            self.metrics.episodic_content_similarity.append(
                (t, statistics.mean(similarities) if similarities else 0.0)
            )

        # Semantic age distribution
        if self.mem.semantic:
            ages = [t - m.get('last_state_change_tick', 0)
                    for m in self.mem.semantic]
            self.metrics.semantic_age_distribution.append((t, statistics.mean(ages)))
            accesses = [m.get('access_count', 0) for m in self.mem.semantic]
            self.metrics.semantic_access_frequency.append((t, statistics.mean(accesses)))

    def _compute_formation_signals(self):
        """Compute the 5 formation signals from collected metrics."""

    def _print_report(self):
        """Print formation experiment report."""
        m = self.metrics
        elapsed = time.time() - self._start_time

        print(f"\n{'='*60}")
        print(f"  FORMATION REPORT: {self.scenario.name}")
        print(f"{'='*60}")

        # Layer evolution
        print(f"\n  Layer Evolution:")
        if m.episodic_counts:
            print(f"    Episodic: {m.episodic_counts[0][1]} → {m.episodic_counts[-1][1]}")
        if m.semantic_counts:
            print(f"    Semantic: {m.semantic_counts[0][1]} → {m.semantic_counts[-1][1]}")
        if m.archive_counts:
            print(f"    Archive:  {m.archive_counts[0][1]} → {m.archive_counts[-1][1]}")

        # Formation signals
        print(f"\n  5 Formation Signals:")
        print(f"    1. Episodic Redundancy:")
        if m.episodic_content_similarity:
            early = statistics.mean([v for _, v in m.episodic_content_similarity[:5]])
            late = statistics.mean([v for _, v in m.episodic_content_similarity[-5:]])
            trend = "↓ falling" if late < early else ("↑ rising" if late > early else "→ stable")
            print(f"       Early={early:.3f} Late={late:.3f} ({trend})")
            print(f"       → {'REDUNDANCY REDUCING (Route A plausible)' if late < early * 0.8 else 'NO REDUNDANCY REDUCTION'}")
        else:
            print(f"       (no data)")

        print(f"    2. Retrieval Abstraction Shift:")
        if m.abstraction_shift:
            early = statistics.mean(m.abstraction_shift[:10])
            late = statistics.mean(m.abstraction_shift[-10:])
            print(f"       Early={early:.3f} Late={late:.3f}")
            print(f"       → {'SEMANTIC CONTRIBUTING MORE (abstraction shift)' if late > early * 1.5 else 'NO SHIFT'}")
        else:
            print(f"       (no semantic retrieval)")

        print(f"    3. Semantic Stability:")
        if m.semantic_age_distribution:
            print(f"       Avg age: {m.semantic_age_distribution[-1][1]:.1f} ticks")
        if m.semantic_access_frequency:
            print(f"       Avg access: {m.semantic_access_frequency[-1][1]:.1f}")
        print(f"    4. Self-Reinforcement:")
        if m.semantic_retrieval_share:
            avg = statistics.mean(m.semantic_retrieval_share)
            print(f"       Semantic top-K share: {avg:.1%}")
            if avg > 0.5:
                print(f"       → DOMINANCE DETECTED (dangerous)")
            elif avg > 0.2:
                print(f"       → HEALTHY CONTRIBUTION")
            else:
                print(f"       → MARGINAL (semantic not contributing)")
        print(f"    5. Consolidation Events:")
        print(f"       Total episodic→semantic promotions: {m.consolidation_count}")
        print(f"       Promotion ticks: {m.episodic_promotions[:10]}{'...' if len(m.episodic_promotions) > 10 else ''}")

        # Compression ratio
        print(f"\n  Compression Ratio:")
        total_episodic = sum(c for _, c in m.episodic_counts) / max(1, len(m.episodic_counts))
        total_semantic = m.semantic_counts[-1][1] if m.semantic_counts else 0
        if total_semantic > 0:
            ratio = total_episodic / (total_semantic * 3)
            print(f"    Episodic/3×Semantic = {total_episodic:.1f}/({total_semantic}×3) = {ratio:.2f}")
            if ratio > 1.0:
                print(f"    → SEMANTIC IS COMPRESSING (3+ episodic per semantic)")
        else:
            print(f"    → NO SEMANTIC FORMED")

        print(f"\n  Retrieval samples (last 5):")
        for tr in self._retrieval_traces[-5:]:
            layers = tr['layers']
            sem_share = layers.count('semantic') / len(layers) if layers else 0
            print(f"    tick={tr['tick']} query='{tr['query'][:30]}' "
                  f"layers={layers} sem={sem_share:.0%}")

        print(f"\n  Runtime: {elapsed:.1f}s")
        print(f"{'='*60}\n")

    def save_results(self, path: Path):
        """Save experiment results to JSON."""
        data = {
            'scenario': self.scenario.name,
            'description': self.scenario.description,
            'expected_route': self.scenario.expected_formation_route(),
            'metrics': self.metrics.to_dict(),
            'retrieval_traces': self._retrieval_traces[-100:],  # last 100 only
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Results saved to {path}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Semantic Formation Experiment v0.10')
    parser.add_argument('--scenario', '-s', default='repeated_goal',
                       choices=list(SCENARIOS.keys()),
                       help='Formation scenario to run')
    parser.add_argument('--ticks', '-t', type=int, default=300,
                       help='Number of ticks to simulate')
    parser.add_argument('--save', action='store_true',
                       help='Save results to sem_exp/')
    parser.add_argument('--verbose', '-v', action='store_true', default=True,
                       help='Print report')
    args = parser.parse_args()

    scenario = SCENARIOS[args.scenario]()
    base_path = str(FORM_EXP_DIR / f"mem_{scenario.name}")

    # Clean up previous run
    import shutil
    if os.path.exists(base_path):
        shutil.rmtree(base_path)

    exp = SemanticFormationExperiment(scenario, base_path)
    metrics = exp.run(args.ticks, verbose=args.verbose)

    if args.save:
        path = FORM_EXP_DIR / f"result_{scenario.name}_{args.ticks}.json"
        exp.save_results(path)

    return metrics


if __name__ == '__main__':
    main()
