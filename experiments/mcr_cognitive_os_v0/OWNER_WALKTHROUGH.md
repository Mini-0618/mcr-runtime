# MCR Cognitive OS v0.1 — Owner 说明文档

## 这是什么？

MCR 的"初级脑子"实验层。它在 Runtime（记忆系统）之上，加了一层**认知判断系统**——能筛选任务、判断风险、选择下一步，并把结果写回记忆。

## 解决什么问题？

Runtime 会"记住"，Auto 会"跑闭环"，但缺少"判断"：哪些事该做？哪些不该做？下一步干什么？

Cognitive OS 就是补这一层。

## 文件说明

| 文件 | 功能 |
|------|------|
| `state_reader.py` | 感知：读取当前任务状态 |
| `attention_filter.py` | 注意力：按紧急度过滤任务 |
| `task_scorer.py` | 评分：给任务打分（优先级/风险/成本） |
| `goal_manager.py` | 目标：管理当前目标 |
| `policy_engine.py` | 策略：阻止危险任务，标记需批准任务 |
| `planner.py` | 规划：生成行动计划 |
| `action_selector.py` | 行动：选择最优下一步 |
| `reflection_engine.py` | 反思：评估决策质量 |
| `memory_writer.py` | 记忆：通过 MCR Runtime WAL 持久化 |
| `input_adapter.py` | 输入：把文字转成结构化任务 |
| `run_cognitive_loop.py` | 总调度：串联所有模块 |
| `tasks.json` | 示例任务数据 |

## 运行流程

```
输入任务 → 感知 → 注意力过滤 → 评分 → 策略检查 → 规划 → 选择 → 反思 → 写记忆 → 回放验证
```

## 为什么 Merge into main 需要 Owner？

策略引擎检测到"merge"属于高风险关键词，自动标记为 `requires_owner`。所有涉及 merge/push/delete/deploy/publish 的任务都需要你亲自批准。

## 为什么 Add real task input 是下一步？

之前只能读固定 tasks.json，现在支持 `--task` 和 `--stdin`，可以随时问它"这个任务该不该做"。

## 当前能做什么

- 输入任务，输出结构化判断（priority/risk/cost/policy）
- 自动阻止高风险任务
- 需要批准的任务标记 ASK_OWNER
- 每次判断结果写入 MCR Runtime 记忆
- 回放验证确保记忆完整性

## 当前不能做什么

- 真实浏览器控制
- 真实社交媒体操作
- 长期学习和自我改进
- 多 Agent 协作
- 真实执行任务（只做判断）

## 安全边界

- 不联网
- 不读 secret/token
- 不改 Runtime 核心
- 不自动 push/tag/release
- 高风险关键词自动拦截
- 所有判断结果可通过回放验证

## 测试覆盖

38 个测试覆盖：每个认知模块、输入适配器、高风险拦截、三种输入模式、回放验证、latest_run.json 生成。

## 建议

- **Push 实验分支**：是，安全隔离，备份用
- **Merge main**：否，先跑更多实验
