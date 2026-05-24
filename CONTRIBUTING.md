# Contributing to MCR

MCR（Memory-Augmented Cognitive Runtime）是一个正在公开验证的 runtime research system。感谢你的兴趣，欢迎所有形式的贡献。

## 贡献类型

- Bug 报告
- 功能提议
- 文档改进
- 代码贡献
- 研究复现 / Benchmark

---

## 开发环境

### 依赖

- Python: 3.10+
- 无第三方依赖（测试框架仅使用 Python stdlib）

### 快速验证

```bash
# 克隆后立即验证
python3 tests/test_g2_replay.py
python3 tests/test_event_gate.py
```

两条全部 PASS 才能提交 PR。

---

## 分支规范

```
main          # 稳定分支，生产级代码
├── stable/   # 已验证的稳定模块
├── runtime/  # 新架构（G2 Event-Sourced Kernel）
├── observability/   # 可观察性模块
└── experimental/   # 实验性代码，未经验证
```

**不要向 `experimental/` 和 `archive/` 提交新代码。**

### 分支命名

```
feature/xxx          # 新功能
fix/xxx              # Bug 修复
docs/xxx             # 文档更新
refactor/xxx         # 代码重构
benchmark/xxx        # Benchmark 相关
```

---

## 开发流程

### 1. 创建分支

```bash
git checkout main
git pull origin main
git checkout -b feature/your-feature-name
```

### 2. 编写代码

- 遵循现有代码风格（Python stdlib，无外部类型检查工具）
- 不要引入新的第三方依赖
- 涉及 WAL/state 变化的逻辑，同步更新 `reducer` 和 `event_gate`
- 涉及 G2 正确性：`python3 tests/test_g2_replay.py` 必须 PASS

### 3. 运行测试

```bash
python3 tests/test_g2_replay.py
python3 tests/test_event_gate.py
```

两个都 PASS 后才能提交。

### 4. 提交规范

```
<type>(<scope>): <subject>

[body]
```

**Type：**
- `feat` — 新功能
- `fix` — Bug 修复
- `docs` — 文档
- `refactor` — 重构（无行为变化）
- `perf` — 性能优化
- `test` — 测试
- `chore` — 构建/工具

**Scope（可选）：**
- `layered_memory` — layered_memory.py 相关
- `event_gate` — event_gate.py 相关
- `wal` — WAL/replay 相关
- `benchmark` — benchmark 相关

**示例：**

```
feat(layered_memory): add set_max_working() for dynamic W adjustment

fix(event_gate): reject None memory_id cleanly without TypeError

docs(benchmark): add W=10/5/3 stress test results
```

### 5. Push 并创建 PR

```bash
git push origin feature/your-feature-name
```

在 GitHub 创建 Pull Request，描述：
- 这个 PR 解决什么问题
- 涉及哪些文件
- 测试结果

---

## 模块负责人

| 领域 | 主要联系人 | 备份 |
|------|-----------|------|
| G2 Event-Sourced Kernel / WAL | @Mini-0618 | — |
| layered_memory / eviction | @Mini-0618 | — |
| EventGate / HermesBridge | @Mini-0618 | — |
| Benchmark / Stress Test | @Mini-0618 | — |
| 可观察性 / Memory Trace | @Mini-0618 | — |

---

## 重要原则

### 不要破坏 G2 正确性

MCR 的核心不变量：

```
runtime_state == replay(WAL)
```

每次修改涉及 WAL 或 state reducer 时，运行 `test_g2_replay.py` 验证。

### 不要修改 LKG Snapshot

LKG（Last Known Good）是经过验证的稳定快照，任何修改需要单独 benchmark 证明不降低 bounded latency。

当前 LKG：`snapshot_v19g_pass/`，Hash：`637a11c907e8a889b909513522dfab8c`

### 不要向 stable/ 目录提交未经验证的代码

stable/ 目录是冻结区，所有进入 stable/ 的代码必须：
1. 通过 `test_g2_replay.py` 和 `test_event_gate.py`
2. 有对应的 benchmark 数据
3. 有更新后的 `SNAPSHOT_DISCIPLINE.md` 记录

---

## 问题报告

Bug 报告请包含：

1. 复现步骤（最小可复现用例）
2. 期望行为 vs 实际行为
3. `tests/test_g2_replay.py` 是否 PASS
4. 如果涉及性能退化：benchmark 数据

功能提议请包含：
1. 解决了什么问题
2. 提议方案
3. 对 bounded latency 的影响（是否有分析）

---

## 代码风格

- 行宽：100 字符
- 缩进：4 空格
- 字符串：双引号
- 类型提示：鼓励使用（非强制）
- Docstring：公共 API 需要（1-2 行）

---

## 提问

不确定模块归属？先在 issue 里描述用例和影响行为，maintainer 会路由。
