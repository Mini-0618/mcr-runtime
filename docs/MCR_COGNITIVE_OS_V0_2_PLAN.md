# MCR Cognitive OS v0.2 — Design Translation Plan

将外部开源项目经验翻译为 MCR 自己的下一阶段设计。

不引入依赖，不复制代码，只借鉴思想。

---

## v0.2 目标

在 v0.1（单次认知循环）基础上，实现三个核心改进：

1. **状态机驱动的可中断循环** — 借鉴 LangGraph
2. **结构化记忆块 + 人格边界** — 借鉴 Letta/MemGPT
3. **浏览器操作预留接口** — 借鉴 browser-use（仅设计，不实现）

---

## 1. 从 LangGraph 借鉴：状态机式认知循环

### LangGraph 的做法

- 图节点 = 动作函数，边 = 状态转换
- 检查点持久化，故障后可恢复
- Human-in-the-loop：执行中途可暂停等待人类输入

### MCR v0.2 翻译

**不引入 LangGraph 依赖。** 用 Python 原生实现状态机。

```text
v0.1 循环：
  感知 → 注意力 → 评分 → 策略 → 规划 → 行动 → 反思 → 写记忆
  （线性，单次，不可中断）

v0.2 循环：
  IDLE → PERCEIVE → ATTEND → SCORE → [CHECKPOINT]
    → POLICY → PLAN → [ASK_OWNER?]
    → ACT → REFLECT → [CHECKPOINT]
    → WRITE_MEMORY → VERIFY → IDLE
```

关键改动：

- **CHECKPOINT 状态**：每步执行后写检查点到 WAL，中断后可从检查点恢复
- **ASK_OWNER 暂停点**：遇到 requires_owner 任务时暂停循环，等待人类决策
- **状态转换表**：用 dict 定义合法状态转换，非法转换抛异常
- **回放兼容**：状态机每次转换都写入 WAL，Replay Verifier 可验证完整循环

### v0.2 最小实现

```python
# 状态定义
STATES = ["IDLE", "PERCEIVE", "ATTEND", "SCORE", "POLICY", "PLAN", "ACT", "REFLECT", "WRITE_MEMORY", "VERIFY"]

# 转换表
TRANSITIONS = {
    "IDLE": ["PERCEIVE"],
    "PERCEIVE": ["ATTEND"],
    "ATTEND": ["SCORE"],
    "SCORE": ["POLICY"],
    "POLICY": ["PLAN", "ASK_OWNER"],  # 分支：需要 Owner
    "PLAN": ["ACT"],
    "ACT": ["REFLECT"],
    "REFLECT": ["WRITE_MEMORY"],
    "WRITE_MEMORY": ["VERIFY"],
    "VERIFY": ["IDLE"],
    "ASK_OWNER": ["PLAN", "IDLE"],  # Owner 决策后继续或终止
}
```

---

## 2. 从 Letta/MemGPT 借鉴：Memory Block + Persona

### Letta 的做法

- Memory Block：标签化持久存储（human, persona）
- 虚拟上下文管理：把 LLM 上下文当有限内存，分页/换入换出
- 自我改进：Agent 跨会话保留和更新记忆

### MCR v0.2 翻译

**不引入 Letta 依赖。** 扩展 MCR 现有的分层记忆。

**Memory Block 设计：**

```text
MCR Memory Blocks:
  persona    — Agent 的身份、边界、价值观（只读，由 Owner 设定）
  context    — 当前任务上下文（工作记忆，每轮更新）
  knowledge  — 学到的知识和经验（长期记忆，跨会话）
  episodic   — 事件记录（MCR Runtime 已有）
```

**Persona Block：**

```text
persona = {
    "name": "MCR Cognitive OS",
    "role": "认知判断层",
    "boundaries": [
        "不自行决定高风险操作",
        "不绕过 Owner 批准",
        "不修改 Runtime 核心",
        "不联网执行未知代码",
    ],
    "values": [
        "安全优先",
        "可验证性",
        "最小惊讶原则",
    ],
}
```

**与 MCR Runtime 集成：**

