#!/usr/bin/env python3
"""
Naive Agent Baseline — 50k Tick
================================
对比组：无限增长的简单 Agent（无 bounded memory，无 WAL，无 replay）

对比对象：MCR LayeredMemory (W=10 bounded, archive+tombstone lifecycle)

目的：证明"bounded memory + lifecycle governance"比"无限增长"好多少
"""
import sys, os, time, json, random, math
from collections import defaultdict

_MCR_ROOT = '/home/minimak/mcr'
PERSIST_DIR = '/home/minimak/mcr/run_data/run_data_baseline_naive_10k'
os.makedirs(PERSIST_DIR, exist_ok=True)

# Same workload as run_physics_50k.py (identical TOPICS, TEMPLATES, params)
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

# Same tick count as MCR 10k (50k too slow for naive O(n) scan)
TICKS = 10_000
REPORT_EVERY = 5000
SNAPSHOT_EVERY = 5000

random.seed(42)

# ===== NAIVE AGENT =====
# Just a flat list — no bounded, no lifecycle, no eviction
class NaiveAgent:
    def __init__(self):
        self.memory = []  # unbounded list — everything stored forever
        self.access_count = defaultdict(int)  # for recency scoring

    def store(self, text, memory_type=None, tags=None):
        item = {
            "id": len(self.memory),
            "text": text,
            "memory_type": memory_type,
            "tags": tags or [],
            "created_tick": None,  # filled by caller
        }
        self.memory.append(item)
        return item["id"]

    def retrieve(self, query, top_k=5):
        """
        Naive retrieval: simple substring + recency scoring.
        No semantic layer. No bounded scan. Full scan over ALL memory.
        """
        if not self.memory:
            return []

        scores = []
        query_lower = query.lower()
        for item in self.memory:
            # Substring match score
            text_lower = item["text"].lower()
            if query_lower in text_lower:
                base_score = len(query_lower) / max(len(text_lower), 1)
            else:
                base_score = 0.0

            # Recency penalty — older items score lower
            age = len(self.memory) - item["id"]
            recency_score = 1.0 / math.log2(age + 2)  # log decay

            # Combined score
            final_score = base_score * recency_score
            scores.append((item, final_score))

        # Sort descending by score, return top_k
        scores.sort(key=lambda x: x[1], reverse=True)
        return [item for item, score in scores[:top_k]]

    def memory_size(self):
        return len(self.memory)


agent = NaiveAgent()

# Metrics
memory_counts = []
latency_per_tick = []
store_ops_per_tick = []
retrieve_ops_per_tick = []
retrieval_scan_depths = []  # how many items we scanned per retrieve
top_k_recall = []  # did we find relevant items?
avg_retrieval_score = []

start_time = time.time()

def make_memory(topic, n, status, comp, env, who):
    tmpl = random.choice(MEMORY_TEMPLATES)
    return tmpl.format(
        topic=topic, n=n, status=status,
        comp=comp, env=env, who=who
    )

# Pre-build expected items per topic (for recall measurement)
# In a real baseline we'd track ground truth; here we approximate
# by measuring whether retrieval returns items of the queried topic
topic_hits = []
topic_misses = []

# ---- MAIN LOOP ----
for tick in range(1, TICKS + 1):
    tick_start = time.perf_counter()

    # Same workload: 3-5 stores per tick
    stored_count = 0
    stored_topics = []
    for _ in range(random.randint(3, 5)):
        topic = random.choice(TOPICS)
        text = make_memory(
            topic, random.randint(1, 100),
            random.choice(STATUSES),
            random.choice(COMPS),
            random.choice(ENVS),
            random.choice(PEOPLE)
        )
        tags = [topic, random.choice(TEAMS)]
        agent.store(text, memory_type=topic, tags=tags)
        stored_count += 1
        stored_topics.append(topic)

    store_ops_per_tick.append(stored_count)

    # Same retrieval: 1-3 per tick
    retrieved_count = 0
    for _ in range(random.randint(1, 3)):
        topic = random.choice(TOPICS)
        results = agent.retrieve(topic, top_k=5)
        retrieved_count += 1

        # Measure: did we scan the full memory?
        scan_depth = len(agent.memory)  # naive scan = full scan every time
        retrieval_scan_depths.append(scan_depth)

        # Recall: did any result match the queried topic?
        if results:
            # Check if top result matches topic
            top = results[0]
            hit = (top.get("memory_type") == topic)
            topic_hits.append(hit)
            topic_misses.append(not hit)

            # Average relevance score
            query_lower = topic.lower()
            scores = []
            for item in results:
                text_lower = item["text"].lower()
                if query_lower in text_lower:
                    scores.append(len(query_lower) / max(len(text_lower), 1))
            if scores:
                avg_retrieval_score.append(sum(scores) / len(scores))
            else:
                avg_retrieval_score.append(0.0)
        else:
            topic_misses.append(True)

    retrieve_ops_per_tick.append(retrieved_count)

    # Latency: store + retrieve ops
    tick_elapsed = (time.perf_counter() - tick_start) * 1000
    latency_per_tick.append(tick_elapsed)

    # Snapshot every SNAPSHOT_EVERY ticks
    if tick % SNAPSHOT_EVERY == 0:
        mem_size = agent.memory_size()
        memory_counts.append({
            "tick": tick,
            "memory_size": mem_size,
            "total_stores": sum(store_ops_per_tick),
            "total_retrieves": sum(retrieve_ops_per_tick),
        })

        # Save snapshot
        snap_path = os.path.join(PERSIST_DIR, f"snap_{tick}.json")
        snap = {
            "tick": tick,
            "memory_size": mem_size,
            "total_stores": sum(store_ops_per_tick),
            "total_retrieves": sum(retrieve_ops_per_tick),
        }
        with open(snap_path, "w") as f:
            json.dump(snap, f, indent=2)

    # Progress report every REPORT_EVERY ticks
    if tick % REPORT_EVERY == 0:
        elapsed = time.time() - start_time
        mem_size = agent.memory_size()
        recent_lat = latency_per_tick[-REPORT_EVERY:]
        avg_lat = sum(recent_lat) / len(recent_lat) if recent_lat else 0
        max_lat = max(recent_lat) if recent_lat else 0
        recent_scan = retrieval_scan_depths[-REPORT_EVERY:]
        avg_scan = sum(recent_scan) / len(recent_scan) if recent_scan else 0
        hit_rate = sum(topic_hits[-REPORT_EVERY:]) / max(len(topic_hits[-REPORT_EVERY:]), 1) if topic_hits else 0
        avg_score = sum(avg_retrieval_score[-REPORT_EVERY:]) / max(len(avg_retrieval_score[-REPORT_EVERY:]), 1) if avg_retrieval_score else 0

        print(f"\n[TICK {tick:,}/{TICKS:,} | {tick/TICKS*100:.1f}%] {elapsed:.1f}s")
        print(f"  MEMORY SIZE: {mem_size:,} (unbounded growth)")
        print(f"  LAT: avg={avg_lat:.3f}ms max={max_lat:.3f}ms")
        print(f"  SCAN DEPTH: avg={avg_scan:.0f} items (full scan every time)")
        print(f"  RECALL HIT RATE: {hit_rate:.3f}")
        print(f"  AVG RETRIEVAL SCORE: {avg_score:.4f}")

