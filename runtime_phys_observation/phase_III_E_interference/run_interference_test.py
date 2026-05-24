#!/usr/bin/env python3
"""
MCR Phase III-E: Observability Interference Physics
A/B test: same workload, observer OFF vs ON.
"""

import sys, os, json, time, random, shutil, hashlib, csv
from pathlib import Path

sys.path.insert(0, './stable')
from layered_memory import LayeredMemory
from wal_manager import WALManager

BASE = Path("./runtime_phys_observation/phase_III_E_interference")
OFF_DIR = BASE / "runs" / "observer_off"
ON_DIR  = BASE / "runs" / "observer_on"
METRICS_DIR = BASE / "metrics"
for d in [OFF_DIR, ON_DIR, METRICS_DIR]: d.mkdir(parents=True, exist_ok=True)

WORKLOAD_TICKS = 10_000
NUM_MEMORIES = 500
SEED = 42_000

sys.path.insert(0, str(BASE))
from minimal_observer import MinimalObserver

TRANSITION_MAP = {
    ("working","episodic"):"promotion", ("working","semantic"):"promotion",
    ("working","archive"):"archive", ("working","deleted"):"delete",
    ("episodic","semantic"):"promotion", ("episodic","archive"):"archive",
    ("episodic","deleted"):"delete", ("semantic","archive"):"archive",
    ("semantic","deleted"):"delete",
    ("working","decay_buffer"):"decay_to_buffer",
    ("decay_buffer","DELETED"):"buffer_evict",
    ("decay_buffer","episodic"):"buffer_promote",
}

def wal_hashes(root):
    wal = WALManager(root=root)
    events = []
    for entry in wal.replay():
        ev_type = TRANSITION_MAP.get((entry.from_state, entry.to_state), f"{entry.from_state}→{entry.to_state}")
        events.append({"seq":entry.seq,"type":ev_type,"memory_id":entry.memory_id,"tick":entry.tick})
    key = "|".join([f"{e['seq']}:{e['type']}:{e['memory_id']}:{e['tick']}" for e in sorted(events,key=lambda x:x['seq'])])
    ohash = hashlib.sha256(key.encode()).hexdigest()[:16]
    seqs = [e["seq"] for e in events]
    lc = {}
    for e in events: lc[e["type"]] = lc.get(e["type"],0)+1
    return {"ordering_hash":ohash,"total_events":len(events),"seq_range":[min(seqs),max(seqs)] if seqs else [0,0],"lifecycle_counts":lc}

