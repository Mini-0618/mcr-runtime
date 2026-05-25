# MCR ORCHESTRATOR

这是一个最小多 Agent 调度层。第一版只做任务拆分和分发文件，不联网，不调用 Codex、Hermes、Claude 或 GitHub API。

目标是把工作流从“人肉中转站”改成：

```text
inbox.md -> orchestrator.py -> tasks.json + dispatch.md + reports.md
```

## 文件

- `inbox.md`: 只写自然语言需求。
- `orchestrator.py`: 读取 inbox，生成结构化任务。
- `tasks.json`: 机器可读任务池。
- `dispatch.md`: 按 assignee 分发给 codex / hermes / claude / github / human。
- `reports.md`: 今日进度汇总。

## 使用

在 `/home/minimak/mcr/ORCHESTRATOR` 下运行：

```bash
python3 orchestrator.py
```

示例输入：

```text
我要做 MCR 的 access_history cap
```

示例输出会生成：

- 给 `codex`: 实现代码修改。
- 给 `hermes`: 跑验证并准备提交状态。
- 给 `claude`: 审查风险、README 和测试遗漏。
- 给 `github`: 实现与验证完成后提交推送。
- 给 `human`: 最终确认真实意图。

## 约束

- 第一版不自动调用任何 Agent。
- 第一版不联网。
- 第一版不自动 commit/push 生成的执行结果以外的内容。
- 调度规则是确定性的关键词规则，后续再接 Hermes、Codex 或 Claude 执行器。

## Demo

```bash
cd /home/minimak/mcr/ORCHESTRATOR
python3 orchestrator.py --demo
cat tasks.json
cat dispatch.md
cat reports.md
```