# ---- FINAL REPORT ----
elapsed = time.time() - start_time
mem_size = agent.memory_size()

# Growth rate: early vs late
def growth_rate(series):
    if len(series) < 3:
        return 0.0
    n = len(series) // 3
    first_third = series[:n]
    last_third = series[-n:]
    f_avg = sum(first_third) / n
    l_avg = sum(last_third) / n
    if f_avg == 0:
        return 0.0
    return (l_avg - f_avg) / f_avg

# Memory growth rate
memory_sizes = [m["memory_size"] for m in memory_counts]
mem_growth_rate = growth_rate(memory_sizes) if len(memory_sizes) >= 3 else 0.0

# Latency ratio early vs late
early_lat = latency_per_tick[:len(latency_per_tick)//10]
late_lat = latency_per_tick[-len(latency_per_tick)//10:]
early_lat_avg = sum(early_lat) / len(early_lat) if early_lat else 0.001
late_lat_avg = sum(late_lat) / len(late_lat) if late_lat else 0.001
lat_ratio = late_lat_avg / early_lat_avg

# Scan depth growth
scan_growth = growth_rate(retrieval_scan_depths) if len(retrieval_scan_depths) >= 3 else 0.0

# Hit rate: early vs late
n = len(topic_hits) // 3
early_hits = sum(topic_hits[:n]) / max(n, 1)
late_hits = sum(topic_hits[-n:]) / max(n, 1)
hit_rate_change = late_hits - early_hits

print(f"\n{'='*60}")
print(f"NAIVE BASELINE 10K — FINAL REPORT")
print(f"{'='*60}")
print(f"  Ticks:        {TICKS:,}")
print(f"  Elapsed:      {elapsed:.1f}s ({elapsed/60:.1f} min)")
print(f"  Final MEM:    {mem_size:,} (UNBOUNDED — no eviction)")
print(f"  Memory growth rate: {mem_growth_rate*100:+.2f}%")
print(f"  Latency ratio:      {lat_ratio:.3f}x (early→late)")
print(f"  Scan depth growth:  {scan_growth*100:+.2f}% (full scan cost)")
print(f"  Recall hit rate:    {sum(topic_hits)/max(len(topic_hits),1):.3f} (overall)")
print(f"  Hit rate change:    {hit_rate_change:+.3f} (late - early)")
print(f"\nVERDICTS:")
print(f"  [REPORT] memory_unbounded: {mem_size > 10000}")
print(f"  [REPORT] latency_degraded: {lat_ratio > 1.5}")
print(f"  [REPORT] scan_cost_grew: {scan_growth > 0.5}")

# Save data
data = {
    "memory_counts": memory_counts,
    "latency_per_tick": latency_per_tick[:10000],
    "store_ops_per_tick": store_ops_per_tick,
    "retrieve_ops_per_tick": retrieve_ops_per_tick,
    "retrieval_scan_depths": retrieval_scan_depths,
    "topic_hits": topic_hits,
    "avg_retrieval_score": avg_retrieval_score,
    "summary": {
        "ticks": TICKS,
        "elapsed": elapsed,
        "final_memory_size": mem_size,
        "mem_growth_rate": mem_growth_rate,
        "lat_ratio": lat_ratio,
        "scan_growth_rate": scan_growth,
        "recall_hit_rate": sum(topic_hits)/max(len(topic_hits),1),
        "hit_rate_change": hit_rate_change,
    }
}
path = os.path.join(PERSIST_DIR, "baseline_naive_10k_data.json")
with open(path, "w") as f:
    json.dump(data, f, indent=2)
print(f"\n[DATA] {path} ({os.path.getsize(path)} bytes)")
