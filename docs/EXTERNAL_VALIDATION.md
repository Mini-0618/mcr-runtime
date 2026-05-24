# External Validation Plan

## 目标

验证 MCR 是否能从"个人项目"变成"别人能理解的项目"。

标准：**第一个外部用户能否在 3 分钟内跑通，并说清楚它解决了什么问题。**

---

## 目标用户画像

MCR 适合以下类型的开发者：

1. **AI Agent 框架开发者**
   - 用过 LangChain / LangGraph / Mem0
   - 遇到过 memory 持续增长导致的延迟问题
   - 想找 bounded-latency 方案

2. **事件驱动架构爱好者**
   - 熟悉 event sourcing / CQRS
   - 想看在 AI Agent 场景的应用
   - 对 WAL + replay verification 有兴趣

3. **嵌入式/持久化系统开发者**
   - 需要 24/7 运行的 AI 服务
   - 关心状态恢复和 crash safety
   - 对确定性有要求

4. **研究者 / 学生**
   - 研究 AI Memory / Cognitive Architecture
   - 需要一个可跑通的 runtime 原型
   - 想找 thesis topic

---

## 3 分钟试跑流程

```
Step 1 (30秒): clone
  git clone https://github.com/Mini-0618/mcr-runtime
  cd mcr-runtime

Step 2 (30秒): 运行 quickstart
  python3 examples/quickstart.py
  期望输出: G2 VERIFICATION PASSED

Step 3 (60秒): 运行 replay demo
  python3 examples/replay_verification_demo.py
  期望输出: verification: PASS ✓

Step 4 (60秒): 阅读 INTRODUCTION.md
  cat docs/INTRODUCTION.md
  期望: 理解 MCR 是什么、解决什么问题
```

如果这四步后对方说"懂了，有意思"，验证通过。

---

## 需要收集的反馈问题

发给测试用户的核心问题（不要一次问完，按顺序问）：

**问题 1（跑完后）：** 这两个 demo 跑通了吗？
**问题 2（跑完后）：** 你觉得它解决了什么问题？用一句话描述。

**问题 3（如果对方卡住）：** 哪里卡住了？

**问题 4（对方理解后）：** 这个项目最吸引你的是什么？

**问题 5（对方理解后）：** 有什么地方让你觉得困惑或者解释得不清楚？

**问题 6（对方理解后）：** 你会不会把这个项目推荐给做 AI Agent 的开发者？为什么？

---

## 反馈记录模板

用于记录每个测试用户的反馈：

```markdown
## 用户 [编号]

### 基本信息
- 背景:
- 经验:

### 跑通情况
- quickstart.py: ✓/✗
- replay_verification_demo.py: ✓/✗
- 卡在:

### 对项目的理解
- 用一句话描述 MCR 解决的问题:
- 描述准确度: 高/中/低

### 正面反馈
-

### 负面反馈 / 困惑点
-

### 是否推荐
- 推荐度: 1-5
- 原因:

### 下一步改进建议
-
```

---

## 测试用户来源（按优先级）

1. **GitHub issue / PR 反馈** — 通过发布让陌生人主动来
2. **AI 开发者社群** — 掘金、知乎、X / Twitter
3. **朋友圈 / 微信群** — 开发者朋友
4. **LeetCode/技术论坛** — 发帖询问

---

## 通过标准

- 至少 3 个外部用户完成 3 分钟试跑
- 至少 2 个人能用一句话准确描述 MCR 解决的问题
- 至少 1 个"有意思，我想深入看看"的反馈

达到以上标准，说明 MCR 的外部验证通过。

---

## Feedback Log Template

每个测试用户的反馈记录，追加于此：

```markdown
---

## 用户 [#]

**日期：**
**背景：**
- 经验水平 (学生/初级/中高级/架构):
- 对 AI Agent 的了解程度:
- 是否熟悉 event sourcing / WAL:

**环境：**
- OS:
- Python version:
- Git available: ✓/✗

**试跑结果：**
- quickstart.py: ✓ PASS / ✗ FAIL / ⚠ 卡在
- replay_verification_demo.py: ✓ PASS / ✗ FAIL / ⚠ 卡在
- hermes_bridge_demo.py: ✓ PASS / ✗ FAIL / ⚠ 未跑

**4 个问题回答：**

1. 30秒内能看懂 MCR 是什么吗？
   回答：

2. quickstart 跑通了吗？
   回答：

3. replay verifier 的价值能理解吗？
   回答：

4. 它更像哪类工具？
   回答：Agent memory backend / observability tool / research artifact / 其他：

**最有价值的部分：**

**最不清楚的部分：**

**改进建议：**

**下一步：**

**跟进动作：**
```

---

## Feedback Targets

**目标：** 找 3–5 个 Python / AI Agent / 工程朋友试跑 MCR v0.9.0

**标准：**
- 每个人只需要 3 分钟（clone + quickstart + replay demo）
- 重点验证：
  1. quickstart 是否能跑通
  2. MCR 是什么是否能被理解
  3. replay verifier 的价值是否有感知

**不在本阶段验证的内容：**
- 不验证 semantic promotion 是否激活
- 不验证 benchmark 数据是否合理
- 不验证 Hermes Bridge 是否可用

**成功标准：**
- 至少 3 个外部用户跑通 quickstart.py
- 至少 2 个用户能准确描述 MCR 解决了什么问题
- 至少 1 个用户给出"有意思，想深入看看"的反馈

**下一步行动：**
拿到第一个真实反馈前，不新增 runtime 功能。