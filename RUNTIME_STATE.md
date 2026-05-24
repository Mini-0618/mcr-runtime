# MCR Runtime State

## Current Runtime

```
active_version: v0.19f
status: MAINTENANCE_MODE
entry_point: ./stable/semantic_governance_v19f.py
LKG: VERIFIED
```

---

## Directory Structure

```
./
├── stable/              ← LKG v0.19f（当前生产版本）
│   ├── semantic_governance_v19f.py
│   ├── semantic_necessity_v19b.py
│   ├── semantic_formation_v19c.py
│   ├── semantic_stability_v19d.py
│   ├── config.py
│   ├── memory.py
│   ├── memory_trace.py
│   ├── loop.py
│   ├── event_system.py
│   ├── layered_memory.py
│   └── CURRENT_LKG.md
│
├── experimental/       ← 所有未验证实验
│   ├── semantic_governance_v19g.py    ← 禁止进入主线
│   ├── semantic_necessity_v19.py
│   ├── semantic_abstraction_v18.py
│   ├── semantic_diagnostic.py
│   ├── semantic_routing.py
│   ├── semantic_schema_adaptation.py
│   ├── semantic_schema_v15.py
│   ├── semantic_schema_v15b.py
│   ├── semantic_utility.py
│   ├── semantic_long_horizon.py
│   ├── chaos_experiment.py
│   └── debug_*.py
│
├── archive/            ← 历史冻结版本
│   ├── semantic_necessity_v17.py
│   ├── semantic_lesion_v16.py
│   ├── semantic_formation.py
│   ├── drift.py
│   ├── stability.py
│   ├── stability_test.py
│   ├── validate_stability.py
│   ├── analyze.py
│   ├── profile_memory.py
│   ├── benchmark_memory.py
│   └── long_run_benchmark.py
│
├── logs/               ← 运行日志和数据
│   ├── benchmark_results.json
│   ├── chaos_experiment_results.json
│   ├── stability_test_results.json
│   ├── drift_history.json
│   ├── event_queue.json
│   ├── memory_store.json
│   ├── world_state.json
│   ├── cognition_trace/
│   └── sem_exp/
│
├── docs/               ← 文档和工具
│   ├── observability.py
│   ├── patch_prefilter.py
│   └── world_state.py
│
├── benchmark/          ← benchmark相关（待用）
├── snapshots/          ← snapshot存储（待用）
└── docs/               ← 项目文档
```

---

## Current Benchmark Baseline

```
location: D:\AI\BENCHMARKS\MCR\v0.19f\
files:
  - benchmark.yaml
  - notes.md
  - results.json

verdict: PASS
5/5 experiments confirmed
bounded properties: verified
```

---

## Active Experiments

```
NONE

Reason: Research Stop Condition reached.
MCR v0.19f 进入 Maintenance Mode。
```

---

## Disabled / Stopped Experiments

```
v19g: 停止（semantic_governance_v19g.py）
  reason: Research Stop Condition
  location: experimental/

v20+: 未开始
  reason: Maintenance Mode
```

---

## Section 22 Violation Status

```
VIOLATION: FIXED ✅

Before: 所有文件堆在根目录
After: stable/experimental/archive 分离

Section 22 要求:
- stable/ = 当前可信 runtime ✅
- experimental/ = 所有新实验 ✅
- archive/ = 历史版本归档 ✅
- merge 需满足 7 个条件 ✅
```

---

## Research Stop Condition Status

```
STATUS: REACHED ✅

满足条件:
✅ bounded property 已验证（latency bounded）
✅ contamination bounded
✅ retrieval stable
✅ no catastrophic drift
✅ benchmark reproducible
✅ bridge count bounded

→ Maintenance Mode 生效
→ 禁止继续扩 semantic governance
```

---

## Rollback Availability

```
rollback: AVAILABLE ✅

LKG: v0.19f
snapshot: ./stable/CURRENT_LKG.md
benchmark: D:\AI\BENCHMARKS\MCR\v0.19f\

rollback command:
cd ./stable/
python semantic_governance_v19f.py
```

---

## Owner Review Required

```
No pending PROPOSAL.
No active research expansion.
System in Maintenance Mode.

Owner action required:
- ComfyUI 01_sdxl_basic verification (Windows side)
```
