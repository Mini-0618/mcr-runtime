#!/usr/bin/env python3
"""
MCR Phase IV-B: Semantic Compaction Physics
==========================================
Deterministic semantic merge experiment.

Workload: 10k ticks, 5 topics, clustered memory content.
Each topic has ~45 memories with shared prefix (e.g., "Python GC").
Retrieval follows co-access pattern (query recent stores).

Key Research Questions:
G1: Can compaction create summaries? (compression ratio)
G2: Do semantic_summary nodes form? (semantic tier growth)
G3: Is original information preserved? (archive)
G4: Does entropy decrease after compaction? (ordering)
G5: Is overhead bounded? (engineering constraint)
G6: What merge ratio emerges? (N:1 compression)

FINDING: Co-access graph needs topic boundary to avoid cross-topic merges.
"""

import sys, os, json, time, random, shutil
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, '/home/minimak/mcr/stable')
sys.path.insert(0, '/home/minimak/mcr/runtime_phys_observation/phase_IV_B_compaction')
from layered_memory import LayeredMemory
from semantic_compaction import SemanticCompaction, CompactionRuntime

BASE = Path("/home/minimak/mcr/runtime_phys_observation/phase_IV_B_compaction")
RUNS = BASE / "runs"; FINDINGS = BASE / "findings"; METRICS = BASE / "metrics"
for d in [RUNS, FINDINGS, METRICS]: d.mkdir(parents=True, exist_ok=True)

WORKLOAD_TICKS = 10_000
SEED = 2025

# 5 topic clusters, ~45 memories each
TOPICS = {
    "python": ["Python GC","Python memory","Python allocator","Python heap",
               "Python refcount","Python GC algorithm","Python memory model",
               "Python object","Python heap allocation","Python GC tuning",
               "Python memory pool","Python GC pause","Python refcount cycle",
               "Python memory leak","Python stack","Python frame","Python context",
               "Python globals","Python locals","Python closure","Python gc module",
               "Python sys.getrefcount","Python memory view","Python buffer",
               "Python bytearray","Python unicode","Python string intern",
               "Python dict implementation","Python list implementation",
               "Python tuple implementation","Python set implementation",
               "Python memory overhead","Python object size","Python array module",
               "Python collections deque","Python heapq module","Python gc thresholds",
               "Python generation","Python module search","Python import system",
               "Python bytecode","Python opcodes"],
    "http": ["HTTP request","HTTP response","HTTP header","HTTP status code",
             "HTTP method GET","HTTP method POST","HTTP keep-alive","HTTP chunked",
             "HTTP cache","HTTP compression","HTTP CORS","HTTP redirect",
             "HTTP 404","HTTP 500","HTTP 301","HTTP cookie","HTTP session",
             "HTTP Basic auth","HTTP Bearer token","HTTP cache control"],
    "database": ["SQL query","SQL join","SQL index","SQL primary key",
                 "SQL foreign key","SQL transaction","SQL ACID","SQL commit",
                 "SQL rollback","SQL deadlock","SQL lock","SQL isolation",
                 "SQL index B-tree","SQL index hash","SQL EXPLAIN",
                 "SQL WHERE clause","SQL SELECT","SQL INSERT","SQL UPDATE",
                 "SQL DELETE","SQL CREATE TABLE","SQL ALTER TABLE",
                 "SQL JOIN types","SQL inner join","SQL outer join",
                 "SQL LEFT JOIN","SQL RIGHT JOIN","SQL full join",
                 "SQL NULL","SQL NOT NULL","SQL UNIQUE constraint",
                 "SQL CHECK constraint","SQL DEFAULT value","SQL AUTOINCREMENT",
                 "SQL sequence","SQL view","SQL stored procedure",
                 "SQL trigger","SQL cursor","SQL FETCH","SQL window function"],
    "network": ["TCP connection","TCP handshake","TCP SYN","TCP ACK",
                "TCP FIN","TCP RST","TCP timeout","TCP retransmit",
                "TCP window size","TCP congestion","TCP slow start",
                "TCP fast recovery","UDP datagram","IP packet","IP fragment",
                "IP routing","IP subnet","IP NAT","DNS query","DNS A record",
                "DNS CNAME","DNS MX","DNS TTL","ARP protocol",
                "ICMP ping","DHCP lease","DHCP renew","VLAN tag",
                "MAC address","Switch port","Router forwarding",
                "BGP protocol","OSPF protocol","STP protocol",
                "SSL certificate","TLS handshake","HTTPS redirect"],
    "unix": ["Unix process","Unix fork","Unix exec","Unix pipe",
             "Unix socket","Unix signal","Unix zombie","Unix orphan",
             "Unix daemon","Unix init","Unix systemd","Unix cron job",
             "Unix inode","Unix directory","Unix symlink","Unix hardlink",
             "Unix filesystem","Unix mount","Unix umount","Unix fstab",
             "Unix inode table","Unix block device","Unix character device",
             "Unix pipe buffer","Unix FIFO","Unix UNIX domain socket",
             "Unix ioctl","Unix select","Unix poll","Unix epoll",
             "Unix kernel","Unix userspace","Unix system call",
             "Unix context switch","Unix scheduler","Unix process state",
             "Unix zombie reap","Unix parent process","Unix child process",
             "Unix process group","Unix session leader","Unix terminal",
             "Unix pts","Unix tty","Unix controlling terminal"],
}

