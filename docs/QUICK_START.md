# MCR 快速上手

## 环境要求

- Python: 3.10+
- 无第三方依赖
- 无数据库、无外部服务

## 一分钟跑起来

```bash
# 克隆
git clone https://github.com/Mini-0618/mcr-runtime.git
cd mcr-runtime

# 运行测试
python3 tests/test_g2_replay.py
python3 tests/test_event_gate.py

# 运行 stress test（W=10→5→3）
python3 runtime_phys_observation/run_stress_10k.py

# 运行 naive baseline 对比
python3 runtime_phys_observation/run_baseline_naive.py
```

---

## 目录结构

```
mcr/
├── stable/              # 已冻结的稳定模块
├── runtime/             # G2 Event-Sourced Kernel
├── observability/       # memory_trace.py 可观察性层
├── experimental/         # 活跃实验代码
├── tests/               # G2 正确性测试（仅 stdlib）
├── runtime_phys_observation/   # Benchmark 脚本
├── docs/                # 架构文档
├── papers/              # 论文草稿
└── snapshot_v19g_pass/  # LKG 快照
```

详细说明：[docs/DIRECTORY_STRUCTURE.md](DIRECTORY_STRUCTURE.md)

---

## 核心模块

| 模块 | 文件 | 作用 |
|------|------|------|
| G2 Kernel | `runtime/` | Event-Sourced WAL + Replay |
| Memory | `stable/layered_memory.py` | 3层记忆架构 |
| EventGate | `runtime/event_gate.py` | 事件校验 |
| HermesBridge | `runtime/hermes_bridge.py` | LLM→结构化事件 |
| Observability | `observability/memory_trace.py` | 5类 trace |
| Benchmark | `runtime_phys_observation/` | Stress/Naive/Physics |

---

## 已有 benchmark 结果

**Naive Baseline（无驱逐）**：
```
late/early latency ratio: 31.032x（10k ticks）
```

**MCR Stress Test（W 收缩）**：
```
W=10:  1.072x bounded
W=5:   1.672x bounded（含 semantic overhead）
W=3:   1.124x bounded（含 semantic overhead）
```

详见：[papers/neurips2025_workshop/](papers/neurips2025_workshop/)

---

## 下一步

- 想了解架构：先读 [docs/ARCHITECTURE_MAP.md](ARCHITECTURE_MAP.md)
- 想开始开发：先读 [CONTRIBUTING.md](../CONTRIBUTING.md)
- 想运行长测：看 [docs/RUN_REPRODUCIBILITY.md](RUN_REPRODUCIBILITY.md)
- 想了解 bounded 性质：看 [docs/BOUNDED_PROPERTY.md](BOUNDED_PROPERTY.md)
