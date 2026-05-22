#!/usr/bin/env python3
import sys, os, time, json, random
from collections import defaultdict

_MCR_ROOT = '/home/minimak/mcr'
sys.path.insert(0, _MCR_ROOT)
sys.path.insert(0, os.path.join(_MCR_ROOT, 'stable'))
from layered_memory import LayeredMemory

PERSIST_DIR = '/home/minimak/mcr/runtime_phys_observation/run_data'
os.makedirs(PERSIST_DIR, exist_ok=True)

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

TICKS = 10_000
REPORT_EVERY = 1000
SNAPSHOT_EVERY = 500

random.seed(42)
lm = LayeredMemory(PERSIST_DIR)

memory_counts = []
latency_per_tick = []
gc_ops_per_tick = []
retrieval_counts = []
pathology_log = []
promotions = []
demotions = []
retrieval_history = []

start_time = time.time()

for tick in range(1, TICKS + 1):
    # Write 1-3 memories
    writes = random.randint(1, 3)
    for _ in range(writes):
        topic = random.choice(TOPICS)
        template = random.choice(MEMORY_TEMPLATES)
        content = template.format(
            topic=topic, n=random.randint(1,999),
            status=random.choice(STATUSES), env=random.choice(ENVS),
            team=random.choice(TEAMS), comp=random.choice(COMPS),
            who=random.choice(PEOPLE)
        )
        importance = random.uniform(0.3, 0.95)
        lm.store(content, "general", importance, [topic], tick)
    
    # Adversarial noise 10%
    if random.random() < 0.1:
        noise_content = f"irrelevant noise memory #{random.randint(1,10000)} at tick {tick}"
        lm.store(noise_content, "noise", 0.1, [f"noise_{random.randint(1,50)}"], tick)
    
    # Retrieval
    query = random.choice(TOPICS) if random.random() < 0.7 else random.choice(MEMORY_TEMPLATES).format(
        topic=random.choice(TOPICS), n="*", status="*", env="*", team="*", comp="*", who="*"
    )
    t0 = time.perf_counter()
    results = lm.retrieve(query, current_goal=query, current_tick=tick, max_results=5)
    latency_ms = (time.perf_counter() - t0) * 1000
    
    latency_per_tick.append((tick, latency_ms))
    retrieval_counts.append((tick, len(results)))
    
    if results:
        retrieval_history.append({
            "tick": tick, "ids": [m["id"] for m in results],
            "states": [m["state"] for m in results]
        })
    
    # Lifecycle
    decay_result = lm.process_decay_buffer(tick)
    review_result = lm.incremental_review(tick)
    gc_ops = (
        len(decay_result.get("revived", [])) + len(decay_result.get("deleted", [])) +
        len(review_result.get("promoted_to_semantic", [])) + len(review_result.get("archived", [])) +
        len(review_result.get("demoted_to_archive", []))
    )
    gc_ops_per_tick.append((tick, gc_ops))
    
    if review_result.get("promoted_to_semantic"):
        promotions.append((tick, len(review_result["promoted_to_semantic"])))
    if review_result.get("archived"):
        demotions.append((tick, len(review_result["archived"])))
    
    # Activation collapse check
    active = len(lm.working) + len(lm.episodic)
    if active < 2 and tick > 100:
        pathology_log.append({"tick": tick, "type": "activation_collapse", "active": active})
    
    # Memory counts
    memory_counts.append({
        "tick": tick,
        "working": len(lm.working),
        "episodic": len(lm.episodic),
        "semantic": len(lm.semantic),
        "archive": len(lm.archive),
    })
    
    # Report
    if tick % REPORT_EVERY == 0:
        elapsed = time.time() - start_time
        recent_lat = [l[1] for l in latency_per_tick[-1000:]]
        avg_lat = sum(recent_lat)/len(recent_lat) if recent_lat else 0
        max_lat = max(recent_lat) if recent_lat else 0
        c = memory_counts[-1]
        total_mem = c["working"] + c["episodic"] + c["semantic"] + c["archive"]
        recent_gc = [g[1] for g in gc_ops_per_tick[-1000:]]
        avg_gc = sum(recent_gc)/len(recent_gc) if recent_gc else 0
        print(f"TICK {tick}/{TICKS} ({elapsed:.1f}s) | mem={total_mem} (W={c['working']} E={c['episodic']} S={c['semantic']} A={c['archive']}) | lat={avg_lat:.4f}ms max={max_lat:.4f}ms | gc={avg_gc:.2f}/tick | proms={sum(p[1] for p in promotions[-1000:])} demos={sum(d[1] for d in demotions[-1000:])}")
    
    # Snapshot
    if tick % SNAPSHOT_EVERY == 0:
        snap = {"tick": tick, "memory": memory_counts[-1], "latency_ms": latency_per_tick[-1][1]}
        with open(os.path.join(PERSIST_DIR, f"snap_{tick}.json"), "w") as f:
            json.dump(snap, f)

