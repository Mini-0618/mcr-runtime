#!/usr/bin/env python3
"""
MCR Boundary Stress Test — W=10→5→3
=====================================
Phase 1: W=10, tick 0-3000
Phase 2: W=5,  tick 3000-6000
Phase 3: W=3,  tick 6000-10000

Key metrics:
  - Latency @ boundary (tick 2999 vs 3001, 5999 vs 6001)
  - Replay trigger rate per phase
  - Replay success rate
  - Layer distribution (W/E/S/A) per phase
  - Eviction burst at shrink events
"""
import sys, os, time, json, random, math
from collections import defaultdict

_MCR_ROOT = '/home/minimak/mcr'
sys.path.insert(0, _MCR_ROOT)
sys.path.insert(0, os.path.join(_MCR_ROOT, 'stable'))
from layered_memory import LayeredMemory

# Output
PERSIST_DIR = '/home/minimak/mcr/runtime_phys_observation/run_data_stress_10k'
os.makedirs(PERSIST_DIR, exist_ok=True)

# Same workload as run_physics_50k.py (identical random seed for fair comparison)
TOPICS = [
    "project_alpha", "project_beta", "project_gamma",
    "meeting_notes", "decision_log", "risk_register",
    "user_feedback", "bug_report", "feature_request",
    "code_review", "deployment_log", "test_results",
    "research_notes", "experiment_log", "analysis_report",
]
MEMORY_TEMPLATES = [
    "completed {topic} milestone {n} with status {status}",
    "updated {topic} documentation for release {n}",
    "resolved {topic} critical issue in component {comp}",
    "deployed {topic} version {n} to {env}",
    "reviewed {topic} PR #{n} from contributor {who}",
]
ENVS = ["production", "staging", "development", "qa"]
TEAMS = ["backend", "frontend", "infra", "security", "data"]
COMPS = ["api", "ui", "db", "cache", "worker", "gateway"]
PEOPLE = ["alice", "bob", "charlie", "diana", "eve", "frank"]
STATUSES = ["complete", "partial", "failed", "pending"]

# 10k stress test
TICKS = 10_000
REPORT_EVERY = 1000
SNAPSHOT_EVERY = 1000

# Stress test phases
PHASE_1_END = 3000   # W=10
PHASE_2_END = 6000   # W=5
PHASE_3_END = 10000  # W=3

random.seed(42)
lm = LayeredMemory(PERSIST_DIR, max_working=10)

# Metrics
latency_per_tick = []      # raw latency ms per tick
memory_counts = []         # [W, E, S, A] per snapshot
events_log = []            # W_SHRINK events
retrieval_counts = []
total_retrievals = 0
replay_attempts = 0
replay_successes = 0
phase_transitions = []      # track phase changes

start_time = time.time()

def make_memory(topic, n, status, comp, env, who):
    tmpl = random.choice(MEMORY_TEMPLATES)
    return tmpl.format(
        topic=topic, n=n, status=status,
        comp=comp, env=env, who=who
    )

def get_current_phase(tick):
    if tick < PHASE_1_END:
        return 1, 10
    elif tick < PHASE_2_END:
        return 2, 5
    else:
        return 3, 3

def measure_retrieval_latency(tick, phase_w):
    """Simulate a retrieval + store cycle, measure latency in ms."""
    t0 = time.perf_counter()
    # Retrieval: scan working + short layers (simulate cognition step)
    for _ in range(3):
        _ = lm.retrieve(
            query="project status update",
            max_results=5,
            current_tick=tick,
        )
    # Store new memory
    topic = random.choice(TOPICS)
    n = random.randint(1, 999)
    status = random.choice(STATUSES)
    comp = random.choice(COMPS)
    env = random.choice(ENVS)
    who = random.choice(PEOPLE)
    content = make_memory(topic, n, status, comp, env, who)
    lm.store(content, memory_type="general", importance=0.5, current_tick=tick)
    t1 = time.perf_counter()
    return (t1 - t0) * 1000

