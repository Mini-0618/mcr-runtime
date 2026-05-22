#!/usr/bin/env python3
"""
v0.15 — Stable Schema Adaptation (clean rewrite)

Key findings from v0.14:
  - REFRESH count = 0 across all scenarios
  - Formation was too aggressive (formed=4, forgot=8)
  - Naive adaptation churned schemas without improving routing

Root cause: topic_phases shows STATIC mid_500=0.98 precision (routing works!)
  but STABLE mid_500=0.000. The adaptation broke CORRECT routing.

Problem: Adaptation can only detect LOCAL mismatch (schema routes to wrong episodic).
But when topic globally shifts (project→debug), each schema's local view stays "correct"
because project_schema still routes to project episodic — until project episodic run out.

v0.15 Fixes:
  1. REASSIGN orphaned schemas: detect when schema topic "dies"
     (no new episodic for STALENESS_WINDOW=80 ticks)
     → repurposing for current active topic
  2. REFRESH before FORMATION: mismatch → update existing schema
  3. STABILITY WINDOW = 150: new schemas protected from eviction
  4. SLOW DECAY: 0.0005 (10x slower than episodic)
  5. OBSERVABILITY: every adaptation event has full reasoning
"""

import random
import math
import statistics
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
from collections import defaultdict

random.seed(42)


@dataclass
class Memory:
    id: str
    content: str
    topic_tag: str
    layer: str = "episodic"
    access_count: int = 0
    last_access: int = 0
    importance: float = 0.5
    created: int = 0
    activation: float = 0.0
    routing_boost: float = 0.0

    def score(self, tick: int) -> float:
        recency = 1.0 / (1.0 + (tick - self.last_access) * 0.01)
        access = self.access_count / (1.0 + self.access_count)
        return recency * 0.4 + access * 0.3 + self.importance * 0.3 + self.routing_boost


@dataclass
class Schema:
    id: str
    keywords: Set[str]
    topic_tag: str
    created_at: int = 0
    last_activation: int = 0
    activation_count: int = 0
    decay: float = 1.0
    activation_strength: float = 0.0
    linked_episodic: List[str] = field(default_factory=list)
    topic_history: List[str] = field(default_factory=list)
    refresh_count: int = 0
    protected_until: int = 0  # stability window

    def age(self, current_tick: int) -> int:
        return current_tick - self.created_at

    def is_stable(self, current_tick: int) -> bool:
        return current_tick < self.protected_until

    def score(self, query_words: Set[str]) -> float:
        overlap = len(self.keywords & query_words)
        return overlap * self.decay * (1.0 if self.decay > 0.05 else 0.0)


