#!/usr/bin/env python3
"""v0.16 - Lesion Experiments + Closed-Loop Cognitive Integration"""
import random, math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
random.seed(42)

@dataclass
class Memory:
    id: str
    content: str
    topic_tag: str
    layer: str = 'episodic'
    access_count: int = 0
    last_access: int = 0
    importance: float = 0.5
    created: int = 0
    activation: float = 0.0
    routing_boost: float = 0.0
    novelty_score: float = 0.0
    def score(self, tick: int, recency_weight: float = 0.2, routing_dominance: bool = True) -> float:
        recency = 1.0 / (1.0 + (tick - self.last_access) * 0.01)
        access = self.access_count / (1.0 + self.access_count)
        base = recency * recency_weight + access * 0.3 + self.importance * 0.3
        novelty = self.novelty_score * 0.1
        if routing_dominance:
            return base + self.routing_boost * 2.0 + novelty
        return base + self.routing_boost + novelty

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
    protected_until: int = 0
    deleted: bool = False
    def age(self, current_tick: int) -> int:
        return current_tick - self.created_at
    def is_stable(self, current_tick: int) -> bool:
        return current_tick < self.protected_until
    def is_active(self, current_tick: int) -> bool:
        return (current_tick - self.last_activation) < 80
    def score(self, query_words: Set[str]) -> float:
        if self.deleted: return 0.0
        overlap = len(self.keywords & query_words)
        return overlap * self.decay * (1.0 if self.decay > 0.05 else 0.0)

@dataclass
class Goal:
    id: str
    content: str
    schema_tag: str
    activation: float = 0.5
    persistence: int = 0
    completed: bool = False

