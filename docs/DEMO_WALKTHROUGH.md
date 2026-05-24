# Demo Walkthrough — 逐行解释 quickstart.py 输出

运行 `python3 examples/quickstart.py`，你会看到五段输出。以下是每一段的含义。

---

## [1] Create runtime

```
[1] Create runtime...
  tick=0, memory items=0
  ✓ Runtime created
```

这是初始状态。MCRRuntimeEngine 创建了一个空运行时：
- `tick = 0`（还没发生任何事件）
- `memory items = 0`（没有任何 memory）
- WAL 文件路径：`/tmp/mcr_quickstart_wal.jsonl`

此时引擎内部有两样东西：
- `state`：当前运行时状态
- `wal`：Write-Ahead Log，持久化到磁盘

---

## [2] Append memory events

```
[2] Append memory events...
  tick=1  memory_store      memory_id=mem-alpha
  tick=2  memory_store      memory_id=mem-beta
  tick=3  memory_store      memory_id=mem-gamma
  tick=4  memory_access     memory_id=mem-alpha
  tick=5  memory_access     memory_id=mem-beta
  ✓ 5 events emitted
```

每次调用 `engine.emit()` 会：
1. 生成一个 Event（带 event_id、tick、timestamp）
2. 通过 Reducer 更新 state
3. 写入 WAL

`tick` 是单调递增的事件计数器，每个 emit 使 tick + 1。

两种事件类型：
- `memory_store`：把一个 memory item 写入 state
- `memory_access`：记录某 memory 被访问了（用于 coaccess graph 构建）

---

## [3] Inspect current state

```
[3] Inspect current state...
  tick:          5
  memory items:  3
  WAL length:    5
  access_history:2
  coaccess_graph:0 nodes
  state hash:    87f9ab98d4766396...
    mem-alpha: tier=episodic, created_tick=1
    mem-beta: tier=episodic, created_tick=2
    mem-gamma: tier=episodic, created_tick=3
```

当前状态快照：
- 5 个 tick 已执行（5 个事件）
- 3 个 memory items 存储在 state 中
- WAL 中有 5 条 event 记录
- access_history 有 2 条（两次 access，alpha 和 beta）
- coaccess_graph 节点数为 0——因为 alpha 和 beta 虽然属于同一 coaccess_group_id，但它们在不同的 tick 被访问（tick=4 和 tick=5），coaccess graph 只记录同一 tick 内共同访问的 items

`state hash` 是对当前状态的确定性摘要。任何状态变化都会导致 hash 变化。

---

## [4] Replay WAL

```
[4] Replay WAL from initial state...
  replayed tick:          5
  replayed memory items:  3
  replayed access_history:2
  replayed state hash:    87f9ab98d4766396...
  ✓ WAL replayed
```

这里做了一件关键的事：**从空状态（tick=0）出发，把 WAL 里的 5 条 event 全部重放一遍**。

重放后的状态和原始状态完全一致：
- tick = 5
- memory items = 3
- access_history = 2
- state hash = 相同

这说明：给定同样的初始状态和同样的 WAL， deterministic reducer 每次都会产生同样的结果。

---

## [5] Verify G2 consistency

```
[5] Verify G2 consistency (original == replayed)...
  runtime hash:   87f9ab98d4766396...
  replay hash:    87f9ab98d4766396...
  WAL event count:5
  WAL hash:       1e8be6d30494b1f2...

  ✓ G2 VERIFICATION PASSED
  Runtime state == Replayed state (deterministic replay confirmed)
```

G2 verification 是 MCR 的核心保证机制：

```
runtime hash    == replay hash   →  状态在 WAL 重放后一致 → OK
runtime hash    != replay hash  →  状态丢失或被破坏     → FAIL
```

`WAL hash` 是 WAL 本身内容的指纹（独立于 state）。如果 WAL 内容被篡改（例如手动删了一条 event），WAL hash 会变化。

这回答了：**如果 Agent 崩溃了，重启后 WAL 重放能恢复到正确的状态吗？**

PASS = 能。FAIL = 不能。

---

## 总结：quickstart 演示了什么

| 输出段落 | 含义 |
|---------|------|
| [1] | 创建空运行时 |
| [2] | 发射 5 个事件，每次 tick + 1 |
| [3] | 查看当前状态（3 items, 5 WAL events） |
| [4] | 从空状态重放 WAL |
| [5] | 验证重放状态 == 运行时状态 |

如果 [5] 显示 FAIL，说明 WAL 或 Reducer 有问题。如果显示 PASS，说明 event sourcing 系统是确定性的—— WAL 是状态的唯一真源（Single Source of Truth）。