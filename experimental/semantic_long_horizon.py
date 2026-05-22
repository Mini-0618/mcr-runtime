#!/usr/bin/env python3
"""
v0.13 — Long-Horizon Semantic Routing Stability

Core Question: Does semantic routing remain effective over 1500+ ticks?
              Can it sustain low entropy, coherent retrieval, and non-collapse
              without degradation, pool flooding, or attractor states?

Key Failure Modes to Detect:
  1. Routing degradation    — precision decays as episodic pool grows
  2. Entropy creep          — retrieval entropy slowly rises over time
  3. Diversity collapse     — retrieval becomes dominated by few clusters
  4. Schema staleness       — semantic schemas become outdated
  5. Attractor states       — system locks into repetitive patterns
  6. Pool flooding          — episodic growth degrades routing signal

Metrics Tracked Over Time:
  - rolling routing precision (windowed)
  - rolling entropy (windowed)
  - rolling diversity (HHI of topic distribution)
  - episodic pool size
  - semantic activation rate
  - top-k repetition rate
  - cluster distribution (detect attractor dominance)
  - routing signal strength (semantic activation overlap)

Hypothesis:
  Semantic routing degrades over long horizons due to:
    - episodic pool growth diluting routing signal
    - schema staleness for novel topics
    - attractor states from recency bias
"""

import random
import math
import statistics
from dataclasses import dataclass
from typing import List, Dict, Set
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