- persona 存为 `memory_store` 事件，tier = "semantic"，不可 purge
- context 每轮覆盖，tier = "working"
- knowledge 累积，tier = "episodic"，通过 coaccess 关联
- 所有 Memory Block 操作走 WAL，Replay Verifier 可验证

### v0.2 最小实现

- 新增 `persona_engine.py`：管理 persona block 的读取和约束检查
- Policy Engine 增加 persona 边界检查：任务是否违反 persona 的 boundaries
- Memory Writer 增加 block 类型区分

---

## 3. 从 browser-use 借鉴：浏览器操作预留接口

### browser-use 的做法

- LLM Agent 控制 Playwright 浏览器
- 截图理解页面状态
- 元素索引交互（click 5, type "hello"）
- CLI 持久会话

### MCR v0.2 翻译

**不引入 browser-use 依赖，不实现浏览器操作。** 只设计接口。

**Operator Interface 设计：**

```text
MCR Operator (Stage 4, 未来):

class BrowserOperator:
    def observe() -> PageState      # 截图 + 可交互元素列表
    def click(index: int) -> Result  # 点击第 N 个元素
    def type(index: int, text: str) -> Result  # 输入文字
    def navigate(url: str) -> Result  # 跳转
    def screenshot() -> bytes        # 截图

class PageState:
    url: str
    title: str
    elements: List[InteractiveElement]  # 可交互元素
    screenshot: bytes
```

**v0.2 只做：**

- 定义 `BrowserOperator` 接口（抽象基类）
- 定义 `PageState` 数据结构
- 实现 `MockBrowserOperator`（返回假数据，用于测试）
- Cognitive OS 的 Action 模块增加 `browser_action` 类型

**v0.2 不做：**

- 不引入 Playwright
- 不真实控制浏览器
- 不联网
- 不登录任何网站

---

## 哪些不引入依赖

| 项目 | 引入依赖？ | 原因 |
|------|-----------|------|
| LangGraph | 否 | 只借鉴状态机思想，Python 原生实现 |
| Letta | 否 | 只借鉴 Memory Block 设计，扩展 MCR 现有记忆 |
| browser-use | 否 | 只定义接口，Stage 4 才实现 |
| AutoGPT | 否 | 不适用当前阶段 |
| AutoGen | 否 | 不适用当前阶段 |
| CrewAI | 否 | 不适用当前阶段 |

## 哪些只借鉴思想

- 状态机循环 → MCR 自己的状态转换表
- Memory Block → MCR 的 persona/context/knowledge 分块
- Persona 边界 → MCR 的 Policy Engine 扩展
- 浏览器接口 → MCR 的 MockBrowserOperator
- 检查点恢复 → MCR 的 WAL 已有类似能力，增强即可

## 进入 MCR Cognitive OS 的部分

1. 状态机驱动循环（v0.2 核心）
2. Persona Engine（v0.2）
3. Memory Block 分层（v0.2）
4. ASK_OWNER 暂停点（v0.2）
5. 检查点恢复（v0.2）

## 留给 MCR Operator 的部分

1. 真实浏览器控制（Stage 4）
2. 截图理解（Stage 4）
3. 网页元素交互（Stage 4）
4. 社交媒体操作（Stage 5）

## v0.2 最小实现边界

**必须实现：**
- `state_machine.py` — 状态机引擎
- `persona_engine.py` — Persona 管理
- `checkpoint.py` — 检查点写入/恢复
- 更新 `run_cognitive_loop.py` — 改为状态机驱动
- 更新 `policy_engine.py` — 增加 persona 边界检查
- 更新测试

**不实现：**
- 真实浏览器操作
- 网络请求
- 多 Agent 协作
- 长期自我改进

## 风险与禁止事项

| 风险 | 缓解 |
|------|------|
| 状态机过复杂 | 限制状态数 ≤ 10 |
| Persona 边界过松 | Owner 必须审核 persona 定义 |
| 检查点性能 | 每步写 WAL，已验证性能可接受 |
| 浏览器接口诱惑 | v0.2 只有 Mock，Stage 4 才真实实现 |

**绝对禁止：**
- 不引入外部依赖
- 不复制外部代码
- 不改 Runtime 核心
- 不联网
- 不真实控制浏览器
- 不自动 push/tag/release
