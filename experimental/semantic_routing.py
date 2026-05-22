#!/usr/bin/env python3
"""
v0.12 — Pure Assisted Path Isolation

Core Question: Is semantic's utility purely from routing (not importance monopoly)?

Design Principles:
  1. importance-flattened: semantic=0.5, episodic=0.5 (no importance advantage)
  2. no direct semantic retrieval: semantic NEVER appears in top-k directly
  3. semantic ONLY does: activate → route → cluster episodic
  4. All metrics measure routing quality, not semantic retrieval share

Key Metrics:
  - retrieval coherence      (episodic cluster activation quality)
  - retrieval entropy       (should DECREASE with good routing)
  - repeated top-k          (should be LOW in routing mode)
  - activation spread       (episodic coverage from semantic routing)
  - routing precision       (semantic→correct episodic precision)
  - long-horizon stability  (consistency over 1000+ ticks)

Hypothesis:
  If pure assisted routing works with flattened importance,
  then semantic's value = organizational, not importance-based.
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
    layer: str = "episodic"
    access_count: int = 0
    last_access: int = 0
    importance: float = 0.5
    created: int = 0
    activation: float = 0.0
    routing_boost: float = 0.0  # extra from semantic routing

    def score(self, query: str, tick: int) -> float:
        recency = 1.0 / (1.0 + (tick - self.last_access) * 0.01)
        access = self.access_count / (1.0 + self.access_count)
        # FLATTENED importance - no semantic advantage
        imp = self.importance
        routing = self.routing_boost
        return recency * 0.4 + access * 0.3 + imp * 0.3 + routing


class RoutingExperiment:
    """
    Tests pure semantic routing with importance-flattened comparison.

    Two modes:
      baseline    — standard retrieval, no routing, flattened importance
      routing     — semantic activates → routes to episodic clusters
                   semantic NEVER directly returned in top-k
    """

    def __init__(self, mode='baseline'):
        self.mode = mode
        self.working: List[Memory] = []
        self.episodic: List[Memory] = []
        self.semantic: List[Memory] = []
        self.tick = 0
        self.retrieval_log: List[Dict] = []
        self.activation_log: List[Dict] = []
        self.routing_precision_log: List[float] = []

    def _init_semantic(self):
        """Semantic schemas for routing — NO importance advantage."""
        schemas = [
            ("project_schema",    "project planning task goal milestone",     0.5),
            ("debug_schema",      "debug error fix log trace issue",           0.5),
            ("meeting_schema",    "meeting discussion participants agenda",     0.5),
            ("coding_schema",     "code implementation function module",        0.5),
            ("review_schema",    "review feedback changes improvement",        0.5),
            ("planning_schema",  "planning strategy steps timeline resource",  0.5),
            ("research_schema",  "research analysis findings experiment",      0.5),
            ("design_schema",    "design architecture pattern component",      0.5),
        ]
        for sid, content, importance in schemas:
            m = Memory(
                id=f"sem_{sid}",
                content=content,
                layer="semantic",
                importance=importance,  # FLATTENED to 0.5
                created=0,
                access_count=0,
                last_access=0,
                activation=0.0,
                routing_boost=0.0
            )
            self.semantic.append(m)

    def store(self, content: str, topic_tag: str) -> Memory:
        """Store with topic tag for routing ground-truth."""
        m = Memory(
            id=f"mem_{self.tick}_{random.randint(1000,9999)}",
            content=content,
            layer="working",
            importance=0.5,  # FLATTENED
            created=self.tick,
            access_count=1,
            last_access=self.tick,
            activation=1.0,
            routing_boost=0.0
        )
        m.topic_tag = topic_tag  # ground truth for routing precision
        self.working.append(m)
        return m

    def evict_working(self):
        while len(self.working) > 8:
            m = self.working.pop(0)
            m.layer = "episodic"
            self.episodic.append(m)

    def _semantic_routing(self, query: str, t: int) -> Dict[str, float]:
        """
        Phase 1: Semantic routing - select schemas matching query.
        Returns {topic_tag: activation_strength}.
        """
        q_words = set(query.lower().split())
        topic_activations: Dict[str, float] = defaultdict(float)

        for m in self.semantic:
            m_words = set(m.content.lower().split())
            overlap = len(q_words & m_words)
            if overlap > 0:
                strength = min(1.0, overlap * 0.2)
                m.access_count += 1
                m.last_access = t
                m.activation = strength
                self.activation_log.append({
                    'tick': t, 'semantic_id': m.id,
                    'activation': strength, 'overlap': overlap
                })
                # Map semantic schema to topic tag
                topic_activations[m.id.split('_')[1]] = strength

        return topic_activations

    def _route_to_episodic(self, topic_activations: Dict[str, float], t: int):
        """
        Phase 2: Spread activation from semantic schemas to episodic clusters.
        """
        if not topic_activations:
            return

        for m in self.episodic:
            topic = getattr(m, 'topic_tag', 'unknown')
            if topic in topic_activations:
                strength = topic_activations[topic]
                m.routing_boost = max(m.routing_boost, strength * 0.4)
                m.activation = max(m.activation, strength * 0.5)
                m.last_access = t

    def _compute_entropy(self, top_k: List[Memory]) -> float:
        """Compute entropy of top-k layer distribution."""
        if not top_k:
            return 0.0
        counts = defaultdict(int)
        for m in top_k:
            counts[m.layer] += 1
        total = sum(counts.values())
        probs = [c / total for c in counts.values()]
        return -sum(p * math.log2(p) for p in probs if p > 0)

    def _compute_coherence(self, top_k: List[Memory]) -> float:
        """
        Coherence = topic一致性 of top-k results.
        High coherence = all results belong to same cluster.
        """
        if not top_k:
            return 0.0
        topics = [getattr(m, 'topic_tag', 'unknown') for m in top_k]
        if not topics:
            return 0.0
        # HHI of topic distribution (lower = more diverse = lower coherence)
        counts = defaultdict(int)
        for t in topics:
            counts[t] += 1
        total = len(topics)
        hhi = sum((c / total) ** 2 for c in counts.values())
        # Coherence = how concentrated (1 - HHI normalized)
        return hhi

    def retrieve(self, query: str, topic_tag: str, top_k: int = 5) -> List[Memory]:
        self.tick += 1
        t = self.tick

        if self.mode == 'routing':
            # Phase 1: semantic routing
            topic_activations = self._semantic_routing(query, t)
            # Phase 2: spread to episodic
            self._route_to_episodic(topic_activations, t)

        # Gather candidates
        candidates = self.working + self.episodic
        # In routing mode, NEVER include semantic in top-k
        if self.mode != 'routing':
            candidates += self.semantic

        # Score with FLATTENED importance
        scored = [(m.score(query, t), m) for m in candidates]
        scored.sort(key=lambda x: -x[0])
        results = [m for _, m in scored[:top_k]]

        # Update access
        for m in results:
            m.access_count += 1
            m.last_access = t

        # Clear routing boosts after retrieval
        if self.mode == 'routing':
            for m in self.episodic:
                m.routing_boost *= 0.5  # decay

        # Compute metrics
        sem_in_topk = sum(1 for m in results if m.layer == 'semantic')
        topic_coherence = self._compute_coherence(results)
        entropy = self._compute_entropy(results)

        # Routing precision: did activated schemas match query topic?
        routing_precision = 0.0
        if self.mode == 'routing':
            correct = sum(1 for m in results if getattr(m, 'topic_tag', '') == topic_tag)
            routing_precision = correct / max(len(results), 1)

        self.retrieval_log.append({
            'tick': t,
            'query': query,
            'topic_tag': topic_tag,
            'result_topics': [getattr(m, 'topic_tag', '') for m in results],
            'layers': [m.layer for m in results],
            'semantic_in_topk': sem_in_topk,
            'coherence': topic_coherence,
            'entropy': entropy,
            'routing_precision': routing_precision,
        })

        return results

    def run(self, scenario: str, ticks: int = 500) -> Dict:
        """Run scenario and collect metrics."""

        # Topic-tagged content for each scenario
        if scenario == 'topic_switching':
            # Alternates between 4 topics every 25 ticks
            topics = ['project', 'debug', 'meeting', 'coding']
            def get_query(i):
                t = topics[(i // 25) % 4]
                return t, f"{t} session {i} notes and details"
            queries_content = [get_query(i) for i in range(ticks)]

        elif scenario == 'gradual_drift':
            # Topics gradually shift: project→debug→meeting over time
            def get_query(i):
                if i < 200:   return 'project', f"project planning task {i} milestone"
                elif i < 350: return 'debug',   f"debugging error issue {i} trace"
                else:          return 'meeting', f"meeting discussion {i} agenda participants"
            queries_content = [get_query(i) for i in range(ticks)]

        elif scenario == 'stable_topic':
            # Single stable topic — tests long-horizon stability
            def get_query(i):
                return 'project', f"project planning task {i} details subtask milestone"
            queries_content = [get_query(i) for i in range(ticks)]

        elif scenario == 'burst_interleaved':
            # Bursts of activity with interleaved topics
            def get_query(i):
                cycle = i % 100
                if cycle < 40:   return 'project', f"project task planning {i} goal"
                elif cycle < 60: return 'debug',   f"debug error {i} fix log"
                elif cycle < 80: return 'project', f"project review {i} feedback"
                else:            return 'debug',   f"debug trace {i} issue"
            queries_content = [get_query(i) for i in range(ticks)]

        elif scenario == 'noisy_background':
            # 80% target topic + 20% noise
            def get_query(i):
                if i % 5 == 0:
                    return 'noise', f"random unrelated content {i}"
                return 'project', f"project planning task {i} goal milestone"
            queries_content = [get_query(i) for i in range(ticks)]

        else:
            queries_content = [('project', f"task {i}") for i in range(ticks)]

        self._init_semantic()

        for i in range(ticks):
            self.tick = i + 1
            query, content = queries_content[i]
            topic_tag = query
            self.store(content, topic_tag)
            self.evict_working()
            results = self.retrieve(query, topic_tag, top_k=5)

        return self._build_report(scenario, ticks)

    def _build_report(self, scenario: str, ticks: int) -> Dict:
        log = self.retrieval_log

        # Per-window metrics
        windows = [log[i:i+20] for i in range(0, len(log), 20)]
        window_coherences = [sum(e['coherence'] for e in w) / max(len(w), 1) for w in windows]
        window_precisions = [sum(e['routing_precision'] for e in w) / max(len(w), 1) for w in windows if w]

        # Stability: how many unique top-3 memories appear in last 10 retrievals
        recent = log[-10:]
        top3_ids = set()
        for entry in recent:
            for m_id in entry.get('result_ids', []):
                top3_ids.add(m_id)
        stability = 1.0 / (1.0 + len(top3_ids) / 10)

        # Repeated top-k: fraction of retrievals where top-3 == previous top-3
        repeated = 0
        for i in range(1, len(log)):
            prev = set(log[i-1].get('result_ids', [])[:3])
            curr = set(log[i].get('result_ids', [])[:3])
            if prev == curr:
                repeated += 1
        repeat_rate = repeated / max(len(log) - 1, 1)

        # Entropy trend
        entropies = [e['entropy'] for e in log]
        avg_entropy = sum(entropies) / max(len(entropies), 1)

        # Routing metrics
        routing_precision_avg = sum(window_precisions) / max(len(window_precisions), 1) if window_precisions else 0.0
        avg_coherence = sum(window_coherences) / max(len(window_coherences), 1)

        # Semantic in top-k (should be 0 for routing mode)
        sem_in_topk_pct = sum(e['semantic_in_topk'] for e in log) / max(len(log), 1)

        return {
            'scenario': scenario,
            'mode': self.mode,
            'ticks': ticks,
            'metrics': {
                'semantic_in_topk_pct': sem_in_topk_pct,
                'avg_coherence': avg_coherence,
                'avg_entropy': avg_entropy,
                'avg_routing_precision': routing_precision_avg,
                'retrieval_stability': stability,
                'repeat_rate': repeat_rate,
                'total_retrievals': len(log),
                'total_activations': len(self.activation_log),
            },
            'window_coherences': window_coherences[-10:],
            'window_precisions': window_precisions[-10:] if window_precisions else [],
        }


def run_experiment():
    scenarios = ['topic_switching', 'gradual_drift', 'stable_topic',
                 'burst_interleaved', 'noisy_background']
    modes = ['baseline', 'routing']

    results = {}
    for scenario in scenarios:
        results[scenario] = {}
        for mode in modes:
            exp = RoutingExperiment(mode=mode)
            results[scenario][mode] = exp.run(scenario, ticks=500)

    return results


def print_results(results: Dict):
    scenarios = list(results.keys())

    print("\n" + "=" * 90)
    print("v0.12 — PURE ASSISTED PATH ISOLATION")
    print("=" * 90)

    for scenario in scenarios:
        print(f"\n{'─' * 90}")
        print(f"SCENARIO: {scenario.upper()}")
        print(f"{'─' * 90}")

        modes = list(results[scenario].keys())
        header = f"{'Metric':<35}" + "".join(f"{m.upper():>14}" for m in modes) + f"{'DELTA':>12}"
        print(header)
        print("-" * 90)

        metric_rows = [
            ('semantic_in_topk_pct',      'sem_in_topk%',     'pct'),
            ('avg_coherence',              'topic_coherence',  'float'),
            ('avg_entropy',                'retrieval_entropy','float'),
            ('avg_routing_precision',      'routing_precision','float'),
            ('retrieval_stability',        'retrieval_stability','float'),
            ('repeat_rate',                'repeat_rate',      'float'),
            ('total_activations',          'sem_activations',  'int'),
        ]

        for key, label, fmt in metric_rows:
            row = f"{label:<35}"
            vals = {}
            for mode in modes:
                v = results[scenario][mode]['metrics'].get(key, 0.0)
                vals[mode] = v
                if fmt == 'pct':
                    row += f"{v:>14.2f}%"
                else:
                    row += f"{v:>14.4f}"
            delta = vals.get('routing', 0) - vals.get('baseline', 0)
            row += f"{delta:>+12.4f}"
            print(row)

        print()

        # Key findings
        base = results[scenario]['baseline']
        rout = results[scenario]['routing']

        coherence_delta = rout['metrics']['avg_coherence'] - base['metrics']['avg_coherence']
        entropy_delta = rout['metrics']['avg_entropy'] - base['metrics']['avg_entropy']
        precision = rout['metrics']['avg_routing_precision']
        repeat_delta = rout['metrics']['repeat_rate'] - base['metrics']['repeat_rate']

        findings = []
        if coherence_delta > 0.05:
            findings.append(f"✓ coherence +{coherence_delta:.3f}")
        if entropy_delta < -0.05:
            findings.append(f"✓ entropy {entropy_delta:+.3f}")
        if precision > 0.5:
            findings.append(f"✓ routing_precision={precision:.2f}")
        if repeat_delta < -0.05:
            findings.append(f"✓ repeat_rate {repeat_delta:+.3f}")

        if findings:
            print(f"  Routing Effects: {' | '.join(findings)}")
        else:
            print(f"  Routing Effects: no significant delta")

    # ─── Cross-Scenario Summary ─────────────────────────────────────────────

    print("\n" + "=" * 90)
    print("CROSS-SCENARIO ROUTING DELTAS")
    print("=" * 90)

    print(f"{'Scenario':<22}" + f"{'Coherence':>12}{'Entropy':>12}{'Precision':>12}{'Repeat':>12}")
    print("-" * 90)

    for scenario in scenarios:
        base = results[scenario]['baseline']
        rout = results[scenario]['routing']

        coh_d = rout['metrics']['avg_coherence'] - base['metrics']['avg_coherence']
        ent_d = rout['metrics']['avg_entropy'] - base['metrics']['avg_entropy']
        prec = rout['metrics']['avg_routing_precision']
        rep_d = rout['metrics']['repeat_rate'] - base['metrics']['repeat_rate']

        print(f"{scenario:<22}{coh_d:>+12.4f}{ent_d:>+12.4f}{prec:>12.4f}{rep_d:>+12.4f}")

    # ─── Architecture Verdict ─────────────────────────────────────────────────

    print("\n" + "=" * 90)
    print("ARCHITECTURE VERDICT")
    print("=" * 90)

    # Aggregate
    coh_deltas = []
    ent_deltas = []
    precisions = []
    for scenario in scenarios:
        base = results[scenario]['baseline']
        rout = results[scenario]['routing']
        coh_deltas.append(rout['metrics']['avg_coherence'] - base['metrics']['avg_coherence'])
        ent_deltas.append(rout['metrics']['avg_entropy'] - base['metrics']['avg_entropy'])
        precisions.append(rout['metrics']['avg_routing_precision'])

    avg_coh = sum(coh_deltas) / len(coh_deltas)
    avg_ent = sum(ent_deltas) / len(ent_deltas)
    avg_prec = sum(precisions) / len(precisions)

    print(f"""
  Importance-Flattened Routing Analysis:
  ─────────────────────────────────────────────────────────────────────
  avg_coherence_delta:  {avg_coh:+.4f}
  avg_entropy_delta:    {avg_ent:+.4f}
  avg_routing_precision:{avg_prec:.4f}

  Path Effectiveness:
    biased (v0.11):       +0.080 (importance monopoly)
    assisted (v0.11):      +0.320 (with importance advantage)
    routing (v0.12):      {'%.3f' % (avg_coh * 0.5 + (1-avg_ent) * 0.5) if True else 'N/A'} (pure routing, importance-flattened)
