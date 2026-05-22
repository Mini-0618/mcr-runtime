#!/usr/bin/env python3
"""
v0.17 — Semantic Necessity Benchmark

RESEARCH QUESTION:
  Does semantic provide capabilities that episodic CANNOT independently achieve?

  v0.16 proved: semantic utility EXISTS (L2/L3 lesions degrade)
                 semantic necessity NOT PROVEN (L4 = baseline)

  v0.17 GOAL:
    Design tasks where episodic-only MUST FAIL
    and semantic-layer MUST SUCCEED

FOUR BENCHMARK TASKS:

  Task A: Multi-topic Interference
    - Rapid topic switching
    - But global goal requires stable long-term routing
    - Episodic: topic oscillation, context pollution
    - Semantic: global routing stability

  Task B: Long-Horizon Conflict
    - Early important signal embedded in large episodic pool
    - Massive recent distractor injection
    - Episodic: recency dominance, signal淹没
    - Semantic: long-range invariant activation

  Task C: Cross-Episode Abstraction
    - Same underlying structure, completely different surface forms
    - Phase 1: "roadmap planning milestone"
    - Phase 2: "deployment sequencing release"
    - Phase 3: "execution dependency graph"
    - Episodic: surface mismatch, activation failure
    - Semantic: invariant structure routing

  Task D: Distractor Injection
    - 1% signal episodic, 99% distractor episodic
    - Signal has distinctive structural pattern
    - Episodic: distractor dominance
    - Semantic: structure recognition, signal preservation

EXPERIMENTS:
  1. episodic-only (schemas=[])
  2. semantic-routing (full semantic, no adaptation)
  3. semantic-adaptive (full system)
  4. lesion: semantic-shuffle (破坏semantic一致性)

KEY METRICS:
  - signal_recall: did system retrieve the critical signal?
  - precision: retrieval accuracy
  - entropy: retrieval coherence
  - oscillation: topic switching confusion
  - invariant_recall: cross-surface structure retrieval

VERDICT CRITERIA:
  semantic necessity PROVEN if:
    - semantic-adaptive >> episodic-only on Tasks A,B,C,D
    - at least 2 tasks show significant divergence
"""

import random
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
random.seed(42)

# ═══════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════

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
    is_signal: bool = False  # Task B/C/D: this is the critical signal
    structure_pattern: str = ''  # Task D: structural signature

    def score(self, tick: int, recency_weight: float = 0.2, routing_dominance: bool = True) -> float:
        recency = 1.0 / (1.0 + (tick - self.last_access) * 0.01)
        access = self.access_count / (1.0 + self.access_count)
        base = recency * recency_weight + access * 0.3 + self.importance * 0.3
        novelty = self.novelty_score * 0.1
        signal_bonus = 0.5 if self.is_signal else 0.0
        if routing_dominance:
            return base + self.routing_boost * 2.0 + novelty + signal_bonus
        return base + self.routing_boost + novelty + signal_bonus


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
    # Cross-episode invariant tracking
    abstract_structure: str = ''  # abstract category this schema represents

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


