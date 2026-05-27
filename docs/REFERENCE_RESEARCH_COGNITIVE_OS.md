# MCR Cognitive OS — Reference Research

开源项目调研报告，为 MCR Cognitive OS / Operator / SocialOps 提供设计参考。

调研日期：2026-05-27

---

## 1. AutoGPT

- **GitHub:** https://github.com/Significant-Gravitas/AutoGPT
- **License:** MIT（核心）+ Polyform Shield（平台部分）
- **Stars:** 170k+

### 解决什么问题

自主 AI Agent 平台——创建、部署、管理持续运行的 AI 工作流。提供可视化低代码界面构建 Agent。

### 架构亮点

- **Agent Builder:** 低代码界面，连接功能块构建 Agent
- **Agent Server:** 运行时环境，支持外部触发和持续运行
- **Agent Protocol:** 标准化 Agent 通信协议（AI Engineer Foundation 标准）
- **Forge:** 开发者工具包，提供 Agent 框架样板
- **Marketplace:** 预构建 Agent 市场

### MCR 可借鉴

- **Agent Protocol 标准化通信** — MCR 的 Agent 间通信可以参考这个协议
- **模块化功能块设计** — 每个块做一件事，MCR 的认知模块已经是这个思路
- **持续运行 + 外部触发** — MCR-Auto 的目标就是这个

### MCR 不应照搬

- Polyform Shield 许可证限制商业竞争使用
- 低代码可视化不是 MCR 当前需求
- Docker 部署架构对 MCR 过重

### 是否适合进入 MCR

设计思想可借鉴，代码不直接引入。

**推荐优先级：MEDIUM**

---

## 2. LangGraph

- **GitHub:** https://github.com/langchain-ai/langgraph
- **License:** MIT
- **Stars:** 10k+

### 解决什么问题

低层级 Agent 编排框架——用图（状态机）构建长时运行、有状态的 AI Agent。

### 架构亮点

- **图状态机:** 节点 = 动作/函数，边 = 状态转换
- **持久执行:** Agent 可在故障后从检查点恢复
- **Human-in-the-loop:** 执行中途可检查和修改 Agent 状态
- **双层记忆:** 短期工作记忆 + 长期持久记忆
- **灵感来源:** Pregel + Apache Beam 的顶点中心计算模型

### MCR 可借鉴

- **状态机驱动的 Agent 循环** — MCR Cognitive OS 的感知→判断→行动→反思就是一个状态机
- **检查点恢复机制** — MCR 的 WAL + Replay Verification 已经有类似能力，可以进一步利用
- **Human-in-the-loop 设计** — ASK_OWNER 机制的扩展版

### MCR 不应照搬

- LangGraph 依赖 LangChain 生态，MCR 应保持独立
- 图可视化对 MCR 当前阶段过重
- 分布式运行时不是当前需求

### 是否适合进入 MCR

状态机设计思想高度契合 MCR。

**推荐优先级：HIGH**

---

## 3. Letta (formerly MemGPT)

- **GitHub:** https://github.com/letta-ai/letta
- **License:** Apache 2.0
- **Stars:** 15k+

### 解决什么问题

为 LLM 构建高级记忆系统——Agent 能学习并随时间自我改进。

### 架构亮点

- **Memory Blocks:** 标签化的持久存储块（如 `human` 存用户信息，`persona` 存 Agent 身份）
- **自我改进:** Agent 可以跨会话保留和更新记忆
- **持续学习:** 预构建的 skills/subagents 支持高级记忆和持续学习
- **有状态 Agent:** Agent 状态（包括记忆）在会话间持久化
- **虚拟上下文管理:** 受操作系统启发，把 LLM 上下文窗口当有限内存，用分页/换入换出技术

### MCR 可借鉴

- **Memory Block 设计** — MCR 的分层记忆（episodic/semantic/working/archive）可以参考这种标签化块设计
- **自我改进机制** — MCR 的 Memory Evolution (Stage 6) 正是这个方向
- **Persona Block** — MCR 的 Policy Engine 可以借鉴，作为 Agent 的"人格"边界
- **虚拟上下文管理** — 对 MCR 的 token 预算控制有参考价值

### MCR 不应照搬

- Apache 2.0 许可证兼容，但不应大段复制
- Letta 的商业化 API 层不是 MCR 需要的
- 其记忆模型比 MCR 更复杂，当前阶段不需要

### 是否适合进入 MCR

记忆系统设计高度相关。

**推荐优先级：HIGH**

---

## 4. browser-use

- **GitHub:** https://github.com/browser-use/browser-use
- **License:** MIT
- **Stars:** 60k+

### 解决什么问题

AI 驱动的浏览器自动化——让 LLM Agent 自主操作浏览器完成任务。

### 架构亮点

- **Agent + Browser 配对:** LLM Agent 控制 Playwright 浏览器实例
- **自然语言任务:** 用户描述任务，Agent 自动导航、点击、输入
- **多 LLM 支持:** OpenAI, Anthropic, Gemini, Ollama
- **CLI 持久会话:** 浏览器在命令间保持运行
- **视觉能力:** 截图让 AI 理解页面状态
- **自定义工具:** `@Tools` 装饰器扩展 Agent 能力

### MCR 可借鉴