""")

    # Routing quality assessment
    routing_works = avg_coh > 0.05 or avg_ent < -0.05 or avg_prec > 0.5

    if routing_works:
        print("  ✓ SEMANTIC ROUTING HAS INDEPENDENT UTILITY")
        print("  → semantic's value is organizational, not importance-based")
        print("  → semantic = retrieval routing layer, not answer layer")
        routing_verdict = "routing_active"
    else:
        print("  ✗ SEMANTIC ROUTING HAS NO INDEPENDENT UTILITY")
        print("  → assisted value came purely from importance advantage")
        print("  → semantic is NOT a useful routing layer")
        routing_verdict = "routing_inert"

    print(f"""
  Hypothesis Test Results:
  ─────────────────────────────────────────────────────────────────────
  H1: semantic can route without importance advantage?
      {'✓ CONFIRMED' if avg_prec > 0.4 else '✗ REJECTED'} (precision={avg_prec:.3f})

  H2: routing increases topic coherence?
      {'✓ CONFIRMED' if avg_coh > 0.05 else '✗ REJECTED'} (delta={avg_coh:+.4f})

  H3: routing reduces retrieval entropy?
      {'✓ CONFIRMED' if avg_ent < -0.05 else '✗ REJECTED'} (delta={avg_ent:+.4f})

  H4: routing reduces repeated top-k?
      REQUIRES per-scenario analysis (see table above)

  Architecture Truth:
  ─────────────────────────────────────────────────────────────────────
  semantic layer role: {'RETRIEVAL ROUTING LAYER' if routing_works else 'INACTIVE ARCHIVE'}
  semantic value source: {'routing/organizational' if routing_works else 'importance monopoly'}
  routing verdict: {routing_verdict}
""")

    return results


if __name__ == '__main__':
    print("Running v0.12 Pure Assisted Path Isolation...")
    results = run_experiment()
    print_results(results)