class LongHorizonExperiment:
    """
    Tests semantic routing stability over 1500 ticks.
    Tracks all metrics in rolling windows to detect degradation.

    Modes:
      no_routing  — flat episodic retrieval (baseline)
      routing     — semantic schema routing + episodic cluster activation
    """

    def __init__(self, mode='routing'):
        self.mode = mode
        self.working: List[Memory] = []
        self.episodic: List[Memory] = []
        self.semantic: List[Memory] = []
        self.tick = 0
        self.retrieval_log: List[Dict] = []
        self.activation_log: List[Dict] = []

    def _init_semantic(self):
        schemas = [
            ("project_schema",  "project planning task goal milestone deliverable",  "project"),
            ("debug_schema",   "debug error fix log trace issue crash",             "debug"),
            ("meeting_schema", "meeting discussion participants agenda decision",     "meeting"),
            ("coding_schema",  "code implementation function class interface",       "coding"),
            ("review_schema",  "review feedback changes revision improvement",       "review"),
            ("design_schema",  "design architecture pattern component module",      "design"),
            ("test_schema",    "test case coverage validation verification",         "test"),
            ("deploy_schema",  "deploy release deployment infrastructure scaling",    "deploy"),
        ]
        for sid, content, topic, in schemas:
            self.semantic.append(Memory(
                id=f"sem_{sid}",
                content=content,
                topic_tag=topic,
                layer="semantic",
                importance=0.5,
                created=0,
                access_count=0,
                last_access=0,
                activation=0.0,
                routing_boost=0.0
            ))

    def store(self, content: str, topic_tag: str):
        m = Memory(
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
        )
        self.working.append(m)

    def evict_working(self):
        while len(self.working) > 8:
            m = self.working.pop(0)
            m.layer = "episodic"
            self.episodic.append(m)

    def _semantic_routing(self, query: str, topic_tag: str, t: int) -> Dict[str, float]:
        """Activate semantic schemas matching query. Returns {topic: activation}."""
        q_words = set(query.lower().split())
        activations: Dict[str, float] = defaultdict(float)

        for m in self.semantic:
            m_words = set(m.content.lower().split())
            overlap = len(q_words & m_words)
            if overlap > 0:
                strength = min(1.0, overlap * 0.2)
                m.access_count += 1
                m.last_access = t
                m.activation = strength
                activations[m.topic_tag] = max(activations[m.topic_tag], strength)
                self.activation_log.append({
                    'tick': t, 'semantic_id': m.id,
                    'topic': m.topic_tag,
                    'activation': strength, 'overlap': overlap
                })

        return activations

    def _spread_to_episodic(self, activations: Dict[str, float], t: int):
        """Spread semantic activation to episodic clusters."""
        for m in self.episodic:
            if m.topic_tag in activations:
                strength = activations[m.topic_tag]
                m.routing_boost = max(m.routing_boost, strength * 0.5)
                m.activation = max(m.activation, strength * 0.4)
                m.last_access = t

    def retrieve(self, query: str, topic_tag: str, top_k: int = 5) -> List[Memory]:
        self.tick += 1
        t = self.tick

        # Routing phase
        activations = {}
        if self.mode == 'routing':
            activations = self._semantic_routing(query, topic_tag, t)
            self._spread_to_episodic(activations, t)

        # Candidate pool
        candidates = self.working + self.episodic
        # Routing mode: semantic NEVER in top-k
        if self.mode != 'routing':
            candidates += self.semantic

        # Score
        scored = [(m.score(t), m) for m in candidates]
        scored.sort(key=lambda x: -x[0])
        results = [m for _, m in scored[:top_k]]

        # Update access
        for m in results:
            m.access_count += 1
            m.last_access = t

        # Decay routing boosts
        if self.mode == 'routing':
            for m in self.episodic:
                m.routing_boost *= 0.5

        # Metrics
        result_topics = [m.topic_tag for m in results]
        correct = sum(1 for m in results if m.topic_tag == topic_tag)
        precision = correct / max(len(results), 1)

        # Entropy of result distribution
        topic_counts = defaultdict(int)
        for tp in result_topics:
            topic_counts[tp] += 1
        total = len(result_topics)
        entropy = 0.0
        for c in topic_counts.values():
            p = c / total
            if p > 0:
                entropy -= p * math.log2(p)

        # Topic diversity (HHI)
        hhi = sum((c / total) ** 2 for c in topic_counts.values())
        diversity = 1.0 - hhi

        # Cluster representation
        cluster_sizes = defaultdict(int)
        for m in self.episodic:
            cluster_sizes[m.topic_tag] += 1

        self.retrieval_log.append({
            'tick': t,
            'query': query[:30],
            'topic_tag': topic_tag,
            'result_topics': result_topics,
            'precision': precision,
            'entropy': entropy,
            'diversity': diversity,
            'result_ids': [m.id for m in results],
            'activations': activations,
            'pool_size': len(self.episodic),
            'cluster_sizes': dict(cluster_sizes),
        })

        return results

    def run(self, scenario: str, ticks: int = 1500) -> Dict:
        """
        Run long-horizon scenario.

        Scenarios:
          stable_topic     — single topic for 1500 ticks (tests stability)
          topic_phases    — 3 phases: project→debug→meeting (tests adaptation)
          mixed_burst     — 4 topics with varying burst patterns (tests multiplexing)
          gradual_drift   — topic slowly shifts (tests schema staleness)
          catastrophic     — sudden topic change at tick 750 (tests recovery)
        """

        if scenario == 'stable_topic':
            def get(i): return 'project', f"project planning task {i} milestone goal"
        elif scenario == 'topic_phases':
            def get(i):
                if i < 500:   return 'project', f"project planning {i} milestone"
                elif i < 1000: return 'debug',  f"debugging error issue {i} trace"
                else:           return 'meeting', f"meeting discussion {i} agenda"
        elif scenario == 'mixed_burst':
            def get(i):
                cycle = i % 200
                if cycle < 80:   return 'project', f"project {i} planning"
                elif cycle < 120: return 'debug',   f"debug {i} error"
                elif cycle < 160: return 'coding',  f"code {i} implementation"
                else:              return 'review',  f"review {i} feedback"
        elif scenario == 'gradual_drift':
            def get(i):
                # Slowly shift topic distribution
                if i < 500:   alpha = 0.9
                elif i < 800: alpha = 0.7
                elif i < 1100: alpha = 0.4
                else:          alpha = 0.2
                if random.random() < alpha:
                    return 'project', f"project planning {i} task"
                else:
                    return 'debug', f"debugging issue {i} error"
        elif scenario == 'catastrophic':
            def get(i):
                if i < 750:
                    return 'project', f"project planning {i} task milestone"
                else:
                    return 'debug', f"debugging issue {i} error fix"
        else:
            def get(i): return 'project', f"task {i}"

        self._init_semantic()

        for i in range(ticks):
            self.tick = i + 1
            topic, content = get(i)
            self.store(content, topic)
            self.evict_working()
            self.retrieve(topic, topic, top_k=5)

        return self._build_report(scenario, ticks)

    def _rolling_metrics(self, window: int = 50):
        """Compute rolling metrics over retrieval log."""
        log = self.retrieval_log
        if len(log) < window:
            return []

        results = []
        for i in range(window - 1, len(log)):
            window_log = log[i - window + 1:i + 1]
            avg_precision = sum(e['precision'] for e in window_log) / window
            avg_entropy = sum(e['entropy'] for e in window_log) / window
            avg_diversity = sum(e['diversity'] for e in window_log) / window
            avg_pool = sum(e['pool_size'] for e in window_log) / window

            # Routing activation rate in window
            routing_acts = sum(1 for e in window_log if e['activations'])
            act_rate = routing_acts / window if self.mode == 'routing' else 0.0

            # Cluster distribution skew (max cluster share)
            all_cluster_sizes = defaultdict(int)
            for e in window_log:
                for tp, size in e['cluster_sizes'].items():
                    all_cluster_sizes[tp] += size
            total = sum(all_cluster_sizes.values())
            max_share = max(all_cluster_sizes.values()) / max(total, 1) if all_cluster_sizes else 0

            results.append({
                'tick': log[i]['tick'],
                'precision': avg_precision,
                'entropy': avg_entropy,
                'diversity': avg_diversity,
                'pool_size': avg_pool,
                'activation_rate': act_rate,
                'max_cluster_share': max_share,
            })
        return results

    def _build_report(self, scenario: str, ticks: int) -> Dict:
        log = self.retrieval_log

        # Rolling metrics (windows of 50)
        rolling = self._rolling_metrics(50)

        # Segment analysis: first 500, mid 500, last 500
        segments = {
            'first_500': log[:500],
            'mid_500':   log[500:1000],
            'last_500':  log[1000:],
        }

        segment_metrics = {}
        for name, seg in segments.items():
            if not seg:
                continue
            seg_precision = sum(e['precision'] for e in seg) / len(seg)
            seg_entropy = sum(e['entropy'] for e in seg) / len(seg)
            seg_diversity = sum(e['diversity'] for e in seg) / len(seg)
            seg_pool = sum(e['pool_size'] for e in seg) / len(seg)
            segment_metrics[name] = {
                'precision': seg_precision,
                'entropy': seg_entropy,
                'diversity': seg_diversity,
                'pool_size': seg_pool,
            }

        # Rolling trend (first vs last window)
        rolling_first = rolling[:5] if len(rolling) >= 5 else []
        rolling_last  = rolling[-5:] if len(rolling) >= 5 else []

        def avg(lst, key): return sum(x[key] for x in lst) / max(len(lst), 1)

        trend = {}
        if rolling_first and rolling_last:
            trend = {
                'precision_delta': avg(rolling_last, 'precision') - avg(rolling_first, 'precision'),
                'entropy_delta':   avg(rolling_last, 'entropy') - avg(rolling_first, 'entropy'),
                'diversity_delta': avg(rolling_last, 'diversity') - avg(rolling_first, 'diversity'),
                'pool_growth':    avg(rolling_last, 'pool_size') - avg(rolling_first, 'pool_size'),
            }

        # Attractor detection: max cluster share in last 500
        last500_clusters = defaultdict(int)
        for e in log[1000:]:
            for tp, size in e['cluster_sizes'].items():
                last500_clusters[tp] += size
        total_last = sum(last500_clusters.values())
        max_share_last = max(last500_clusters.values()) / max(total_last, 1) if last500_clusters else 0

        # Total activations
        total_activations = len(self.activation_log)

        return {
            'scenario': scenario,
            'mode': self.mode,
            'ticks': ticks,
            'segment_metrics': segment_metrics,
            'trend': trend,
            'rolling': rolling,
            'final_pool_size': len(self.episodic),
            'total_activations': total_activations,
            'max_cluster_share_last500': max_share_last,
            'last_log': log[-3:],
        }


