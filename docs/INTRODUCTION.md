# MCR 是什么 / What Is MCR

MCR — Memory-Augmented Cognitive Runtime — 是一个**事件驱动的持久化运行时**，专为长周期 AI Agent 设计。

它的核心职责：在 AI Agent 长期运行的过程中，保证**状态不丢失、检索 latency 有上界、任意时刻可以恢复到过去某个状态**。

---

## 解决什么问题

### 问题 1：检索延迟无上界

大多数 AI Agent 的 memory 是一个 flat list。随着运行时间变长，每次检索都要扫描整个 list，延迟线性增长。

MCR 的解法：分层 memory（working / episodic / semantic / archive），每个层都有硬上限。检索只扫这三个层，复杂度是 O(W+CAP+K)，和 Agent 运行时间 T 完全无关。

### 问题 2：状态不知道从哪里来的

当 Agent "忘记"了某个 memory，开发者无法追溯：是谁覆盖的？什么时候被驱逐的？被什么事件触发的？

MCR 的解法：WAL（Write-Ahead Log）+ G2 replay verification。**每一次状态变更都是一条 event 记录**。你可以随时重放 WAL，恢复到任意 tick 的状态。

### 问题 3：不知道运行时状态对不对

Agent 在生产环境崩溃了，重启后内存是空的。没有办法验证"重启后的状态和崩溃前是否一致"。

MCR 的解法：G2 deterministic replay。重启时用 WAL 重放所有事件，比较重放后的 state hash 和崩溃前的 hash。match = 状态完整，mismatch = 有东西丢了。

---

## 为什么需要 Replay Verification

```
崩溃前：          WAL（1, 2, 3, 4, 5 events）
重启后重放：      WAL → replay() → state_hash
                 state_hash == 崩溃前 hash？
```

Replay verification 回答的是：**你的状态真的没丢吗？**

这对于需要 24/7 运行的 AI Agent 至关重要——而不是靠"我觉得没问题"来判断。

---

## MCR 当前不是什么

- **不是 AGI**：不涉及通用智能、自我意识、涌现能力
- **不是 production-ready agent framework**：没有真实 LLM 集成、没有部署方案、没有监控告警
- **不是通用记忆库**：不是 vector DB + RAG 的替代品，不做语义相似性检索
- **不承诺 semantic 层自动激活**：当前 semantic promotion 需要显式 trigger

---

## MCR 适合谁

- 对 event sourcing 在 AI Agent 场景中的应用感兴趣的研究者
- 想构建 bounded-latency memory 子系统的 runtime 开发者
- 想理解 WAL + replay 如何保证状态可恢复性的系统工程师

---

## 快速开始

```bash
git clone https://github.com/Mini-0618/mcr-runtime
cd mcr-runtime
python3 examples/quickstart.py
python3 examples/replay_verification_demo.py
```

两个 demo 跑完，你就理解了 MCR 的核心保证。