- **自然语言→浏览器操作的转换** — MCR Operator (Stage 4) 的核心能力
- **CLI 持久会话模式** — MCR 可以保持浏览器会话跨任务复用
- **截图理解页面** — 作为 MCR Perception 的输入源
- **元素索引交互** — `click 5` 这种简洁交互方式

### MCR 不应照搬

- 依赖 Playwright 和 LangChain，MCR 应考虑更轻量方案
- 云浏览器服务不是 MCR 需要的
- 代理/指纹/CAPTCHA 绕过功能有伦理风险

### 是否适合进入 MCR

浏览器操作是 Stage 4 的核心参考。

**推荐优先级：HIGH**

---

## 5. AutoGen (Microsoft)

- **GitHub:** https://github.com/microsoft/autogen
- **License:** MIT
- **Stars:** 40k+

### 解决什么问题

多 Agent AI 应用框架——Agent 间对话协作，支持自主运行或与人类协作。

### 架构亮点

- **分层设计:** Core API（消息传递）→ AgentChat API（快速原型）→ Extensions API
- **多 Agent 模式:** 单 Agent、双 Agent 对话、群聊、嵌套聊天
- **MCP 集成:** 通过 Model Context Protocol 连接外部工具服务器
- **AgentTool 模式:** 专家 Agent 包装成工具，由通用 Agent 路由
- **Magentic-One:** 真实多 Agent 团队示例（浏览、代码执行、文件处理）

### MCR 可借鉴

- **Agent-as-Tool 模式** — MCR 可以把专项能力（browser、social、memory）包装成工具
- **MCP 协议集成** — 标准化的工具连接方式
- **分层 API 设计** — Core 层最小化，上层按需扩展

### MCR 不应照搬

- 已进入维护模式，Microsoft 转向 MAF
- 群聊模式对 MCR 过重
- .NET 跨语言支持不是 MCR 需要的

### 是否适合进入 MCR

Agent-as-Tool 和 MCP 思想可借鉴。

**推荐优先级：MEDIUM**

---

## 6. CrewAI

- **GitHub:** https://github.com/crewAIInc/crewAI
- **License:** MIT
- **Stars:** 25k+

### 解决什么问题

角色扮演多 Agent 编排——Agent 以角色协作，支持顺序/层级/事件驱动流程。

### 架构亮点

- **Crews:** 角色化 Agent 团队，可动态委派任务
- **Flows:** 事件驱动工作流，精确控制复杂自动化
- **编排模式:** 顺序、层级（自动分配管理者）、事件路由
- **装饰器触发:** `@start`, `@listen`, `@router` + 逻辑运算符
- **独立框架:** 不依赖 LangChain，从零构建

### MCR 可借鉴

- **角色化 Agent 设计** — MCR 的认知模块可以有"角色"（Perceiver, Thinker, Executor）
- **层级编排 + 自动管理者** — MCR SocialOps 可能需要这种模式
- **事件驱动路由** — 条件分支决定下一步，MCR 的 Policy Engine 可以扩展
- **Crew + Flow 组合** — 自主性 + 确定性控制的平衡

### MCR 不应照搬

- 角色 backstory 对 MCR 过于"拟人"
- 企业版 (AMP) 不是 MCR 需要的
- 100k 开发者认证课程与 MCR 无关

### 是否适合进入 MCR

事件驱动路由和角色化设计有参考价值。

**推荐优先级：MEDIUM**

---

## 综合对比

| 项目 | License | Agent Loop | Memory | Browser | Multi-Agent | MCR 适配 |
|------|---------|------------|--------|---------|-------------|----------|
| AutoGPT | MIT+Polyform | 有 | 弱 | 无 | 无 | 中 |
| LangGraph | MIT | **强** | 有 | 无 | 有 | **高** |
| Letta | Apache 2.0 | 有 | **强** | 无 | 无 | **高** |
| browser-use | MIT | 有 | 无 | **强** | 无 | **高** |
| AutoGen | MIT | 有 | 弱 | 有(MCP) | **强** | 中 |
| CrewAI | MIT | 有 | 弱 | 无 | **强** | 中 |

## MCR 路线对应

| MCR Stage | 主要参考 | 借鉴点 |
|-----------|---------|--------|
| Stage 3: Cognitive OS | LangGraph, Letta | 状态机循环、Memory Block、Persona |
| Stage 4: Operator | browser-use | 浏览器自动化、截图理解、元素交互 |
| Stage 5: SocialOps | CrewAI, AutoGen | 角色化 Agent、事件路由、Agent-as-Tool |
| Stage 6: Memory Evolution | Letta | 自我改进、持续学习、虚拟上下文管理 |

## 许可证兼容性

| License | MCR 可用 | 说明 |
|---------|---------|------|
| MIT | 是 | 自由使用，保留声明 |
| Apache 2.0 | 是 | 自由使用，保留声明，注明修改 |
| Polyform Shield | 否 | 限制竞争性使用 |
| GPL/AGPL | 否 | 未在本次调研中出现 |

## 建议

1. **优先学习 LangGraph 的状态机设计** — 直接应用到 MCR Cognitive OS 的循环架构
2. **参考 Letta 的 Memory Block** — 改进 MCR 的分层记忆系统
3. **Stage 4 时深入研究 browser-use** — 浏览器操作是 Operator 的核心
4. **不引入任何大型依赖** — 只提炼设计思想，MCR 保持轻量
5. **所有参考必须注明来源** — 如有极少量代码借鉴，写明出处和 license