class StableSchemaSystem:
    """
    Stable schema adaptation with global staleness detection.

    Adaptation priority:
      1. REASSIGN orphaned schemas (key new mechanism)
      2. REFRESH existing schemas (on mismatch)
      3. FORM new schemas (last resort only)
      4. DECAY inactive schemas
      5. FORGET dead schemas

    Modes:
      static  — no adaptation (v0.13 baseline)
      naive   — v0.14 style (formation-first, fast decay)
      stable  — v0.15 style (reassign+refresh, slow decay, stability window)
    """

    STABILITY_WINDOW = 150
    SCHEMA_DECAY_RATE = 0.0005
    FORGET_THRESHOLD = 0.05
    REFRESH_OVERLAP = 0.3
    MAX_SCHEMAS = 12
    STALENESS_WINDOW = 80  # ticks without activation = orphaned

    def __init__(self, mode='stable'):
        self.mode = mode
        self.working: List[Memory] = []
        self.episodic: List[Memory] = []
        self.schemas: List[Schema] = []
        self.tick = 0
        self.retrieval_log: List[Dict] = []
        self.adaptation_log: List[Dict] = []
        self.schema_lifetimes: List[int] = []
        self.cluster_history: Dict[str, List[int]] = defaultdict(list)

    def _init_schemas(self):
        base = [
            ("project_schema",  {"project", "planning", "task", "goal", "milestone"}, "project"),
            ("debug_schema",   {"debug", "error", "fix", "log", "trace", "issue"}, "debug"),
            ("meeting_schema", {"meeting", "discussion", "participants", "agenda"}, "meeting"),
            ("coding_schema",  {"code", "implementation", "function", "class"}, "coding"),
            ("review_schema",  {"review", "feedback", "changes", "revision"}, "review"),
        ]
        for sid, keywords, topic in base:
            self.schemas.append(Schema(
                id=f"sem_{sid}",
                keywords=keywords,
                topic_tag=topic,
                created_at=0,
                last_activation=0,
                activation_count=0,
                decay=1.0,
                activation_strength=0.0,
                protected_until=self.STABILITY_WINDOW,
            ))

    def store(self, content: str, topic_tag: str):
        self.working.append(Memory(
            id=f"mem_{self.tick}_{random.randint(1000,9999)}",
            content=content,
            topic_tag=topic_tag,
            layer="working",
            importance=0.5,
            created=self.tick,
            access_count=1,
            last_access=self.tick,
            activation=1.0,
            routing_boost=0.0
        ))

    def evict_working(self):
        while len(self.working) > 8:
            m = self.working.pop(0)
            m.layer = "episodic"
            self.episodic.append(m)

    # ─── Routing ──────────────────────────────────────────────────────────

    def _route(self, query: str, t: int) -> Dict[str, float]:
        q_words = set(query.lower().split())
        activations: Dict[str, float] = defaultdict(float)
        for schema in self.schemas:
            score = schema.score(q_words)
            if score > 0:
                schema.last_activation = t
                schema.activation_count += 1
                schema.activation_strength = min(1.0, score * 0.3)
                activations[schema.topic_tag] = max(
                    activations[schema.topic_tag],
                    schema.activation_strength
                )
        return activations

    def _spread(self, activations: Dict[str, float], t: int):
        for m in self.episodic:
            if m.topic_tag in activations:
                strength = activations[m.topic_tag]
                m.routing_boost = max(m.routing_boost, strength * 0.5)
                m.activation = max(m.activation, strength * 0.4)
                m.last_access = t

    def _track_clusters(self):
        clusters: Dict[str, int] = defaultdict(int)
        for m in self.episodic:
            clusters[m.topic_tag] += 1
        for topic, count in clusters.items():
            self.cluster_history[topic].append(count)
            if len(self.cluster_history[topic]) > 10:
                self.cluster_history[topic].pop(0)

    # ─── Adaptation ────────────────────────────────────────────────────────

    def _best_schema_for_topic(self, topic_tag: str):
        """Find schema with best keyword overlap to topic_tag."""
        best, best_overlap = None, 0.0
        for s in self.schemas:
            overlap = len(s.keywords & {topic_tag}) / max(len(s.keywords), 1)
            if overlap > best_overlap:
                best_overlap = overlap
                best = s
        return best, best_overlap

    def _reassign_orphaned_schemas(self, current_topic: str, events: List[str]):
        """
        Key v0.15 mechanism: global staleness detection.

        Scenario: topic_phases
          Phase 1 (0-500): project_schema activated, project episodic created
          Phase 2 (500-1000): NO project episodic created, debug episodic active
          → project_schema has NOT been activated for STALENESS_WINDOW=80 ticks
          → But project_schema's local routing was "correct" (no mismatch)
          → project_schema is orphaned: topic died, but no local signal

        Detection:
          schema.last_activation is old AND current_topic != schema.topic_tag
          AND no active schema covers current_topic

        Action:
          Repurpose orphaned schema to current_topic
        """
        if self.mode != 'stable':
            return
        t = self.tick

        for schema in self.schemas:
            if schema.is_stable(t):
                continue  # protected schemas can't be reassigned

            stale_ticks = t - schema.last_activation
            if stale_ticks <= self.STALENESS_WINDOW:
                continue

            if schema.decay < self.FORGET_THRESHOLD:
                continue

            # Is current_topic already covered by an active schema?
            covered = any(
                s.topic_tag == current_topic and
                (t - s.last_activation) < self.STALENESS_WINDOW
                for s in self.schemas if s != schema
            )
            if covered:
                continue  # current topic already has active schema

            # REASSIGN: repurposing orphaned schema for current topic
            old_topic = schema.topic_tag
            schema.topic_tag = current_topic
            schema.topic_history.append(f"REASSIGN_from_{old_topic}")
            schema.keywords = schema.keywords | {current_topic}
            schema.decay = min(1.0, schema.decay + 0.3)
            schema.refresh_count += 1
            schema.last_activation = t

            events.append(
                f"REASSIGN {schema.id.split('_')[1]}: "
                f"{old_topic}→{current_topic} "
                f"(orphaned {stale_ticks}t, "
                f"refresh={schema.refresh_count})"
            )

    def _refresh_schema(self, schema: Schema, new_topic: str,
                        mismatched: List[Memory], events: List[str]):
        """REFRESH: update existing schema's topic_tag and keywords on mismatch."""
        old_topic = schema.topic_tag
        old_kw = len(schema.keywords)
        schema.topic_tag = new_topic
        schema.topic_history.append(new_topic)
        new_kw = set()
        for m in mismatched[:5]:
            new_kw.update(m.content.lower().split())
        schema.keywords = schema.keywords | new_kw
        schema.decay = min(1.0, schema.decay + 0.15)
        schema.refresh_count += 1
        schema.last_activation = self.tick
        for m in mismatched[:5]:
            if m.id not in schema.linked_episodic:
                schema.linked_episodic.append(m.id)
        events.append(
            f"REFRESH {schema.id.split('_')[1]}: {old_topic}→{new_topic} "
            f"(kw:{old_kw}→{len(schema.keywords)}, ref={schema.refresh_count})"
        )

    def _form_schema(self, topic_tag: str, episodic: List[Memory], events: List[str]):
        """FORM: last resort when no existing schema overlaps."""
        if len(self.schemas) >= self.MAX_SCHEMAS:
            evictable = [s for s in self.schemas
                        if not s.is_stable(self.tick) and s.decay < 0.3]
            if evictable:
                victim = min(evictable, key=lambda s: s.decay)
                self.schemas.remove(victim)
                self.schema_lifetimes.append(victim.age(self.tick))
                events.append(f"EVICT {victim.id}(decay={victim.decay:.3f},age={victim.age(self.tick)})")
            else:
                return

        keywords = set()
        for m in episodic[:10]:
            keywords.update(m.content.lower().split())

        self.schemas.append(Schema(
            id=f"sem_{topic_tag}_{self.tick}",
            keywords=keywords,
            topic_tag=topic_tag,
            created_at=self.tick,
            last_activation=self.tick,
            activation_count=1,
            decay=0.8,
            activation_strength=0.5,
            protected_until=self.tick + self.STABILITY_WINDOW,
        ))
        events.append(
            f"FORM {topic_tag}: kw={len(keywords)} "
            f"(protected {self.STABILITY_WINDOW}t)"
        )

    def _schema_decay(self):
        rate = self.SCHEMA_DECAY_RATE if self.mode == 'stable' else 0.005
        for schema in self.schemas:
            if self.tick - schema.last_activation > 50:
                schema.decay = max(0.0, schema.decay - rate)

    def _forget_dead_schemas(self, events: List[str]):
        to_remove = []
        for schema in self.schemas:
            if schema.decay < self.FORGET_THRESHOLD and not schema.is_stable(self.tick):
                to_remove.append(schema)
                events.append(
                    f"FORGET {schema.id.split('_')[1]} "
                    f"(decay={schema.decay:.3f}, age={schema.age(self.tick)}, "
                    f"refresh={schema.refresh_count})"
                )
        for schema in to_remove:
            self.schemas.remove(schema)
            self.schema_lifetimes.append(schema.age(self.tick))

    def _adapt(self, query: str, topic_tag: str,
                activated_schemas: List[Schema],
                routed_episodic: List[Memory]):
        """Run all adaptation mechanisms."""
        if self.mode == 'static':
            return

        events = []
        t = self.tick

        # 1. REASSIGN orphaned schemas (global staleness)
        self._reassign_orphaned_schemas(topic_tag, events)

        # 2. LOCAL MISMATCH → refresh or form
        for schema in activated_schemas:
            mismatched = [m for m in routed_episodic
                        if m.routing_boost > 0 and m.topic_tag != schema.topic_tag]
            if not mismatched:
                continue

            topic_counts: Dict[str, int] = defaultdict(int)
            for m in mismatched:
                topic_counts[m.topic_tag] += 1
            dominant = max(topic_counts, key=lambda tt: topic_counts[tt])

            candidate, overlap = self._best_schema_for_topic(dominant)
            if overlap >= self.REFRESH_OVERLAP and candidate:
                self._refresh_schema(candidate, dominant, mismatched, events)
            elif self.mode == 'stable':
                self._form_schema(dominant, mismatched, events)

        # 3. DECAY
        if self.mode in ('naive', 'stable'):
            self._schema_decay()

        # 4. FORGET
        if self.mode == 'stable':
            self._forget_dead_schemas(events)

        if events:
            self.adaptation_log.append({
                'tick': t, 'query': query[:30],
                'target_topic': topic_tag,
                'events': events,
                'schema_count': len(self.schemas),
            })

    # ─── Retrieval ────────────────────────────────────────────────────────

    def retrieve(self, query: str, topic_tag: str, top_k: int = 5) -> List[Memory]:
        self.tick += 1
        t = self.tick

        activations = self._route(query, t)
        activated_schemas = [s for s in self.schemas if s.activation_strength > 0]
        self._spread(activations, t)
        routed = [m for m in self.episodic if m.routing_boost > 0]
        self._adapt(query, topic_tag, activated_schemas, routed)

        candidates = self.working + self.episodic
        scored = [(m.score(t), m) for m in candidates]
        scored.sort(key=lambda x: -x[0])
        results = [m for _, m in scored[:top_k]]

        for m in results:
            m.access_count += 1
            m.last_access = t
        for m in self.episodic:
            m.routing_boost *= 0.5

        self._track_clusters()

        correct = sum(1 for m in results if m.topic_tag == topic_tag)
        precision = correct / max(len(results), 1)

        tc = defaultdict(int)
        for m in results:
            tc[m.topic_tag] += 1
        total = len(results)
        entropy = -sum((c/total)*math.log2(c/total) for c in tc.values() if c > 0)

        self.retrieval_log.append({
            'tick': t, 'query': query[:30], 'topic_tag': topic_tag,
            'result_topics': [m.topic_tag for m in results],
            'precision': precision, 'entropy': entropy,
            'schema_count': len(self.schemas),
            'activations': len(activations),
            'avg_decay': sum(s.decay for s in self.schemas) / max(len(self.schemas), 1),
            'protected': sum(1 for s in self.schemas if s.is_stable(t)),
            'total_refresh': sum(s.refresh_count for s in self.schemas),
            'decays': [s.decay for s in self.schemas],
        })
        return results

    def run(self, scenario: str, ticks: int = 1500) -> Dict:
        if scenario == 'topic_phases':
            def get(i):
                if i < 500:   return 'project', f"project planning task {i} milestone"
                elif i < 1000: return 'debug',   f"debugging error issue {i} trace"
                else:           return 'meeting', f"meeting discussion {i} agenda"
        elif scenario == 'gradual_drift':
            def get(i):
                alpha = 0.9 if i < 500 else (0.7 if i < 800 else (0.4 if i < 1100 else 0.2))
                return ('project' if random.random() < alpha else 'debug', f"task {i}")
        elif scenario == 'catastrophic':
            def get(i):
                return ('project' if i < 750 else 'debug', f"task {i}")
        elif scenario == 'mixed_burst':
            def get(i):
                topics = ['project', 'debug', 'coding', 'review']
                return topics[(i % 200) // 50], f"task {i}"
        else:
            def get(i): return 'project', f"task {i}"

        self._init_schemas()
        for i in range(ticks):
            self.tick = i + 1
            topic, content = get(i)
            self.store(content, topic)
            self.evict_working()
            self.retrieve(topic, topic, top_k=5)

        return self._build_report(scenario, ticks)

    def _seg(self, start: int, end: int) -> Dict:
        seg = self.retrieval_log[start:end]
        if not seg:
            return {}
        return {
            'precision': sum(e['precision'] for e in seg) / len(seg),
            'entropy': sum(e['entropy'] for e in seg) / len(seg),
            'schema_count': sum(e['schema_count'] for e in seg) / len(seg),
            'protected': sum(e['protected'] for e in seg) / len(seg),
            'avg_decay': sum(e['avg_decay'] for e in seg) / len(seg),
        }

    def _build_report(self, scenario: str, ticks: int) -> Dict:
        segs = {
            'first_500': self._seg(0, 500),
            'mid_500':   self._seg(500, 1000),
            'last_500':  self._seg(1000, 1500),
        }

        formed_e = [e for log in self.adaptation_log for ev in log['events'] for e in [ev] if 'FORM' in e]
        forgot_e = [e for log in self.adaptation_log for ev in log['events'] for e in [ev] if 'FORGET' in e]
        evict_e  = [e for log in self.adaptation_log for ev in log['events'] for e in [ev] if 'EVICT' in e]
        refresh_e = [e for log in self.adaptation_log for ev in log['events'] for e in [ev] if 'REFRESH' in e]
        reassign_e = [e for log in self.adaptation_log for ev in log['events'] for e in [ev] if 'REASSIGN' in e]

        churn = len(formed_e) + len(forgot_e)
        churn_rate = churn / (ticks / 100)
        rf_ratio = len(refresh_e) / max(len(formed_e), 1)

        recovery = None
        if scenario in ('topic_phases', 'catastrophic'):
            phase2 = 500 if scenario == 'topic_phases' else 750
            post = self.retrieval_log[phase2:phase2+200]
            for i, entry in enumerate(post):
                if entry['precision'] > 0.6:
                    recovery = i
                    break

        return {
            'scenario': scenario,
            'mode': self.mode,
            'ticks': ticks,
            'segment_metrics': segs,
            'adaptation_summary': {
                'total_events': len(self.adaptation_log),
                'refresh': len(refresh_e),
                'reassign': len(reassign_e),
                'formed': len(formed_e),
                'forgot': len(forgot_e),
                'evict': len(evict_e),
                'final_schema_count': len(self.schemas),
                'total_refresh': sum(s.refresh_count for s in self.schemas),
                'avg_lifetime': sum(self.schema_lifetimes) / max(len(self.schema_lifetimes), 1) if self.schema_lifetimes else 0,
                'churn_rate_per_100ticks': churn_rate,
                'refresh_to_formation_ratio': rf_ratio,
                'recovery_ticks': recovery,
            },
            'final_schemas': [
                (s.id.split('_')[1], round(s.decay, 3), s.topic_tag, s.age(ticks))
                for s in self.schemas
            ],
        }


def run_experiment():
    scenarios = ['topic_phases', 'gradual_drift', 'catastrophic', 'mixed_burst']
    modes = ['static', 'naive', 'stable']
    results = {}

    for scenario in scenarios:
        results[scenario] = {}
        for mode in modes:
            print(f"  {scenario}/{mode}...", end=' ', flush=True)
            sys = StableSchemaSystem(mode=mode)
            results[scenario][mode] = sys.run(scenario, ticks=1500)
            a = results[scenario][mode]['adaptation_summary']
            print(f"done (S={a['final_schema_count']}, R={a['refresh']}, "
                  f"RR={a['reassign']}, F={a['formed']}, "
                  f"Fo={a['forgot']}, R/F={a['refresh_to_formation_ratio']:.1f})")

    return results


def print_results(results: Dict):
    scenarios = list(results.keys())
    modes = list(results[scenarios[0]].keys())

    print("\n" + "=" * 95)
    print("v0.15 — STABLE SCHEMA ADAPTATION")
    print("=" * 95)

    # Precision table
    print(f"\n{'─' * 95}")
    print("PRECISION BY SEGMENT")
    print(f"{'─' * 95}")
    print(f"{'Scenario':<16}{'Segment':<10}" + "".join(f"{m.upper():>13}" for m in modes))
    print("-" * 95)
    for scenario in scenarios:
        for seg in ['first_500', 'mid_500', 'last_500']:
            row = f"{scenario:<16}{seg:<10}"
            for mode in modes:
                p = results[scenario][mode]['segment_metrics'].get(seg, {}).get('precision', 0.0)
                row += f"{p:>13.3f}"
            print(row)
        print()

    # Adaptation events
    print(f"{'─' * 95}")
    print("ADAPTATION EVENTS")
    print(f"{'─' * 95}")
    print(f"{'Metric':<28}" + "".join(f"{m.upper():>13}" for m in modes))
    print("-" * 95)
    for key, label in [
        ('refresh',           'Refresh'),
        ('reassign',         'Reassign'),
        ('formed',           'Formed'),
        ('forgot',           'Forgot'),
        ('evict',            'Evict'),
        ('total_refresh',    'Total Refresh'),
        ('churn_rate_per_100ticks', 'Churn/100t'),
        ('refresh_to_formation_ratio', 'R/F Ratio'),
    ]:
        row = f"{label:<28}"
        for mode in modes:
            vals = [results[s][mode]['adaptation_summary'].get(key, 0) for s in scenarios]
            avg = sum(vals) / len(vals)
            if isinstance(avg, float):
                row += f"{avg:>13.3f}"
            else:
                row += f"{avg:>13}"
        print(row)
    print()

    # Schema final state
    print(f"{'─' * 95}")
    print("FINAL SCHEMA STATE")
    print(f"{'─' * 95}")
    for scenario in scenarios:
        print(f"\n  {scenario.upper()}:")
        for mode in modes:
            fs = results[scenario][mode]['final_schemas']
            a = results[scenario][mode]['adaptation_summary']
            print(f"    {mode.upper()}: S={len(fs)}, lifetime={a['avg_lifetime']:.0f}t")
            for sid, decay, topic, age in fs[:4]:
                print(f"      {sid}: decay={decay}, topic={topic}, age={age}")

    # Recovery
    print(f"\n{'─' * 95}")
    print("ROUTING RECOVERY AFTER TOPIC SHIFT")
    print(f"{'─' * 95}")
    print(f"{'Scenario':<22}{'Naive':>12}{'Stable':>12}{'Delta':>12}")
    print("-" * 95)
    for scenario in ['topic_phases', 'catastrophic']:
        naive_r = results[scenario]['naive']['adaptation_summary'].get('recovery_ticks')
        stable_r = results[scenario]['stable']['adaptation_summary'].get('recovery_ticks')
        delta = (naive_r or 999) - (stable_r or 999)
        print(f"{scenario:<22}{(naive_r or 'N/A'):>12}{(stable_r or 'N/A'):>12}"
              f"{delta if stable_r else 'N/A':>12}")

    # Architecture verdict
    print("\n" + "=" * 95)
    print("ARCHITECTURE VERDICT — STABLE SCHEMA ADAPTATION")
    print("=" * 95)

    naive_churn = sum(results[s]['naive']['adaptation_summary']['churn_rate_per_100ticks'] for s in scenarios) / len(scenarios)
    stable_churn = sum(results[s]['stable']['adaptation_summary']['churn_rate_per_100ticks'] for s in scenarios) / len(scenarios)
    naive_rf = sum(results[s]['naive']['adaptation_summary']['refresh_to_formation_ratio'] for s in scenarios) / len(scenarios)
    stable_rf = sum(results[s]['stable']['adaptation_summary']['refresh_to_formation_ratio'] for s in scenarios) / len(scenarios)

    improvements = []
    for scenario in scenarios:
        for seg in ['mid_500', 'last_500']:
            np = results[scenario]['naive']['segment_metrics'].get(seg, {}).get('precision', 0.0)
            sp = results[scenario]['stable']['segment_metrics'].get(seg, {}).get('precision', 0.0)
            improvements.append((scenario, seg, sp - np, sp))

    avg_imp = sum(i[2] for i in improvements) / max(len(improvements), 1)

    stable_scenarios = sum(
        1 for s in scenarios
        if abs(results[s]['stable']['segment_metrics'].get('last_500', {}).get('precision', 0) -
               results[s]['stable']['segment_metrics'].get('first_500', {}).get('precision', 0)) < 0.25
    )

    stable_reassigns = sum(results[s]['stable']['adaptation_summary']['reassign'] for s in scenarios)
    stable_refreshes = sum(results[s]['stable']['adaptation_summary']['refresh'] for s in scenarios)

    print(f"""
  Core Fixes in v0.15:
    1. REASSIGN orphaned schemas (key new mechanism)
    2. REFRESH before FORMATION
    3. STABILITY WINDOW = 150 ticks
    4. SLOW DECAY = 0.0005

  Results:
    avg_precision_improvement (stable vs naive): {avg_imp:+.4f}
    naive_churn:   {naive_churn:.2f} per 100 ticks
    stable_churn:  {stable_churn:.2f} per 100 ticks
    naive R/F:     {naive_rf:.2f}
    stable R/F:    {stable_rf:.2f}
    stable_scenarios: {stable_scenarios}/4
    reassign_events (stable): {stable_reassigns}
    refresh_events (stable):  {stable_refreshes}

  Adaptation Quality:
    {'REASSIGN fired (key mechanism working)' if stable_reassigns > 0 else 'REASSIGN did not fire'}
    {'REFRESH dominant' if stable_rf > 0.5 else 'Still formation-heavy' if stable_rf < 0.3 else 'Mixed'}
    {'Churn reduced' if stable_churn < naive_churn else 'Churn still high'}
    {'Stable scenarios improved' if stable_scenarios >= 3 else 'Some degradation present'}

  Verdict:
    {'STABLE ADAPTATION WORKS ✓' if stable_rf >= 0.5 and avg_imp > 0.05 else
     'ADAPTATION PARTIAL ✓' if avg_imp > 0 else
     'ADAPTATION NEEDS REFINEMENT ✗'}

  Architecture Evolution:
    ─────────────────────────────────────────────────────────────────────
    v0.13: semantic routing (static schemas) → degrades on topic shift
    v0.14: naive adaptation → formation-first, REFRESH=0
    v0.15: stable adaptation → reassign+refresh, slow decay, stability window
    ─────────────────────────────────────────────────────────────────────
    Current role: RETRIEVAL ROUTING + ADAPTIVE TOPOLOGY LAYER

  Next:
    {'Agent integration now viable (schema lifecycle stable)' if stable_scenarios >= 3 else 'Schema lifecycle still needs refinement before agent integration'}
""")


if __name__ == '__main__':
    print("v0.15 — Stable Schema Adaptation")
    print("Modes: static vs naive vs stable")
    print("Scenarios: topic_phases, gradual_drift, catastrophic, mixed_burst\n")
    results = run_experiment()
    print_results(results)
