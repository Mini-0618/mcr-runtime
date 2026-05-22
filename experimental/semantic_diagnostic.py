#!/usr/bin/env python3
"""v0.15 Diagnostic — trace routing + adaptation for topic_phases"""

import random
import math
from collections import defaultdict
random.seed(42)

from semantic_schema_v15 import StableSchemaSystem

# Run topic_phases with stable mode, capture per-tick details
sys = StableSchemaSystem(mode='stable')
sys._init_schemas()

trace = []

for i in range(1500):
    sys.tick = i + 1
    topic = 'project' if i < 500 else ('debug' if i < 1000 else 'meeting')
    content = f"{topic} task {i}"
    sys.store(content, topic)
    sys.evict_working()

    t = sys.tick
    q_words = set(content.lower().split())

    # Route
    activations = sys._route(content, t)
    activated = [s for s in sys.schemas if s.activation_strength > 0]

    # Spread
    sys._spread(activations, t)
    routed = [m for m in sys.episodic if m.routing_boost > 0]

    # Score and retrieve
    candidates = sys.working + sys.episodic
    scored = [(m.score(t), m) for m in candidates]
    scored.sort(key=lambda x: -x[0])
    results = [m for _, m in scored[:5]]

    for m in results:
        m.access_count += 1
        m.last_access = t
    for m in sys.episodic:
        m.routing_boost *= 0.5

    sys._track_clusters()

    correct = sum(1 for m in results if m.topic_tag == topic)
    precision = correct / max(len(results), 1)

    trace.append({
        'tick': i+1,
        'topic': topic,
        'activated_schemas': [(s.id.split('_')[1], s.topic_tag) for s in activated],
        'activations': dict(activations),
        'result_topics': [m.topic_tag for m in results],
        'precision': precision,
        'schema_count': len(sys.schemas),
        'routed_epi_topics': [m.topic_tag for m in routed],
    })

# Phase transitions
print("="*70)
print("TOPIC_PHASES DIAGNOSTIC")
print("="*70)

print("\nPHASE TRANSITION (tick 498-512):")
print(f"{'tick':>5} {'topic':>8} {'activated':>25} {'acts':>15} {'result':>20} {'prec':>6}")
print("-"*70)
for entry in trace:
    if 498 <= entry['tick'] <= 512:
        acts_str = str(entry['activations'])[:20]
        result_str = str(entry['result_topics'][:3])[:20]
        print(f"{entry['tick']:>5} {entry['topic']:>8} {str(entry['activated_schemas']):>25} "
              f"{acts_str:>15} {result_str:>20} {entry['precision']:>6.2f}")

# Schema activations per phase
print("\n\nSCHEMA ACTIVATIONS PER PHASE:")
phase_activations = [defaultdict(int) for _ in range(3)]
for entry in trace:
    phase = 0 if entry['tick'] <= 500 else (1 if entry['tick'] <= 1000 else 2)
    for schema_id, schema_topic in entry['activated_schemas']:
        phase_activations[phase][f"{schema_id}({schema_topic})"] += 1

for phase, acts in enumerate(phase_activations):
    print(f"\nPhase {phase} ({[0,500,1000][phase]}-{[500,1000,1500][phase]}):")
    for k, v in sorted(acts.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

# Key insight: when topic shifts, what do activated schemas look like?
print("\n\nKEY INSIGHT — why routing fails:")
for phase in range(2):
    phase_data = [e for e in trace if (phase==0 and e['tick']<=500) or (phase==1 and 500<e['tick']<=1000)]
    phase_data = phase_data[:50]  # first 50 ticks of phase

    # What schemas activate for "debug" queries in phase 2?
    topics_activated = defaultdict(list)
    for e in phase_data:
        for schema_id, schema_topic in e['activated_schemas']:
            topics_activated[schema_topic].append(schema_id)

    print(f"\nPhase {phase+1} (topic={['project','debug','meeting'][phase]}) first 50 queries:")
    for tp, schemas in sorted(topics_activated.items()):
        unique = set(schemas)
        print(f"  {tp}: schemas activated = {[(s, schemas.count(s)) for s in sorted(unique)]}")

# How many "debug" queries in phase 2 get debug schema activation?
phase2_debug = [e for e in trace if 500 < e['tick'] <= 1000]
debug_schema_activated = sum(1 for e in phase2_debug if any('debug' in s[1] for s in e['activated_schemas']))
print(f"\nPhase 2: {debug_schema_activated}/{len(phase2_debug)} debug queries activate debug_schema")
print(f"Phase 2: avg precision = {sum(e['precision'] for e in phase2_debug)/len(phase2_debug):.3f}")

# What does routing look like for tick 510?
entry510 = trace[509]  # tick 510
print(f"\n\nTICK 510 ROUTING DETAIL:")
print(f"  Query topic: debug")
print(f"  Activated schemas: {entry510['activated_schemas']}")
print(f"  Activation dict: {entry510['activations']}")
print(f"  Routed episodic topics: {entry510['routed_epi_topics'][:10]}")
print(f"  Result: {entry510['result_topics']}")
print(f"  Precision: {entry510['precision']}")

# Show episodic pool composition at tick 510
epi_at_510 = [m for m in sys.episodic if 500 <= m.created <= 510]
print(f"\n  Episodic created 500-510: {len(epi_at_510)}")
print(f"  Topics: {dict(defaultdict(int, [(m.topic_tag, 1) for m in epi_at_510]))}")

# Now check: when debug_schema activates, does it spread to debug episodic?
print("\n\nTESTING: If debug_schema activated, does it spread to debug episodic?")
# At tick 510, debug_schema should activate for "debug task 510"
# then spread to debug episodic
# but what is the routing_boost?
for m in sys.episodic[-20:]:
    print(f"  {m.topic_tag}: routing_boost={m.routing_boost:.4f}, created={m.created}")