class CognitiveSystem:
    SPREAD_BOOST = 0.9
    ROUTING_DECAY = 0.3
    WORKING_MEMORY = 12
    RECENCY_WEIGHT = 0.2
    ROUTING_DOMINANCE = True
    STABILITY_WINDOW = 150
    SCHEMA_DECAY_RATE = 0.0005
    FORGET_THRESHOLD = 0.05
    REFRESH_OVERLAP = 0.3
    MAX_SCHEMAS = 12
    STALENESS_WINDOW = 80

    def __init__(self, mode: str = 'full', lesion_type: Optional[str] = None):
        self.mode = mode
        self.lesion_type = lesion_type
        self.working = []
        self.episodic = []
        self.schemas = []
        self.goals = []
        self.tick = 0
        self.attention_focus = None
        self.exploration_pressure = 0.0
        self.active_goal = None
        self.retrieval_log = []
        self.adaptation_log = []
        self.behavior_log = []
        self.lesion_effects = []
        self.schema_lifetimes = []
        self.recent_topics = []
        self.routing_authority = defaultdict(float)

    def _init_schemas(self):
        base = [
            ('project_schema',  {'project', 'planning', 'task', 'goal', 'milestone'}, 'project'),
            ('debug_schema',   {'debug', 'error', 'fix', 'log', 'trace', 'issue'}, 'debug'),
            ('meeting_schema', {'meeting', 'discussion', 'participants', 'agenda'}, 'meeting'),
            ('coding_schema',  {'code', 'implementation', 'function', 'class'}, 'coding'),
            ('review_schema',  {'review', 'feedback', 'changes', 'revision'}, 'review'),
        ]
        for sid, keywords, topic in base:
            s = Schema(id=f'sem_{sid}', keywords=keywords, topic_tag=topic,
                      created_at=0, last_activation=0, activation_count=0,
                      decay=1.0, activation_strength=0.0,
                      protected_until=self.STABILITY_WINDOW)
            if self.lesion_type == 'shuffle_routing':
                other = [t for _, _, t in base if t != topic]
                s.topic_tag = random.choice(other)
                s.topic_history.append(f'LESION_shuffled_from_{topic}')
            self.schemas.append(s)

    def _lesion_delete_hubs(self):
        if not self.schemas: return []
        by_act = sorted(self.schemas, key=lambda s: -s.activation_count)[:2]
        for s in by_act: s.deleted = True
        return [s.id for s in by_act]

    def _lesion_shuffle_routing(self):
        topics = [s.topic_tag for s in self.schemas if not s.deleted]
        active = [s for s in self.schemas if not s.deleted and s.is_active(self.tick)]
        if not active: return []
        random.shuffle(topics)
        for i, s in enumerate(active):
            if i < len(topics):
                old = s.topic_tag
                s.topic_tag = topics[i]
                s.topic_history.append(f'LESION_shuffled_{old}_>{topics[i]}')
        return [s.id for s in active]

    def _lesion_randomize_priors(self):
        for s in self.schemas:
            if s.deleted: continue
            all_kw = set()
            for sch in self.schemas: all_kw |= sch.keywords
            shuffled = list(all_kw)
            random.shuffle(shuffled)
            per = max(1, len(shuffled) // max(len(self.schemas), 1))
            s.keywords = set(shuffled[:per])

    def store(self, content: str, topic_tag: str):
        novelty = 1.0 if topic_tag not in self.recent_topics[-5:] else 0.0
        self.working.append(Memory(
            id=f'mem_{self.tick}_{random.randint(1000,9999)}',
            content=content, topic_tag=topic_tag, layer='working',
            importance=0.5, created=self.tick, access_count=1,
            last_access=self.tick, activation=1.0, routing_boost=0.0,
            novelty_score=novelty))
        self.recent_topics.append(topic_tag)
        if len(self.recent_topics) > 10: self.recent_topics.pop(0)

    def evict_working(self):
        while len(self.working) > self.WORKING_MEMORY:
            m = self.working.pop(0)
            m.layer = 'episodic'
            self.episodic.append(m)

    def _route(self, query: str, t: int) -> Dict[str, float]:
        q_words = set(query.lower().split())
        activations = defaultdict(float)
        for schema in self.schemas:
            if schema.deleted: continue
            score = random.random() * 0.1 if self.lesion_type == 'randomize_priors' else schema.score(q_words)
            if score > 0:
                schema.last_activation = t
                schema.activation_count += 1
                schema.activation_strength = min(1.0, score * 0.3)
                activations[schema.topic_tag] = max(activations[schema.topic_tag], schema.activation_strength)
                self.routing_authority[schema.id] += schema.activation_strength
        return activations

    def _spread(self, activations: Dict[str, float], t: int):
        for m in self.episodic:
            if m.topic_tag in activations:
                strength = activations[m.topic_tag]
                m.routing_boost = max(m.routing_boost, strength * self.SPREAD_BOOST)
                m.activation = max(m.activation, strength * 0.4)
                m.last_access = t

    def _apply_lesion(self, tick: int):
        if self.lesion_type == 'delete_hubs' and tick == 520:
            d = self._lesion_delete_hubs()
            self.lesion_effects.append({'tick': tick, 'type': 'delete_hubs', 'deleted': d})
        elif self.lesion_type == 'shuffle_routing' and tick == 520:
            s = self._lesion_shuffle_routing()
            self.lesion_effects.append({'tick': tick, 'type': 'shuffle_routing', 'shuffled': s})
        elif self.lesion_type == 'randomize_priors' and tick == 0:
            self._lesion_randomize_priors()
            self.lesion_effects.append({'tick': 0, 'type': 'randomize_priors', 'shuffled': 'all'})

    def _attention_router(self, activations: Dict[str, float], topic_tag: str) -> str:
        if not activations: return topic_tag
        target = max(activations, key=lambda k: activations[k])
        if self.exploration_pressure > 0.5 and random.random() < self.exploration_pressure * 0.3:
            all_t = ['project', 'debug', 'meeting', 'coding', 'review']
            novel = [t for t in all_t if t not in activations]
            if novel: target = random.choice(novel)
        self.attention_focus = target
        return target

    def _goal_router(self, topic_tag: str) -> Optional[Goal]:
        if self.active_goal and not self.active_goal.completed:
            if self.active_goal.persistence > 50:
                match = any(s.topic_tag == self.active_goal.schema_tag for s in self.schemas if not s.deleted)
                if not match: self.active_goal.completed = True
            self.active_goal.persistence += 1
            return self.active_goal
        match = next((s for s in self.schemas if not s.deleted and s.topic_tag == topic_tag), None)
        if match:
            g = Goal(id=f'goal_{self.tick}', content=f'Pursue {topic_tag}', schema_tag=topic_tag,
                      activation=0.8, persistence=0)
            self.active_goal = g
            return g
        return None

    def _update_exploration_pressure(self, topic_tag: str):
        recent = [g.schema_tag for g in self.goals[-20:] if hasattr(g, 'schema_tag')]
        if len(set(recent)) <= 2 and len(recent) >= 10:
            self.exploration_pressure = min(1.0, self.exploration_pressure + 0.05)
        else:
            self.exploration_pressure = max(0.0, self.exploration_pressure - 0.01)
        if topic_tag not in self.recent_topics[-10:]:
            self.exploration_pressure = max(0.0, self.exploration_pressure - 0.1)

    def _contextual_suppression(self, topic_tag: str):
        for s in self.schemas:
            if s.deleted: continue
            if s.topic_tag != topic_tag and s.activation_strength > 0:
                s.activation_strength *= 0.7
                s.last_activation = min(s.last_activation, self.tick - 30)

    def _best_schema_for_topic(self, topic_tag: str):
        best, best_ov = None, 0.0
        for s in self.schemas:
            if s.deleted: continue
            ov = len(s.keywords & {topic_tag}) / max(len(s.keywords), 1)
            if ov > best_ov: best_ov, best = ov, s
        return best, best_ov

    def _reassign_orphaned_schemas(self, current_topic: str, events: List[str]):
        if self.mode == 'no_adaptation': return
        t = self.tick
        for s in self.schemas:
            if s.deleted or s.is_stable(t): continue
            stale = t - s.last_activation
            if stale <= self.STALENESS_WINDOW or s.decay < self.FORGET_THRESHOLD: continue
            covered = any(x.topic_tag == current_topic and (t - x.last_activation) < self.STALENESS_WINDOW for x in self.schemas if not x.deleted and x != s)
            if covered: continue
            old = s.topic_tag
            s.topic_tag = current_topic
            s.topic_history.append(f'REASSIGN_from_{old}')
            s.keywords = s.keywords | {current_topic}
            s.decay = min(1.0, s.decay + 0.3)
            s.refresh_count += 1
            s.last_activation = t
            events.append(f'REASSIGN {s.id.split("_")[1]}: {old}->{current_topic}')

    def _schema_decay(self):
        rate = self.SCHEMA_DECAY_RATE if self.mode == 'full' else 0.005
        for s in self.schemas:
            if s.deleted: continue
            if self.tick - s.last_activation > 50:
                s.decay = max(0.0, s.decay - rate)

    def _forget_dead_schemas(self, events: List[str]):
        remove = [s for s in self.schemas if not s.deleted and s.decay < self.FORGET_THRESHOLD and not s.is_stable(self.tick)]
        for s in remove:
            events.append(f'FORGET {s.id.split("_")[1]}')
            self.schemas.remove(s)
            self.schema_lifetimes.append(s.age(self.tick))

    def _adapt(self, query: str, topic_tag: str, activated_schemas: List[Schema], routed_episodic: List[Memory]):
        if self.mode == 'no_adaptation': return
        events = []
        t = self.tick
        self._reassign_orphaned_schemas(topic_tag, events)
        for schema in activated_schemas:
            mismatched = [m for m in routed_episodic if m.routing_boost > 0 and m.topic_tag != schema.topic_tag]
            if not mismatched: continue
            cnt = defaultdict(int)
            for m in mismatched: cnt[m.topic_tag] += 1
            dominant = max(cnt, key=lambda tt: cnt[tt])
            cand, ov = self._best_schema_for_topic(dominant)
            if ov >= self.REFRESH_OVERLAP and cand:
                old = cand.topic_tag
                cand.topic_tag = dominant
                cand.topic_history.append(dominant)
                nk = set()
                for m in mismatched[:5]: nk.update(m.content.lower().split())
                cand.keywords = cand.keywords | nk
                cand.decay = min(1.0, cand.decay + 0.15)
                cand.refresh_count += 1
                cand.last_activation = t
                events.append(f'REFRESH {cand.id.split("_")[1]}: {old}->{dominant}')
            elif self.mode == 'full' and len(self.schemas) < self.MAX_SCHEMAS:
                kw = set()
                for m in mismatched[:10]: kw.update(m.content.lower().split())
                self.schemas.append(Schema(id=f'sem_{dominant}_{t}', keywords=kw, topic_tag=dominant,
                          created_at=t, last_activation=t, activation_count=1,
                          decay=0.8, activation_strength=0.5, protected_until=t + self.STABILITY_WINDOW))
                events.append(f'FORM {dominant}')
        if self.mode in ('full', 'partial'): self._schema_decay()
        if self.mode == 'full': self._forget_dead_schemas(events)
        if events: self.adaptation_log.append({'tick': t, 'events': events, 'schema_count': sum(1 for s in self.schemas if not s.deleted)})

    def retrieve(self, query: str, topic_tag: str, top_k: int = 5) -> List[Memory]:
        self.tick += 1
        t = self.tick
        self._apply_lesion(t)
        activations = self._route(query, t)
        activated = [s for s in self.schemas if not s.deleted and s.activation_strength > 0]
        attn = self._attention_router(activations, topic_tag)
        self._contextual_suppression(topic_tag)
        self._spread(activations, t)
        routed = [m for m in self.episodic if m.routing_boost > 0]
        goal = self._goal_router(topic_tag)
        if goal: self.goals.append(goal)
        self._update_exploration_pressure(topic_tag)
        self._adapt(query, topic_tag, activated, routed)
        candidates = self.working + self.episodic
        scored = [(m.score(t, recency_weight=self.RECENCY_WEIGHT, routing_dominance=self.ROUTING_DOMINANCE), m) for m in candidates]
        scored.sort(key=lambda x: -x[0])
        results = [m for _, m in scored[:top_k]]
        for m in results: m.access_count += 1; m.last_access = t
        for m in self.episodic: m.routing_boost *= self.ROUTING_DECAY
        correct = sum(1 for m in results if m.topic_tag == topic_tag)
        precision = correct / max(len(results), 1)
        tc = defaultdict(int)
        for m in results: tc[m.topic_tag] += 1
        total = len(results)
        entropy = -sum((c/total)*math.log2(c/total) for c in tc.values() if c > 0)
        novelty_in_results = sum(m.novelty_score for m in results) / max(len(results), 1)
        self.retrieval_log.append({
            'tick': t, 'query': query[:30], 'topic_tag': topic_tag,
            'attention_focus': self.attention_focus,
            'result_topics': [m.topic_tag for m in results],
            'precision': precision, 'entropy': entropy,
            'schema_count': sum(1 for s in self.schemas if not s.deleted),
            'activations': len(activations),
            'active_schema_topics': [s.topic_tag for s in activated],
            'exploration_pressure': self.exploration_pressure,
            'goal_schema': goal.schema_tag if goal else None,
            'routing_authority': dict(self.routing_authority),
            'novelty_in_results': novelty_in_results,
        })
        self.behavior_log.append({
            'tick': t, 'attention': self.attention_focus,
            'goal': goal.content if goal else None,
            'goal_schema': goal.schema_tag if goal else None,
            'exploration': self.exploration_pressure,
            'schemas_active': [s.topic_tag for s in activated],
            'result_diversity': len(tc),
        })
        return results

    def run(self, scenario: str, ticks: int = 1500) -> Dict:
        if scenario == 'topic_phases':
            def get(i):
                if i < 500: return 'project', f'project planning task {i} milestone'
                elif i < 1000: return 'debug', f'debugging error issue {i} trace'
                else: return 'meeting', f'meeting discussion {i} agenda'
        elif scenario == 'gradual_drift':
            def get(i):
                alpha = 0.9 if i < 500 else (0.7 if i < 800 else (0.4 if i < 1100 else 0.2))
                return ('project' if random.random() < alpha else 'debug', f'task {i}')
        elif scenario == 'catastrophic':
            def get(i): return ('project' if i < 750 else 'debug', f'task {i}')
        elif scenario == 'mixed_burst':
            def get(i):
                topics = ['project', 'debug', 'coding', 'review']
                return topics[(i % 200) // 50], f'task {i}'
        else:
            def get(i): return 'project', f'task {i}'
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
        if not seg: return {}
        return {
            'precision': sum(e['precision'] for e in seg) / len(seg),
            'entropy': sum(e['entropy'] for e in seg) / len(seg),
            'novelty': sum(e['novelty_in_results'] for e in seg) / len(seg),
            'exploration': sum(e['exploration_pressure'] for e in seg) / len(seg),
            'schema_count': sum(e['schema_count'] for e in seg) / len(seg),
        }

    def _build_report(self, scenario: str, ticks: int) -> Dict:
        segs = {'first_500': self._seg(0, 500), 'mid_500': self._seg(500, 1000), 'last_500': self._seg(1000, 1500)}
        formed_e = [e for log in self.adaptation_log for ev in log['events'] for e in [ev] if 'FORM' in e]
        refresh_e = [e for log in self.adaptation_log for ev in log['events'] for e in [ev] if 'REFRESH' in e]
        reassign_e = [e for log in self.adaptation_log for ev in log['events'] for e in [ev] if 'REASSIGN' in e]
        churn_rate = len(formed_e) / (ticks / 100)
        recovery = None
        if scenario in ('topic_phases', 'catastrophic'):
            phase2 = 500 if scenario == 'topic_phases' else 750
            post = self.retrieval_log[phase2:phase2+200]
            for i, entry in enumerate(post):
                if entry['precision'] > 0.6: recovery = i; break
        goal_schemas = [e['goal_schema'] for e in self.retrieval_log if e['goal_schema']]
        goal_div = len(set(goal_schemas)) / max(len(goal_schemas), 1)
        return {
            'scenario': scenario, 'mode': self.mode, 'lesion_type': self.lesion_type, 'ticks': ticks,
            'segment_metrics': segs,
            'adaptation_summary': {
                'refresh': len(refresh_e), 'reassign': len(reassign_e), 'formed': len(formed_e),
                'final_schema_count': sum(1 for s in self.schemas if not s.deleted),
                'churn_rate_per_100ticks': churn_rate, 'recovery_ticks': recovery, 'goal_diversity': goal_div,
            },
            'behavioral_metrics': {
                'avg_exploration': sum(e['exploration_pressure'] for e in self.retrieval_log) / len(self.retrieval_log),
                'attention_stability': 1.0 - (sum(1 for e in self.retrieval_log if e['attention_focus'] != e['topic_tag']) / len(self.retrieval_log)),
                'novelty_in_results': sum(e['novelty_in_results'] for e in self.retrieval_log) / len(self.retrieval_log),
                'goal_diversity': goal_div,
            },
            'lesion_effects': self.lesion_effects,
            'final_schemas': [(s.id.split('_')[1], round(s.decay, 3), s.topic_tag, s.age(ticks), s.activation_count) for s in self.schemas if not s.deleted],
        }


def run_lesion_experiment():
    print('\n' + '='*70)
    print('PHASE 1: LESION EXPERIMENTS (topic_phases)')
    print('='*70)
    baseline = CognitiveSystem(mode='full', lesion_type=None)
    baseline.run('topic_phases', ticks=1500)
    experiments = [
        ('L1_delete_hubs', 'full', 'delete_hubs'),
        ('L2_shuffle_routing', 'full', 'shuffle_routing'),
        ('L3_random_priors', 'full', 'randomize_priors'),
        ('L4_episodic_only', 'full', None),
    ]
    results = {'baseline': baseline._build_report('topic_phases', 1500)}
    header = f"{'Experiment':<22}{'first':>8}{'mid':>8}{'last':>8}{'churn':>8}{'recover':>10}{'goal_div':>10}"
    print(f"\n{header}")
    print('-'*70)
    for label, mode, lesion in experiments:
        sys = CognitiveSystem(mode=mode, lesion_type=lesion)
        if label == 'L4_episodic_only': sys.schemas = []
        report = sys.run('topic_phases', ticks=1500)
        results[label] = report
        segs = report['segment_metrics']
        fp = segs.get('first_500', {}).get('precision', 0.0)
        mp = segs.get('mid_500', {}).get('precision', 0.0)
        lp = segs.get('last_500', {}).get('precision', 0.0)
        churn = report['adaptation_summary']['churn_rate_per_100ticks']
        rec = report['adaptation_summary']['recovery_ticks'] or 'N/A'
        gd = report['behavioral_metrics']['goal_diversity']
        print(f"{label:<22}{fp:>8.3f}{mp:>8.3f}{lp:>8.3f}{churn:>8.2f}{str(rec):>10}{gd:>10.3f}")
    b = results['baseline']
    segs = b['segment_metrics']
    bl = f"{'baseline':<22}{segs.get('first_500',{}).get('precision',0):>8.3f}{segs.get('mid_500',{}).get('precision',0):>8.3f}{segs.get('last_500',{}).get('precision',0):>8.3f}{b['adaptation_summary']['churn_rate_per_100ticks']:>8.2f}{str(b['adaptation_summary']['recovery_ticks'] or 'N/A'):>10}{b['behavioral_metrics']['goal_diversity']:>10.3f}"
    print(bl)
    return results


def run_closed_loop_experiment():
    print('\n\n' + '='*70)
    print('PHASE 2: CLOSED-LOOP COGNITIVE INTEGRATION')
    print('='*70)
    scenarios = ['topic_phases', 'gradual_drift', 'catastrophic', 'mixed_burst']
    header = f"{'Scenario':<16}{'Mode':<12}{'first':>8}{'mid':>8}{'last':>8}{'expl':>8}{'novelty':>8}{'goal_div':>10}"
    print(f"\n{header}")
    print('-'*70)
    results = {}
    for scenario in scenarios:
        for mode in ['full', 'partial', 'no_adaptation']:
            sys = CognitiveSystem(mode=mode)
            report = sys.run(scenario, ticks=1500)
            key = f'{scenario}/{mode}'
            results[key] = report
            segs = report['segment_metrics']
            bm = report['behavioral_metrics']
            row = f"{scenario:<16}{mode:<12}{segs.get('first_500',{}).get('precision',0):>8.3f}{segs.get('mid_500',{}).get('precision',0):>8.3f}{segs.get('last_500',{}).get('precision',0):>8.3f}{bm['avg_exploration']:>8.3f}{bm['novelty_in_results']:>8.3f}{bm['goal_diversity']:>10.3f}"
            print(row)
    return results


def compute_elasticity(all_results):
    print('\n\n' + '='*70)
    print('BEHAVIORAL ROUTING ELASTICITY')
    print('='*70)
    elasticities = {}
    for key, report in all_results.items():
        bm = report.get('behavioral_metrics', {})
        novelty = bm.get('novelty_in_results', 0)
        exploration = bm.get('avg_exploration', 0)
        fixation = 1.0 - bm.get('goal_diversity', 0)
        E = novelty / max(fixation, 0.01)
        elasticities[key] = {'E': E, 'novelty': novelty, 'exploration': exploration, 'fixation': fixation}
    header = f"{'Experiment':<30}{'E':>8}{'Novelty':>10}{'Exploration':>12}{'Fixation':>10}"
    print(f"\n{header}")
    print('-'*70)
    for key, vals in sorted(elasticities.items(), key=lambda x: -x[1]['E']):
        row = f"{key:<30}{vals['E']:>8.3f}{vals['novelty']:>10.3f}{vals['exploration']:>12.3f}{vals['fixation']:>10.3f}"
        print(row)
    return elasticities


if __name__ == '__main__':
    print('v0.16 - Lesion Experiments + Closed-Loop Cognitive Integration')
    print('='*70)
    lesion_results = run_lesion_experiment()
    closed_loop_results = run_closed_loop_experiment()
    all_results = {'baseline': lesion_results['baseline'], **{k: v for k, v in lesion_results.items() if k != 'baseline'}, **closed_loop_results}
    elasticities = compute_elasticity(all_results)
    print('\n\n' + '='*70)
    print('ARCHITECTURE VERDICT - v0.16')
    print('='*70)
    b_prec = lesion_results['baseline']['segment_metrics']['mid_500']['precision']
    l1 = lesion_results.get('L1_delete_hubs', {}).get('segment_metrics', {}).get('mid_500', {}).get('precision', 0)
    l2 = lesion_results.get('L2_shuffle_routing', {}).get('segment_metrics', {}).get('mid_500', {}).get('precision', 0)
    l3 = lesion_results.get('L3_random_priors', {}).get('segment_metrics', {}).get('mid_500', {}).get('precision', 0)
    l4 = lesion_results.get('L4_episodic_only', {}).get('segment_metrics', {}).get('mid_500', {}).get('precision', 0)
    causal = 'SEMANTIC IS CAUSAL' if l4 < b_prec - 0.3 else 'PARTIAL CAUSALITY' if l4 < b_prec else 'EPIPHENOMENAL'
    print(f"""
  LESION RESULTS (topic_phases mid_500):
    Baseline:                    {b_prec:.3f}
    L1 delete_hubs:            {l1:.3f}  ({l1-b_prec:+.3f})
    L2 shuffle_routing:        {l2:.3f}  ({l2-b_prec:+.3f})
    L3 random_priors:          {l3:.3f}  ({l3-b_prec:+.3f})
    L4 episodic_only:          {l4:.3f}  ({l4-b_prec:+.3f})

  CAUSALITY TEST: {causal}
  Hubs causal: {'YES' if l1 < b_prec - 0.3 else 'NO - distributed routing'}
  Routing optimized: {'YES' if l3 < b_prec - 0.2 else 'NO - routing is robust'}
""")