def run_workload(lm, observer_on=False, obs=None):
    tick_times = []
    t0 = time.perf_counter()
    for tick in range(1, WORKLOAD_TICKS+1):
        t_start = time.perf_counter()
        content = f"content_{tick % NUM_MEMORIES}"
        if observer_on and obs:
            obs.store(content, memory_type="test", tags=["t"], importance=0.5, current_tick=tick)
        else:
            lm.store(content, memory_type="test", tags=["t"], importance=0.5, current_tick=tick)
        if tick % 3 == 0:
            q = f"content_{(tick-1) % NUM_MEMORIES}"
            if observer_on and obs:
                obs.retrieve(q, max_results=3)
            else:
                lm.retrieve(q, max_results=3)
        if tick % 7 == 0:
            if observer_on and obs:
                obs.process_decay_buffer(tick)
            else:
                lm.process_decay_buffer(tick)
        if tick % 50 == 0:
            if observer_on and obs:
                obs.incremental_review(tick, top_k=5)
            else:
                lm.incremental_review(tick, top_k=5)
        if tick % 200 == 0:
            if observer_on and obs:
                obs.try_flush(tick)
            else:
                lm.try_flush(tick)
        tick_times.append(time.perf_counter() - t_start)
    total = time.perf_counter() - t0
    tick_times.sort()
    avg = sum(tick_times)/len(tick_times)
    p50 = tick_times[len(tick_times)//2]
    p99 = tick_times[int(len(tick_times)*0.99)]
    mc = {"working":len(lm.working),"episodic":len(lm.episodic),"semantic":len(lm.semantic),"archive":len(lm.archive)}
    m_obs = obs.get_metrics() if observer_on else {}
    return {"total_time_s":total,"avg_ms":avg*1000,"p50_ms":p50*1000,"p99_ms":p99*1000,"metrics":m_obs,"memory_counts":mc}

# ── RUN A: Observer OFF ───────────────────────────────────────────────────────
print("[A] Observer OFF...", end=" ", flush=True)
shutil.rmtree(str(OFF_DIR), ignore_errors=True); os.makedirs(str(OFF_DIR))
random.seed(SEED)
lm_off = LayeredMemory(str(OFF_DIR))
res_off = run_workload(lm_off, observer_on=False)
wal_off = wal_hashes(str(OFF_DIR))
print(f"done. time={res_off['total_time_s']:.2f}s avg={res_off['avg_ms']:.4f}ms p99={res_off['p99_ms']:.4f}ms events={wal_off['total_events']}")

# ── RUN B: Observer ON ───────────────────────────────────────────────────────
print("[B] Observer ON...", end=" ", flush=True)
shutil.rmtree(str(ON_DIR), ignore_errors=True); os.makedirs(str(ON_DIR))
random.seed(SEED)
lm_on = LayeredMemory(str(ON_DIR))
obs = MinimalObserver(lm_on)
res_on = run_workload(lm_on, observer_on=True, obs=obs)
wal_on = wal_hashes(str(ON_DIR))
print(f"done. time={res_on['total_time_s']:.2f}s avg={res_on['avg_ms']:.4f}ms p99={res_on['p99_ms']:.4f}ms events={wal_on['total_events']}")

# ── COMPARE ───────────────────────────────────────────────────────────────────
ratio = res_on["avg_ms"] / max(0.0001, res_off["avg_ms"])
p99r  = res_on["p99_ms"] / max(0.0001, res_off["p99_ms"])
hash_match = wal_off["ordering_hash"] == wal_on["ordering_hash"]
lc_match   = wal_off["lifecycle_counts"] == wal_on["lifecycle_counts"]
mc_off = res_off["memory_counts"]
mc_on  = res_on["memory_counts"]
mc_match = mc_off == mc_on
wal_amp = wal_on["total_events"] / max(1, wal_off["total_events"])

print(f"\n{'='*50}")
print(f"Latency ratio (ON/OFF): {ratio:.4f}x")
print(f"P99 ratio:               {p99r:.4f}x")
print(f"WAL hash match:          {hash_match}")
print(f"Lifecycle match:         {lc_match}")
print(f"Memory state match:      {mc_match}")
print(f"WAL amplification:       {wal_amp:.4f}x")
print(f"WAL OFF: {wal_off['ordering_hash']}")
print(f"WAL ON:  {wal_on['ordering_hash']}")
print(f"OFF lifecycle: {wal_off['lifecycle_counts']}")
print(f"ON  lifecycle: {wal_on['lifecycle_counts']}")
print(f"OFF memory: {mc_off}")
print(f"ON  memory: {mc_on}")

CLASS_E = []; CLASS_F = []
if ratio > 1.2:
    CLASS_E.append(f"G1: latency_ratio={ratio:.3f}x > 1.2x (PATHOLOGY)")
else:
    CLASS_F.append(f"G1: latency_ratio={ratio:.4f}x ≤ 1.2x (EXPECTED)")
if not lc_match:
    CLASS_E.append(f"G2: lifecycle_divergence — OFF={wal_off['lifecycle_counts']} ON={wal_on['lifecycle_counts']}")
else:
    CLASS_F.append("G2: lifecycle_counts MATCH (EXPECTED)")
if not hash_match:
    CLASS_E.append(f"G3: replay_hash DIVERGENCE")
else:
    CLASS_F.append("G3: replay_hash MATCH (EXPECTED)")
if not mc_match:
    CLASS_E.append(f"G4: memory_state DIVERGENCE — {mc_off} vs {mc_on}")
else:
    CLASS_F.append("G4: memory_state MATCH (EXPECTED)")
if wal_amp > 1.1:
    CLASS_E.append(f"G6: wal_amp={wal_amp:.3f}x > 1.1x (PATHOLOGY)")
else:
    CLASS_F.append(f"G6: wal_amp={wal_amp:.4f}x ≤ 1.1x (EXPECTED)")

all_expected = len(CLASS_E) == 0

print(f"\n{'='*50}")
for e in CLASS_E: print(f"  ❌ CLASS_E: {e}")
for e in CLASS_F: print(f"  ✅ CLASS_F: {e}")
print(f"\nOVERALL: {'✅ ALL EXPECTED — NO INTERFERENCE' if all_expected else '❌ PATHOLOGY DETECTED'}")

# ── SAVE ──────────────────────────────────────────────────────────────────────
comparison = {
    "experiment":"PHASE_III_E_Observability_Interference",
    "LKG":"637a11c907e8a889b909513522dfab8c",
    "workload_ticks":WORKLOAD_TICKS, "num_memories":NUM_MEMORIES, "seed":SEED,
    "observer_off":{
        "total_time_s":res_off["total_time_s"], "avg_ms":res_off["avg_ms"],
        "p99_ms":res_off["p99_ms"], "memory_counts":mc_off, "wal":wal_off,
    },
    "observer_on":{
        "total_time_s":res_on["total_time_s"], "avg_ms":res_on["avg_ms"],
        "p99_ms":res_on["p99_ms"], "memory_counts":mc_on, "wal":wal_on,
        "observer_metrics":res_on["metrics"],
    },
    "ratios":{"latency_ratio":ratio,"p99_ratio":p99r,"wal_amp":wal_amp},
    "matches":{"wal_hash_match":hash_match,"lifecycle_match":lc_match,"memory_match":mc_match},
    "classifications":{"CLASS_E_pathology":CLASS_E,"CLASS_F_expected":CLASS_F},
    "all_expected":all_expected,
}
with open(METRICS_DIR/"observer_overhead_metrics.json","w") as f:
    json.dump(comparison, f, indent=2, default=str)

with open(METRICS_DIR/"replay_divergence.json","w") as f:
    json.dump({
        "divergence":not hash_match,
        "off_hash":wal_off["ordering_hash"], "on_hash":wal_on["ordering_hash"],
        "off_events":wal_off["total_events"], "on_events":wal_on["total_events"],
        "off_lc":wal_off["lifecycle_counts"], "on_lc":wal_on["lifecycle_counts"],
        "ordering_preserved":hash_match,
    }, f, indent=2)

with open(METRICS_DIR/"lifecycle_diff.csv","w",newline="") as f:
    w = csv.writer(f)
    w.writerow(["metric","observer_off","observer_on","match"])
    for k in sorted(set(list(wal_off["lifecycle_counts"])+list(wal_on["lifecycle_counts"]))):
        off_v = wal_off["lifecycle_counts"].get(k,0)
        on_v  = wal_on["lifecycle_counts"].get(k,0)
        w.writerow([k, off_v, on_v, off_v==on_v])
    w.writerow(["total_events",wal_off["total_events"],wal_on["total_events"],wal_off["total_events"]==wal_on["total_events"]])
    w.writerow(["ordering_hash",wal_off["ordering_hash"],wal_on["ordering_hash"],hash_match])

with open(METRICS_DIR/"topology_diff.json","w") as f:
    json.dump({
        "topology_preserved":mc_match,
        "working_diff":mc_off["working"]-mc_on["working"],
        "episodic_diff":mc_off["episodic"]-mc_on["episodic"],
        "semantic_diff":mc_off["semantic"]-mc_on["semantic"],
        "archive_diff":mc_off["archive"]-mc_on["archive"],
        "off_state":mc_off, "on_state":mc_on,
    }, f, indent=2)

print(f"\n[Saved] All 4 output files to {METRICS_DIR}/")
