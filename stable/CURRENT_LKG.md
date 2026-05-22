# LKG — Last Known Good

## Current LKG

```
version: v0.19f
status: PRODUCTION
date: 2026-05-12
owner: Hermes-MCR
```

---

## Version Info

```
benchmark: v0.19f
verdict: PASS
source_file: semantic_governance_v19f.py
runtime_path: /home/minimak/mcr/stable/
```

---

## Benchmark Result

```
5/5 experiments PASS:

1. Boundary Enforcement: max_size + contamination_threshold → PASS
2. Reinforcement Lifecycle: reinforce → decay → archive → collapse → PASS
3. Validation Pass: min_co_activations + negative_evidence → PASS
4. Bridge Budget: active / dormant / archived layers → PASS
5. Latency Bounded: long-term latency < 10ms → PASS
```

---

## Bounded Status

```
✅ latency_bounded: true (< 10ms)
✅ active_bounded: true (<= 150 active bridges)
✅ contamination bounded: true
✅ bridge_count bounded: true
✅ no catastrophic drift: confirmed
```

---

## Governance Primitives

```
1. Boundary enforcement (max_size + contamination_threshold)
2. Reinforcement lifecycle (active → dormant → archived → collapsed)
3. Validation pass (min_co_activations + negative_evidence + context)
4. Bridge budget (active / dormant / archived layers)
5. Bridge GC (inactive + low_confidence + redundancy merge)
```

---

## Snapshot ID

```
benchmark_snapshot: v0.19f_verified
runtime_snapshot: semantic_governance_v19f
date: 2026-05-12
```

---

## Rollback Command

```bash
# If v0.19f runtime is needed:
cd /home/minimak/mcr/stable/
python semantic_governance_v19f.py

# If benchmark is needed:
# See: D:\AI\BENCHMARKS\MCR\v0.19f\
```

---

## Entry Point

```
main entry: /home/minimak/mcr/stable/semantic_governance_v19f.py
config: /home/minimak/mcr/stable/config.py
memory: /home/minimak/mcr/stable/memory.py
trace: /home/minimak/mcr/stable/memory_trace.py
```

---

## Known Issues

```
- Bridge saturation at extreme scale (not tested)
- Real-world vs synthetic dataset gap
- Negative evidence quality depends on context
```

---

## Linked Versions

```
linked_previous: v0.19d
linked_next: null (Research Stop Condition reached)
```

---

## Maintenance Mode

```
MCR v0.19f 已达到 Research Stop Condition。
进入 Maintenance Mode。

禁止:
- 扩 v0.20/v0.21
- 新增 semantic capability
- 修改 retrieval 主路径
- 直接在 stable/ 热修

仅允许:
- bug fix (需 PROPOSE MODE)
- observability
- benchmark rerun
- documentation
```