# ═══════════════════════════════════════════════════════════════════
# COGNITIVE SYSTEM
# ═══════════════════════════════════════════════════════════════════

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
        self.recent_topics = []
        self.routing_authority = defaultdict(float)
        # Task-specific metrics
        self.signal_retrievals = []  # did we retrieve the critical signal?
        self.oscillation_count = 0
        self.last_retrieved_topics = []
        self.signal_memories = []  # references to signal memories

    def _init_schemas(self):
        base = [
            ('project_schema',  {'project', 'planning', 'milestone', 'roadmap', 'goal', 'deployment', 'sequencing', 'release', 'execution', 'dependency', 'graph'}, 'project'),
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
            self.schemas.append(s)

    def store(self, content: str, topic_tag: str, is_signal: bool = False, pattern: str = ''):
        novelty = 1.0 if topic_tag not in self.recent_topics[-5:] else 0.0
        m = Memory(
            id=f'mem_{self.tick}_{random.randint(1000,9999)}',
            content=content, topic_tag=topic_tag, layer='working',
            importance=0.5, created=self.tick, access_count=1,
            last_access=self.tick, activation=1.0, routing_boost=0.0,
            novelty_score=novelty, is_signal=is_signal, structure_pattern=pattern)
        self.working.append(m)
        if is_signal:
            self.signal_memories.append(m)
        self.recent_topics.append(topic_tag)
        if len(self.recent_topics) > 10:
            self.recent_topics.pop(0)

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
            if self.lesion_type == 'randomize_priors':
                score = random.random() * 0.1
            else:
                score = schema.score(q_words)
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

    def _attention_router(self, activations: Dict[str, float], topic_tag: str) -> str:
        if not activations: return topic_tag
        return max(activations, key=lambda k: activations[k])

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
        activations = self._route(query, t)
        activated = [s for s in self.schemas if not s.deleted and s.activation_strength > 0]
        attn = self._attention_router(activations, topic_tag)
        self._contextual_suppression(topic_tag)
        self._spread(activations, t)
        routed = [m for m in self.episodic if m.routing_boost > 0]
        goal = self._goal_router(topic_tag)
        if goal: self.goals.append(goal)
        self._adapt(query, topic_tag, activated, routed)
        candidates = self.working + self.episodic
        scored = [(m.score(t, recency_weight=self.RECENCY_WEIGHT, routing_dominance=self.ROUTING_DOMINANCE), m) for m in candidates]
        scored.sort(key=lambda x: -x[0])
        results = [m for _, m in scored[:top_k]]
        for m in results:
            m.access_count += 1
            m.last_access = t
        for m in self.episodic:
            m.routing_boost *= self.ROUTING_DECAY
        correct = sum(1 for m in results if m.topic_tag == topic_tag)
        precision = correct / max(len(results), 1)
        tc = defaultdict(int)
        for m in results:
            tc[m.topic_tag] += 1
        total = len(results)
        entropy = -sum((c/total)*math.log2(c/total) for c in tc.values() if c > 0) if total > 0 else 0.0

        # Signal retrieval tracking (Tasks B, C, D)
        signal_retrieved = any(m.is_signal for m in results)
        self.signal_retrievals.append(1 if signal_retrieved else 0)

        # Oscillation tracking (Task A)
        retrieved_topics = [m.topic_tag for m in results]
        if len(self.last_retrieved_topics) > 0:
            if retrieved_topics[0] != self.last_retrieved_topics[0]:
                self.oscillation_count += 1
        self.last_retrieved_topics = retrieved_topics

        self.retrieval_log.append({
            'tick': t, 'query': query[:30], 'topic_tag': topic_tag,
            'attention_focus': self.attention_focus,
            'result_topics': retrieved_topics,
            'precision': precision, 'entropy': entropy,
            'schema_count': sum(1 for s in self.schemas if not s.deleted),
            'activations': len(activations),
            'signal_retrieved': signal_retrieved,
            'goal_schema': goal.schema_tag if goal else None,
        })
        return results

    def _seg(self, start: int, end: int) -> Dict:
        seg = self.retrieval_log[start:end]
        if not seg: return {}
        return {
            'precision': sum(e['precision'] for e in seg) / len(seg),
            'entropy': sum(e['entropy'] for e in seg) / len(seg),
            'signal_recall': sum(e['signal_retrieved'] for e in seg) / len(seg),
        }

    def _build_report(self, scenario: str, ticks: int) -> Dict:
        seg1 = self._seg(0, 500)
        seg2 = self._seg(500, 1000)
        seg3 = self._seg(1000, 1500) if ticks >= 1500 else {}
        signal_recall = sum(self.signal_retrievals) / max(len(self.signal_retrievals), 1)
        formed = [e for log in self.adaptation_log for ev in log['events'] for e in [ev] if 'FORM' in e]
        return {
            'scenario': scenario,
            'segment_metrics': {'first': seg1, 'second': seg2, 'third': seg3},
            'signal_recall': signal_recall,
            'oscillation_rate': self.oscillation_count / max(ticks, 1),
            'adaptation': {'formed': len(formed), 'final_schema_count': sum(1 for s in self.schemas if not s.deleted)},
            'final_schemas': [(s.id.split('_')[1], round(s.decay, 3), s.topic_tag) for s in self.schemas if not s.deleted],
        }


# ═══════════════════════════════════════════════════════════════════
# TASK GENERATORS
# ═══════════════════════════════════════════════════════════════════

def make_task_a():
    """
    Task A: Multi-topic Interference

    Design:
      - Global goal: "project" planning
      - Topic switches every 10 ticks (4 topics)
      - Only "project" topic has content relevant to global goal
      - Other topics have irrelevant content
      - Query: "project planning" (the global goal)

    Episodic prediction:
      - Will oscillate: retrieves from current topic (debug/meeting/coding)
      - Topic switching causes context pollution
      - Global goal precision will be low

    Semantic prediction:
      - project_schema stays active across topic switches
      - Routes to project content even when topic is not "project"
      - Stable global goal precision
    """
    def get(i):
        # Rapid topic switching
        topics = ['project', 'debug', 'meeting', 'coding']
        topic = topics[i % 40 // 10]  # switch every 10 ticks

        if topic == 'project':
            # Global goal content - should be retrieved via semantic routing
            content = 'project planning milestone roadmap objective'
        elif i % 5 == 0:
            # Occasionally inject project keywords in other topics
            content = f'{topic} discussion project planning {i}'
        else:
            # Pure distractor content
            content = f'{topic} discussion {i}'

        return topic, content

    def query_fn(i):
        # Always query for project - the global goal
        return 'project planning'

    return get, query_fn, 'project', 'TaskA_MultiTopicInterference'


def make_task_b(signal_tick: int = 50, n_distractors: int = 1000):
    """
    Task B: Long-Horizon Retrieval Conflict

    Design:
      - Signal memory at tick 50 (early, important)
      - 1000+ distractor memories after (recent noise)
      - Query: signal's topic/content

    Episodic prediction:
      - Recency dominated: latest distractors overwhelm
      - Signal recall = ~0 (buried under recent memories)
      - Signal has low recency score

    Semantic prediction:
      - Signal marked as important (is_signal=True)
      - Semantic routing can boost signal
      - But only if semantic knows about signal's structure
      - (May still fail if signal is truly episodic-only)
    """
    def get(i):
        if i == signal_tick:
            # The critical signal - should be remembered
            topic = 'project'
            content = 'project planning milestone alpha critical objective'
            is_signal = True
        else:
            # Distractor memories
            topic = 'debug' if i % 2 == 0 else 'meeting'
            content = f'{topic} discussion {i} {random.randint(1000,9999)}'
            is_signal = False
        return topic, content, is_signal

    # Pre-generate to know signal position
    all_memories = []
    for i in range(n_distractors + 100):
        topic, content, is_signal = get(i)
        all_memories.append({'topic': topic, 'content': content, 'is_signal': is_signal, 'tick': i})

    signal_info = [m for m in all_memories if m['is_signal']][0]
    signal_idx = signal_info['tick']

    def query_fn(i):
        # During distractor-heavy phase, keep querying for signal
        if i > signal_idx + 100:
            return 'project planning milestone'
        return 'project planning'

    return get, query_fn, 'project', 'TaskB_LongHorizonConflict', signal_idx


def make_task_c():
    """
    Task C: Cross-Episode Abstraction

    Design:
      - Phase 1 (0-499): "roadmap planning milestone" - project keywords
      - Phase 2 (500-999): "deployment sequencing release" - NO project keywords
      - Phase 3 (1000-1499): "execution dependency graph" - NO project keywords
      - Query: "project planning" throughout ALL phases

    Surface forms completely change across phases.
    But all share the same underlying category: PLANNING/EXECUTION COORDINATION.

    Episodic prediction:
      - Phase 1: high recall (keyword match)
      - Phase 2: near-zero recall (no project keywords)
      - Phase 3: near-zero recall (no project keywords)
      - Surface mismatch causes activation failure

    Semantic prediction:
      - project_schema captures abstract structure across phases
      - Phase 2/3: schema still routes to content because...
        - BUT: our current semantic only does keyword matching
        - No actual abstract structure formation
      - May still fail = proves abstraction doesn't naturally emerge
    """
    def get(i):
        if i < 500:
            # Phase 1: classic project keywords
            topic = 'project'
            content = 'roadmap planning milestone alignment objectives'
            abstract = 'planning'
        elif i < 1000:
            # Phase 2: same structure, different surface
            topic = 'coding'
            content = 'deployment sequencing release coordination dependency'
            abstract = 'planning'
        else:
            # Phase 3: same structure, different surface
            topic = 'meeting'
            content = 'execution dependency graph workflow coordination'
            abstract = 'planning'
        return topic, content

    def query_fn(i):
        # Query always uses Phase 1 keywords
        return 'project planning milestone'

    return get, query_fn, 'project', 'TaskC_CrossEpisodeAbstraction'


def make_task_d(n_signal: int = 15, n_distractor: int = 1485):
    """
    Task D: Distractor Injection

    Design:
      - 1% signal (15), 99% distractor (1485)
      - Signal has distinctive structure: contains both "alpha" and "critical"
      - Distractors are random
      - Both have similar recency distribution

    Episodic prediction:
      - Distractor overwhelming by count
      - No structural pattern to exploit
      - Signal recall ≈ signal_ratio = 0.01

    Semantic prediction:
      - If semantic learns "alpha critical" pattern:
        - Can filter distractors
        - Signal recall >> 0.01
      - If semantic only does keyword matching:
        - Same as episodic = no advantage
    """
    signal_pattern = 'alpha critical project planning'

    def get(i):
        if i < n_signal:
            # Signal memories - distinctive pattern
            topic = 'project'
            content = f'{signal_pattern} objective {i}'
            is_signal = True
            pattern = 'alpha_critical'
        else:
            # Distractor memories - random
            topics = ['debug', 'meeting', 'coding', 'review']
            topic = topics[i % len(topics)]
            content = f'{topic} discussion {i} {random.randint(1000,9999)}'
            is_signal = False
            pattern = 'distractor'
        return topic, content, is_signal, pattern

    def query_fn(i):
        return 'project planning alpha critical'

    return get, query_fn, 'project', 'TaskD_DistractorInjection'


# ═══════════════════════════════════════════════════════════════════
# EXPERIMENTAL SYSTEM (wraps CognitiveSystem for task-specific logic)
# ═══════════════════════════════════════════════════════════════════

class ExperimentalSystem:
    """CognitiveSystem extended with task-specific signal injection."""

    def __init__(self, task_fn, query_fn, target_topic: str, task_name: str,
                 mode: str = 'full', lesion_type: Optional[str] = None,
                 n_ticks: int = 1500):
        self.task_fn = task_fn
        self.query_fn = query_fn
        self.target_topic = target_topic
        self.task_name = task_name
        self.n_ticks = n_ticks

        # Build base cognitive system
        self.cog = CognitiveSystem(mode=mode, lesion_type=lesion_type)

        # Task B/D need special memory injection
        self.task_b_signal_idx = None
        if 'TaskB' in task_name:
            # Pre-generate to find signal position
            all_m = []
            for test_i in range(n_ticks):
                topic, content, is_signal = task_fn(test_i)
                if is_signal:
                    self.task_b_signal_idx = test_i
                    all_m.append({'topic': topic, 'content': content})
                    break
            if self.task_b_signal_idx is None:
                self.task_b_signal_idx = 50

    def run(self):
        cog = self.cog
        cog._init_schemas()

        for i in range(self.n_ticks):
            cog.tick = i + 1

            # Memory storage - check tuple length to determine task type
            task_result = self.task_fn(i)
            if len(task_result) == 4:
                topic, content, is_signal, pattern = task_result
                cog.store(content, topic, is_signal=is_signal, pattern=pattern)
            elif len(task_result) == 3:
                topic, content, is_signal = task_result
                cog.store(content, topic, is_signal=is_signal)
            else:
                topic, content = task_result
                cog.store(content, topic)

            cog.evict_working()

            # Retrieval query
            query = self.query_fn(i)
            target = self.target_topic if 'TaskB' not in self.task_name else 'project'
            results = cog.retrieve(query, target, top_k=5)

        return cog._build_report(self.task_name, self.n_ticks)


# ═══════════════════════════════════════════════════════════════════
# RUN EXPERIMENTS
# ═══════════════════════════════════════════════════════════════════

def run_task_a():
    """Task A: Multi-topic Interference"""
    print('\n' + '='*70)
    print('TASK A: Multi-topic Interference')
    print('='*70)
    task_fn, query_fn, target, name = make_task_a()

    print(f"\n{'Config':<20}{'first':>8}{'second':>8}{'osc':>10}{'signal':>10}{'entropy':>10}")
    print('-'*70)

    results = {}
    for config, mode, lesion in [
        ('episodic_only', 'full', None),
        ('semantic_route', 'no_adaptation', None),
        ('semantic_full', 'full', None),
        ('lesion_shuffle', 'full', 'shuffle_routing'),
    ]:
        sys = ExperimentalSystem(task_fn, query_fn, target, name, mode=mode, lesion_type=lesion, n_ticks=1500)
        if config == 'episodic_only':
            sys.cog.schemas = []
        report = sys.run()
        results[config] = report

        segs = report['segment_metrics']
        f = segs.get('first', {}).get('precision', 0)
        s = segs.get('second', {}).get('precision', 0)
        osc = report['oscillation_rate']
        sig = report['signal_recall']
        ent = sum(e['entropy'] for e in sys.cog.retrieval_log) / max(len(sys.cog.retrieval_log), 1)
        print(f"{config:<20}{f:>8.3f}{s:>8.3f}{osc:>10.3f}{sig:>10.3f}{ent:>10.3f}")

    return results


def run_task_b():
    """Task B: Long-Horizon Retrieval Conflict"""
    print('\n' + '='*70)
    print('TASK B: Long-Horizon Retrieval Conflict')
    print('='*70)
    task_fn, query_fn, target, name, signal_idx = make_task_b()

    print(f"\n{'Config':<20}{'first':>8}{'second':>8}{'signal':>10}{'entropy':>10}")
    print('-'*70)

    results = {}
    for config, mode, lesion in [
        ('episodic_only', 'full', None),
        ('semantic_route', 'no_adaptation', None),
        ('semantic_full', 'full', None),
        ('lesion_shuffle', 'full', 'shuffle_routing'),
    ]:
        sys = ExperimentalSystem(task_fn, query_fn, target, name, mode=mode, lesion_type=lesion, n_ticks=1500)
        if config == 'episodic_only':
            sys.cog.schemas = []
        report = sys.run()
        results[config] = report

        segs = report['segment_metrics']
        f = segs.get('first', {}).get('precision', 0)
        s = segs.get('second', {}).get('precision', 0)
        sig = report['signal_recall']
        ent = sum(e['entropy'] for e in sys.cog.retrieval_log) / max(len(sys.cog.retrieval_log), 1)
        print(f"{config:<20}{f:>8.3f}{s:>8.3f}{sig:>10.3f}{ent:>10.3f}")

    return results


def run_task_c():
    """Task C: Cross-Episode Abstraction"""
    print('\n' + '='*70)
    print('TASK C: Cross-Episode Abstraction')
    print('='*70)
    task_fn, query_fn, target, name = make_task_c()

    print(f"\n{'Config':<20}{'phase1':>8}{'phase2':>8}{'phase3':>8}{'signal':>10}")
    print('-'*70)

    results = {}
    for config, mode, lesion in [
        ('episodic_only', 'full', None),
        ('semantic_route', 'no_adaptation', None),
        ('semantic_full', 'full', None),
        ('lesion_shuffle', 'full', 'shuffle_routing'),
    ]:
        sys = ExperimentalSystem(task_fn, query_fn, target, name, mode=mode, lesion_type=lesion, n_ticks=1500)
        if config == 'episodic_only':
            sys.cog.schemas = []
        report = sys.run()
        results[config] = report

        segs = report['segment_metrics']
        p1 = segs.get('first', {}).get('precision', 0)
        p2 = segs.get('second', {}).get('precision', 0)
        p3 = segs.get('third', {}).get('precision', 0)
        sig = report['signal_recall']
        print(f"{config:<20}{p1:>8.3f}{p2:>8.3f}{p3:>8.3f}{sig:>10.3f}")

    return results


def run_task_d():
    """Task D: Distractor Injection"""
    print('\n' + '='*70)
    print('TASK D: Distractor Injection (1% signal / 99% distractor)')
    print('='*70)
    task_fn, query_fn, target, name = make_task_d()

    print(f"\n{'Config':<20}{'first':>8}{'second':>8}{'signal':>10}{'entropy':>10}")
    print('-'*70)

    results = {}
    for config, mode, lesion in [
        ('episodic_only', 'full', None),
        ('semantic_route', 'no_adaptation', None),
        ('semantic_full', 'full', None),
        ('lesion_shuffle', 'full', 'shuffle_routing'),
    ]:
        sys = ExperimentalSystem(task_fn, query_fn, target, name, mode=mode, lesion_type=lesion, n_ticks=1500)
        if config == 'episodic_only':
            sys.cog.schemas = []
        report = sys.run()
        results[config] = report

        segs = report['segment_metrics']
        f = segs.get('first', {}).get('precision', 0)
        s = segs.get('second', {}).get('precision', 0)
        sig = report['signal_recall']
        ent = sum(e['entropy'] for e in sys.cog.retrieval_log) / max(len(sys.cog.retrieval_log), 1)
        print(f"{config:<20}{f:>8.3f}{s:>8.3f}{sig:>10.3f}{ent:>10.3f}")

    return results


def compute_verdict(all_results: Dict):
    """Compute overall verdict on semantic necessity."""
    print('\n\n' + '='*70)
    print('SEMANTIC NECESSITY VERDICT')
    print('='*70)

    # For each task, compare episodic_only vs semantic_full
    tasks = ['TaskA', 'TaskB', 'TaskC', 'TaskD']
    verdicts = {}

    print(f"\n{'Task':<20}{'Episodic':>10}{'SemFull':>10}{'Delta':>10}{'Necessity?':>15}")
    print('-'*70)

    necessity_count = 0
    for task in tasks:
        epi = all_results.get(f'{task}_epi', {})
        sem = all_results.get(f'{task}_sem', {})

        epi_signal = epi.get('signal_recall', 0)
        sem_signal = sem.get('signal_recall', 0)
        delta = sem_signal - epi_signal

        necessity = 'YES' if delta > 0.1 else ('MARGINAL' if delta > 0 else 'NO')
        if necessity == 'YES':
            necessity_count += 1

        verdicts[task] = {'epi': epi_signal, 'sem': sem_signal, 'delta': delta, 'verdict': necessity}

        epi_str = f"{epi_signal:.3f}" if epi_signal > 0 else 'N/A'
        sem_str = f"{sem_signal:.3f}" if sem_signal > 0 else 'N/A'
        print(f"{task:<20}{epi_str:>10}{sem_str:>10}{delta:>+10.3f}{necessity:>15}")

    print(f"\n{'='*70}")
    print(f"Tasks with semantic necessity proven: {necessity_count}/4")
    if necessity_count >= 2:
        print("VERDICT: SEMANTIC PROVIDES EPISODIC-INDEPENDENT CAPABILITY ✓")
        print("  semantic layer has proven necessity on multiple tasks")
    elif necessity_count == 1:
        print("VERDICT: MARGINAL - semantic provides benefit on limited tasks")
        print("  1/4 tasks show semantic necessity - insufficient for strong claim")
    else:
        print("VERDICT: SEMANTIC NECESSITY NOT PROVEN")
        print("  episodic-only performs equivalently across all tasks")
        print("  semantic layer is useful but not independently necessary")

    return verdicts


if __name__ == '__main__':
    print('v0.17 — Semantic Necessity Benchmark')
    print('='*70)
    print('Research Question: Does semantic provide capabilities')
    print('                   that episodic CANNOT independently achieve?')
    print('='*70)

    # Run all tasks
    results = {}

    # Task A
    r_a = run_task_a()
    results['TaskA_epi'] = r_a.get('episodic_only', {})
    results['TaskA_sem'] = r_a.get('semantic_full', {})

    # Task B
    r_b = run_task_b()
    results['TaskB_epi'] = r_b.get('episodic_only', {})
    results['TaskB_sem'] = r_b.get('semantic_full', {})

    # Task C
    r_c = run_task_c()
    results['TaskC_epi'] = r_c.get('episodic_only', {})
    results['TaskC_sem'] = r_c.get('semantic_full', {})

    # Task D
    r_d = run_task_d()
    results['TaskD_epi'] = r_d.get('episodic_only', {})
    results['TaskD_sem'] = r_d.get('semantic_full', {})

    # Verdict
    verdicts = compute_verdict(results)

    print('\n\n' + '='*70)
    print('SUMMARY')
    print('='*70)
    print("""
  v0.16 Result: semantic utility EXISTS, necessity NOT PROVEN
  v0.17 Goal: Design tasks where episodic MUST FAIL

  Key Metric: signal_recall
    - Did system retrieve the critical signal?
    - episodic-only baseline vs semantic-adaptive

  Interpretation:
    - Delta > 0.1: semantic provides significant independent capability
    - Delta ~ 0: episodic alone is sufficient
    - Delta < 0: semantic may be interfering

  Next Step: If necessity NOT PROVEN:
    - Current architecture cannot超越 episodic baseline
    - Need deeper abstraction mechanism
    - Or: accept that routing is the primary function
""")