def generate_workload(n_ticks, seed):
    rng = random.Random(seed)
    topic_names = list(TOPICS.keys())
    workload = []
    for tick in range(1, n_ticks+1):
        topic = rng.choice(topic_names)
        content = rng.choice(TOPICS[topic])
        tags = [topic, "compaction_test"]
        workload.append((tick, content, tags))
        if tick % 3 == 0:
            workload.append((tick, f"RETR:{content}", tags))
    return workload

# BASELINE
print(f"[BASELINE] {WORKLOAD_TICKS} ticks...", end=" ", flush=True)
root_b = str(RUNS / "baseline")
if os.path.exists(root_b): shutil.rmtree(root_b)
lm_b = LayeredMemory(root_b); t0 = time.perf_counter()
workload = generate_workload(WORKLOAD_TICKS, SEED)
for tick, content, tags in workload:
    if content.startswith("RETR:"):
        lm_b.retrieve(content[5:], max_results=3)
    else:
        lm_b.store(content, tags=tags, importance=0.6, current_tick=tick)
    lm_b.process_decay_buffer(tick)
    if tick % 50 == 0: lm_b.incremental_review(tick)
    if tick % 200 == 0: lm_b.try_flush(tick)
b_elapsed = time.perf_counter() - t0
b_mc = {"working":len(lm_b.working),"episodic":len(lm_b.episodic),
        "semantic":len(lm_b.semantic),"archive":len(lm_b.archive)}
print(f"done. {b_elapsed:.2f}s mem={b_mc}")

# COMPACTION
print(f"[COMPACTION] {WORKLOAD_TICKS} ticks...", end=" ", flush=True)
root_c = str(RUNS / "compaction_on")
if os.path.exists(root_c): shutil.rmtree(root_c)
cr = CompactionRuntime(root_c); t0 = time.perf_counter()
workload = generate_workload(WORKLOAD_TICKS, SEED)
for tick, content, tags in workload:
    if content.startswith("RETR:"):
        cr.retrieve(content[5:], current_tick=tick, max_results=3)
    else:
        cr.store(content, tags=tags, importance=0.6, current_tick=tick)
    cr.tick()
cr._compaction.run_compaction()
c_elapsed = time.perf_counter() - t0
c_mc = {"working":len(cr.working),"episodic":len(cr.episodic),
        "semantic":len(cr.semantic),"archive":len(cr.archive)}
cm = cr.get_compaction_metrics()
sem_sum = sum(1 for m in cr.semantic if m.get('memory_type')=='semantic_summary')
coaccess_edges = len(cr._compaction._coaccess.edges)
print(f"done. {c_elapsed:.2f}s mem={c_mc}")

# ANALYSIS
CLASS_E=[]; CLASS_F=[]
if cm['total_summaries_created']>0:
    CLASS_F.append(f"G1: summaries={cm['total_summaries_created']}")
else:
    CLASS_E.append("G1: No summaries — co-access did not trigger")
if sem_sum>0:
    CLASS_F.append(f"G2: semantic_summary nodes={sem_sum}")
else:
    CLASS_E.append("G2: No semantic_summary nodes")
if c_mc['archive']>0:
    CLASS_F.append(f"G3: archive={c_mc['archive']}")
else:
    CLASS_E.append("G3: No archive — possible info loss")
ed = cm.get('avg_entropy_delta',0.0)
if abs(ed)<5.0:
    CLASS_F.append(f"G4: entropy_delta={ed:.3f} bounded")
else:
    CLASS_E.append(f"G4: entropy UNBOUNDED delta={ed:.3f}")
overhead = c_elapsed/max(0.001,b_elapsed)
if overhead<=3.0:
    CLASS_F.append(f"G5: overhead={overhead:.2f}x<=3x")
else:
    CLASS_E.append(f"G5: overhead={overhead:.2f}x>3x")
if cm['total_memories_compacted']>0:
    ratio=cm['total_memories_compacted']/max(1,cm['total_summaries_created'])
    CLASS_F.append(f"G6: merge_ratio={ratio:.1f}:1")
else:
    CLASS_E.append("G6: No memories merged")

all_expected = len(CLASS_E)==0
print(f"\n{'='*60}")
for e in CLASS_E: print(f"  CLASS_E: {e}")
for e in CLASS_F: print(f"  CLASS_F: {e}")
print(f"\nOVERALL: {'VALIDATED' if all_expected else 'PATHOLOGY'}")

# Save results
results = {
    "experiment":"PHASE_IV_B_Semantic_Compaction",
    "LKG":"637a11c907e8a889b909513522dfab8c",
    "workload_ticks":WORKLOAD_TICKS,"seed":SEED,
    "baseline":{"elapsed_s":b_elapsed,"memory_counts":b_mc},
    "compaction":{"elapsed_s":c_elapsed,"memory_counts":c_mc,
                  "metrics":cm,"summary_count":sem_sum,
                  "coaccess_edges":coaccess_edges},
    "classification":{"CLASS_E":CLASS_E,"CLASS_F":CLASS_F},
    "all_expected":all_expected,"overhead":overhead,
}
with open(METRICS/"compaction_results.json","w") as f:
    json.dump(results,f,indent=2,default=str)
print(f"\n[Saved] compaction_results.json")