# Warmup: pre-populate with some memories
for i in range(15):
    topic = random.choice(TOPICS)
    lm.store(
        make_memory(topic, i, random.choice(STATUSES),
                    random.choice(COMPS), random.choice(ENVS), random.choice(PEOPLE)),
        current_tick=0
    )

print(f"[STRESS] Starting W=10→5→3 stress test, {TICKS} ticks")
print(f"[STRESS] Phase 1: W=10 (tick 0-{PHASE_1_END})")
print(f"[STRESS] Phase 2: W=5  (tick {PHASE_1_END}-{PHASE_2_END})")
print(f"[STRESS] Phase 3: W=3  (tick {PHASE_2_END}-{PHASE_3_END})")

for tick in range(1, TICKS + 1):
    current_phase, expected_w = get_current_phase(tick)

    # Trigger W shrink at phase boundaries
    if tick == PHASE_1_END:
        event = lm.set_max_working(5, current_tick=tick)
        events_log.append(event)
        phase_transitions.append({
            "tick": tick, "from": 10, "to": 5, "phase": 2,
            "working_before_shrink": 10
        })
        print(f"[STRESS] tick={tick}: W_SHRINK 10→5, evicted={event['evicted']}")

    if tick == PHASE_2_END:
        event = lm.set_max_working(3, current_tick=tick)
        events_log.append(event)
        phase_transitions.append({
            "tick": tick, "from": 5, "to": 3, "phase": 3,
            "working_before_shrink": 5
        })
        print(f"[STRESS] tick={tick}: W_SHRINK 5→3, evicted={event['evicted']}")

    # Measure latency
    phase_w = lm.max_working
    lat_ms = measure_retrieval_latency(tick, phase_w)
    latency_per_tick.append([tick, lat_ms])

    # Snapshot at phase transitions (boundary analysis)
    if tick == PHASE_1_END - 1 or tick == PHASE_1_END + 1 or \
       tick == PHASE_2_END - 1 or tick == PHASE_2_END + 1 or \
       tick % SNAPSHOT_EVERY == 0:
        snapshot = {
            "tick": tick,
            "phase": current_phase,
            "W": phase_w,
            "working": len(lm.working),
            "episodic": len(lm.episodic),
            "semantic": len(lm.semantic),
            "archive": len(lm.archive),
            "latency_ms": lat_ms,
        }
        memory_counts.append(snapshot)

    if tick % REPORT_EVERY == 0:
        elapsed = time.time() - start_time
        w = lm.max_working
        print(f"[STRESS] tick={tick:5d} phase={current_phase} W={w} "
              f"lat={lat_ms:.4f}ms W={len(lm.working)} E={len(lm.episodic)} "
              f"A={len(lm.archive)} ({elapsed:.1f}s)")

    # Periodic flush + review
    if tick % 100 == 0:
        lm.try_flush(current_tick=tick)
    if tick % 500 == 0:
        lm.periodic_review(current_tick=tick)

# Final flush
lm.try_flush(current_tick=TICKS)

# Save data
output = {
    "config": {
        "ticks": TICKS,
        "phase_1": {"W": 10, "ticks": f"0-{PHASE_1_END}"},
        "phase_2": {"W": 5,  "ticks": f"{PHASE_1_END}-{PHASE_2_END}"},
        "phase_3": {"W": 3,  "ticks": f"{PHASE_2_END}-{PHASE_3_END}"},
    },
    "latency": latency_per_tick,
    "snapshots": memory_counts,
    "events": events_log,
    "phase_transitions": phase_transitions,
    "total_ticks": TICKS,
    "duration_s": time.time() - start_time,
}

out_path = os.path.join(PERSIST_DIR, "stress_10k_data.json")
with open(out_path, "w") as f:
    json.dump(output, f, indent=2)

print(f"\n[STRESS] DONE — {TICKS} ticks in {time.time()-start_time:.1f}s")
print(f"[STRESS] Data: {out_path}")
print(f"[STRESS] Shrink events: {len(events_log)}")
for ev in events_log:
    print(f"  tick={ev['tick']} {ev['old']}→{ev['new']} evicted={ev['evicted']}")