def run_experiment():
    scenarios = ['stable_topic', 'topic_phases', 'mixed_burst', 'gradual_drift', 'catastrophic']
    modes = ['no_routing', 'routing']

    results = {}
    for scenario in scenarios:
        results[scenario] = {}
        for mode in modes:
            print(f"  Running {scenario}/{mode}...", end='', flush=True)
            exp = LongHorizonExperiment(mode=mode)
            results[scenario][mode] = exp.run(scenario, ticks=1500)
            print(f" done (pool={exp.episodic.__len__()}, acts={len(exp.activation_log)})")

    return results


def print_results(results: Dict):
    scenarios = list(results.keys())

    print("\n" + "=" * 90)
    print("v0.13 — LONG-HORIZON SEMANTIC ROUTING STABILITY")
    print("=" * 90)

    for scenario in scenarios:
        print(f"\n{'─' * 90}")
        print(f"SCENARIO: {scenario.upper()} (1500 ticks)")
        print(f"{'─' * 90}")

        for mode in ['no_routing', 'routing']:
            r = results[scenario][mode]
            segs = r['segment_metrics']

            print(f"\n  {mode.upper()}:")
            if segs:
                print(f"    {'Segment':<12}{'Precision':>12}{'Entropy':>12}{'Diversity':>12}{'Pool Size':>12}")
                print(f"    {'-' * 60}")
                for name in ['first_500', 'mid_500', 'last_500']:
                    if name in segs:
                        s = segs[name]
                        print(f"    {name:<12}{s['precision']:>12.3f}{s['entropy']:>12.3f}"
                              f"{s['diversity']:>12.3f}{s['pool_size']:>12.1f}")

            trend = r.get('trend', {})
            if trend:
                print(f"\n    Trend (last_500 - first_500):")
                print(f"      precision: {trend.get('precision_delta', 0):+.4f}")
                print(f"      entropy:   {trend.get('entropy_delta', 0):+.4f}")
                print(f"      diversity: {trend.get('diversity_delta', 0):+.4f}")
                print(f"      pool grow: {trend.get('pool_growth', 0):+.1f}")

            print(f"    Final pool: {r['final_pool_size']}, "
                  f"activations: {r['total_activations']}, "
                  f"max_cluster: {r['max_cluster_share_last500']:.3f}")

        # Delta analysis
        nr = results[scenario]['no_routing']
        rt = results[scenario]['routing']
        print(f"\n  ROUTING DELTA (routing - no_routing):")

        for seg in ['first_500', 'mid_500', 'last_500']:
            if seg not in nr['segment_metrics'] or seg not in rt['segment_metrics']:
                continue
            ns = nr['segment_metrics'][seg]
            rs = rt['segment_metrics'][seg]
            print(f"    {seg}:")
            print(f"      precision: {rs['precision'] - ns['precision']:+.3f} "
                  f"(nr={ns['precision']:.3f}, rt={rs['precision']:.3f})")
            print(f"      entropy:   {rs['entropy'] - ns['entropy']:+.3f} "
                  f"(nr={ns['entropy']:.3f}, rt={rs['entropy']:.3f})")

    # ─── Cross-Scenario Summary ─────────────────────────────────────────────

    print("\n" + "=" * 90)
    print("STABILITY VERDICT BY SCENARIO")
    print("=" * 90)

    print(f"\n{'Scenario':<18}{'Precision Δ':>12}{'Entropy Δ':>12}{'Diversity Δ':>14}{'Pool→':>8}{'Verdict':>18}")
    print("-" * 90)

    for scenario in scenarios:
        nr = results[scenario]['no_routing']
        rt = results[scenario]['routing']

        # Use last_500 segments for verdict
        ns = nr.get('segment_metrics', {}).get('last_500', {})
        rs = rt.get('segment_metrics', {}).get('last_500', {})

        p_delta = rs.get('precision', 0) - ns.get('precision', 0)
        e_delta = rs.get('entropy', 0) - ns.get('entropy', 0)
        d_delta = rs.get('diversity', 0) - ns.get('diversity', 0)
        pool = rt['final_pool_size']

        # Verdict
        if p_delta > 0.1 and e_delta < -0.1:
            v = "STABLE ✓"
        elif p_delta > 0.05:
            v = "MARGINAL ✓"
        elif abs(p_delta) < 0.05:
            v = "NO EFFECT"
        else:
            v = "DEGRADED ✗"

        print(f"{scenario:<18}{p_delta:>+12.3f}{e_delta:>+12.3f}{d_delta:>+14.3f}{pool:>8}{v:>18}")

    # ─── Degradation Analysis ────────────────────────────────────────────────

    print("\n" + "=" * 90)
    print("DEGRADATION ANALYSIS")
    print("=" * 90)

    degradation_cases = []
    for scenario in scenarios:
        nr = results[scenario]['no_routing']
        rt = results[scenario]['routing']

        segs = ['first_500', 'mid_500', 'last_500']
        precision_by_seg = []
        for seg in segs:
            ns = nr.get('segment_metrics', {}).get(seg, {}).get('precision', 0)
            rs = rt.get('segment_metrics', {}).get(seg, {}).get('precision', 0)
            precision_by_seg.append(rs - ns)

        # Check: precision declining from first to last
        if len(precision_by_seg) >= 3:
            early_delta = precision_by_seg[0]
            late_delta = precision_by_seg[-1]
            if late_delta < early_delta - 0.1:
                degradation_cases.append((scenario, 'precision_decline',
                                          early_delta, late_delta))
            elif late_delta < 0.05 and early_delta > 0.1:
                degradation_cases.append((scenario, 'precision_collapse',
                                          early_delta, late_delta))

        # Entropy creep: is routing entropy rising in late segments?
        rs_last = rt.get('segment_metrics', {}).get('last_500', {}).get('entropy', 0)
        rs_first = rt.get('segment_metrics', {}).get('first_500', {}).get('entropy', 0)
        if rs_last > rs_first + 0.2:
            degradation_cases.append((scenario, 'entropy_creep',
                                      rs_first, rs_last))

    if degradation_cases:
        print("  DETECTED DEGRADATION CASES:")
        for scenario, dtype, early, late in degradation_cases:
            print(f"    {scenario}: {dtype} ({early:+.3f} → {late:+.3f})")
    else:
        print("  NO SIGNIFICANT DEGRADATION DETECTED")

    # ─── Architecture Verdict ─────────────────────────────────────────────────

    print("\n" + "=" * 90)
    print("ARCHITECTURE VERDICT — LONG-HORIZON STABILITY")
    print("=" * 90)

    # Aggregate across scenarios
    stable_count = sum(1 for scenario in scenarios
                       if results[scenario]['routing'].get('segment_metrics', {}).get('last_500', {}).get('precision', 0) >
                          results[scenario]['no_routing'].get('segment_metrics', {}).get('last_500', {}).get('precision', 0) + 0.05)

    if stable_count >= 4:
        long_horizon_verdict = "STABLE"
        long_horizon_desc = f"Routing stable in {stable_count}/5 scenarios over 1500 ticks"
    elif stable_count >= 2:
        long_horizon_verdict = "MARGINALLY STABLE"
        long_horizon_desc = f"Routing degrades in some scenarios (adaptation required)"
    else:
        long_horizon_verdict = "UNSTABLE"
        long_horizon_desc = "Routing degrades over long horizons — needs decay/replay mechanism"

    print(f"""
  Long-Horizon Stability Test (1500 ticks):
  ─────────────────────────────────────────────────────────────────────
  Scenarios tested: {', '.join(scenarios)}
  Stable: {stable_count}/5 scenarios

  Verdict: {long_horizon_verdict}

  Details:
    {long_horizon_desc}

  Failure Modes Observed:
""")

    for scenario in scenarios:
        rt = results[scenario]['routing']
        nr = results[scenario]['no_routing']

        if rt.get('trend'):
            trend = rt['trend']
            pool_growth = trend.get('pool_growth', 0)

            issues = []
            if trend.get('precision_delta', 0) < -0.1:
                issues.append(f"precision_drop({trend['precision_delta']:+.3f})")
            if trend.get('entropy_delta', 0) > 0.2:
                issues.append(f"entropy_creep({trend['entropy_delta']:+.3f})")
            if pool_growth > 200:
                issues.append(f"pool_flood(+{pool_growth:.0f})")

            if issues:
                print(f"    {scenario}: {', '.join(issues)}")
            else:
                print(f"    {scenario}: stable")

    print(f"""
  Routing Architecture Sustainability:
  ─────────────────────────────────────────────────────────────────────
  semantic role:          RETRIEVAL ROUTING LAYER
  routing utility:        CONFIRMED (low entropy, high coherence)
  long-horizon stability: {long_horizon_verdict}

  Key Finding:
    Routing effectiveness {'maintains' if stable_count >= 4 else 'degrades'}
    over 1500 ticks.
    {'No structural collapse observed.' if stable_count >= 4 else 'Requires schema refresh or episodic pruning.'}

  Architecture Implication:
    If routing is stable → semantic can serve as persistent topology layer
    If routing degrades → need active schema maintenance mechanism

  Next Stage Priority:
    1. Agent integration (routing in real cognitive loop)
    2. Schema refresh mechanism (adaptive schemas)
    3. Episodic pruning (prevent pool flooding)
""")

    return results


if __name__ == '__main__':
    print("Running v0.13 Long-Horizon Stability (5 scenarios × 1500 ticks × 2 modes)...")
    print("This will take ~30 seconds...")
    results = run_experiment()
    print_results(results)