# Final report
elapsed = time.time() - start_time
initial = memory_counts[0]
final = memory_counts[-1]
all_lat = [l[1] for l in latency_per_tick]
early_lat = [l[1] for l in latency_per_tick[:1000]]
late_lat = [l[1] for l in latency_per_tick[-1000:]]
early_avg = sum(early_lat)/len(early_lat)
late_avg = sum(late_lat)/len(late_lat)
lat_ratio = late_avg/early_avg if early_avg > 0 else 0

total_gc = [g[1] for g in gc_ops_per_tick]
avg_gc_total = sum(total_gc)/len(total_gc)
early_gc = [g[1] for g in gc_ops_per_tick[:1000]]
late_gc = [g[1] for g in gc_ops_per_tick[-1000:]]
gc_trend = (sum(late_gc)/len(late_gc)) / max(sum(early_gc)/len(early_gc), 0.001)

init_total = initial["working"] + initial["episodic"] + initial["semantic"] + initial["archive"]
fin_total = final["working"] + final["episodic"] + final["semantic"] + final["archive"]
memory_growth = fin_total - init_total

print(f"\n{'='*60}")
print(f"FINAL REPORT — {TICKS} ticks, {elapsed:.1f}s")
print(f"{'='*60}")
print(f"\n[BOUNDED PROPERTIES]")
print(f"  Memory growth:   {memory_growth:+d} items ({init_total} → {fin_total})")
print(f"  Working:         {initial['working']} → {final['working']} (capped at MAX_WORKING)")
print(f"  Episodic:        {initial['episodic']} → {final['episodic']} (capped at EPISODIC_HARD_CAP)")
print(f"  Semantic:        {initial['semantic']} → {final['semantic']} (no hard cap)")
print(f"  Archive:         {initial['archive']} → {final['archive']}")
print(f"  Latency avg:     {sum(all_lat)/len(all_lat):.4f}ms  max: {max(all_lat):.4f}ms")
print(f"  Latency ratio:   {lat_ratio:.2f}x (early→late, <10x = PASS)")
print(f"  GC avg:          {avg_gc_total:.4f} ops/tick")
print(f"  GC trend:        {gc_trend:.2f}x (early→late, <1.0 = bounded)")
print(f"\n[FAILURE SIGNALS]")
print(f"  Activation collapses: {len([p for p in pathology_log if p['type']=='activation_collapse'])}")
print(f"  Total pathologies:    {len(pathology_log)}")
print(f"\n[RETRIEVAL]")
print(f"  Unique retrievals: {len(retrieval_history)}")
state_counts = defaultdict(int)
for r in retrieval_history:
    for s in r["states"]:
        state_counts[s] += 1
print(f"  By state: {dict(state_counts)}")
print(f"\n[LIFECYCLE TRANSITIONS]")
print(f"  Total promotions: {sum(p[1] for p in promotions)}")
print(f"  Total demotions:   {sum(d[1] for d in demotions)}")
print(f"\n[VERDICT]")
verdicts = []
if abs(memory_growth) < TICKS * 0.5:
    verdicts.append("MEMORY BOUNDED")
else:
    verdicts.append("MEMORY UNBOUNDED")
if lat_ratio < 10:
    verdicts.append("LATENCY BOUNDED")
else:
    verdicts.append("LATENCY EXPLODING")
if gc_trend < 1.0:
    verdicts.append("GC BOUNDED")
else:
    verdicts.append("GC GROWING")
for v in verdicts:
    print(f"  {'✓' if 'BOUNDED' in v else '✗'} {v}")

# Save data
data = {
    "memory_counts": memory_counts,
    "latency_per_tick": latency_per_tick,
    "gc_ops_per_tick": gc_ops_per_tick,
    "pathology_log": pathology_log,
    "promotions": promotions,
    "demotions": demotions,
    "retrieval_history": retrieval_history[:1000],
    "summary": {
        "ticks": TICKS, "elapsed": elapsed,
        "memory_growth": memory_growth,
        "lat_ratio": lat_ratio,
        "gc_trend": gc_trend,
        "verdicts": verdicts,
    }
}
path = os.path.join(PERSIST_DIR, "runtime_physics_data.json")
with open(path, "w") as f:
    json.dump(data, f, indent=2)
print(f"\n[DATA] {path} ({os.path.getsize(path)} bytes)")
