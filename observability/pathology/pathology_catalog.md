# Pathology Catalog

## MCR Phase 2.5 — Observed Pathologies

---

## Catalog Format

```
## [ID] Pathology Name
- **Category**: ...
- **Trigger**: ...
- **Observable Signal**: ...
- **Bounded/Unbounded**: ...
- **Mitigation**: ...
- **Allowed in Mainline**: YES/NO
- **Last Observed**: ...
- **Evidence**: ...
```

---

## Known Pathologies

---

## [P001] Bridge Collapse Loop

- **Category**: lifecycle
- **Trigger**: Reinforcement signal missing + time decay → bridge repeatedly collapses and regenerates
- **Observable Signal**: collapsed_count high, reconstruct_count high, same bridges cycling
- **Bounded/Unbounded**: Bounded（bridge_budget 限制总数）
- **Mitigation**: bridge_budget + dormant state prevents rapid cycling
- **Allowed in Mainline**: YES
- **Last Observed**: v0.19f benchmark
- **Evidence**: chaos_experiment_results.json

---

## [P002] Retrieval Drift

- **Category**: retrieval
- **Trigger**: Episodic access patterns shift over time, bridge weights stale
- **Observable Signal**: retrieval results no longer match fresh episodic, Delta drops
- **Bounded/Unbounded**: Bounded（governance 可以触发 re-formation）
- **Mitigation**: bridge_governance + validation_pass
- **Allowed in Mainline**: YES（可检测和恢复）
- **Last Observed**: v0.19d
- **Evidence**: Delta +81.7% → degradation over time

---

## [P003] Semantic Suppression

- **Category**: semantic layer
- **Trigger**: High-frequency episodic patterns dominate, semantic layer never fires
- **Observable Signal**: semantic_activation_count = 0, all retrieval from episodic
- **Bounded/Unbounded**: Bounded（semantic 层存在但可被压制）
- **Mitigation**: consolidation_trigger needed
- **Allowed in Mainline**: YES（可观测）
- **Last Observed**: v0.19f
- **Evidence**: benchmark query 和知识库无字符交集

---

## [P004] Architecture Explosion

- **Category**: system
- **Trigger**: 无限新增 governance layer / abstraction
- **Observable Signal**: 代码行数增长、层数增长、benchmark 复杂化
- **Bounded/Unbounded**: Unbounded（若不控制会无限增长）
- **Mitigation**: Policy Section 24（Complexity Budget）+ Section 28（禁止无限 governance）
- **Allowed in Mainline**: NO
- **Last Observed**: 2026-05-14（Policy v1.5 已修复）
- **Evidence**: RUNTIME_POLICY.md v1.5

---

## [P005] Recursive Governance

- **Category**: governance
- **Trigger**: governance 需要 governance 来治理 → 无限递归
- **Observable Signal**: governance layer 互相引用、无终止条件
- **Bounded/Unbounded**: Unbounded（必须从架构上阻止）
- **Mitigation**: Policy Section 23（Research Stop Condition）+ Section 27（禁止递归 governance）
- **Allowed in Mainline**: NO
- **Last Observed**: N/A（已预防）
- **Evidence**: RUNTIME_POLICY.md Section 27

---

## [P006] Latency Spike

- **Category**: performance
- **Trigger**: retrieval_budget 过大或 bridge_count 过高
- **Observable Signal**: p95/p99 latency 超过 threshold
- **Bounded/Unbounded**: Bounded（latency_bounded 验证）
- **Mitigation**: bridge_budget + latency_bounded
- **Allowed in Mainline**: YES
- **Last Observed**: v0.19f benchmark
- **Evidence**: latency < 10ms verified

---

## [P007] Memory Contamination

- **Category**: memory
- **Trigger**: 错误的 semantic bridge 建立，导致不相关 episodic 互相干扰
- **Observable Signal**: contamination_rate 上升、category_purity 下降
- **Bounded/Unbounded**: Bounded（contamination_threshold 限制）
- **Mitigation**: boundary_enforcement + validation_pass
- **Allowed in Mainline**: YES
- **Last Observed**: v0.19d
- **Evidence**: drift pathology exposed

---

## [P008] Activation Starvation

- **Category**: retrieval
- **Trigger**: bridge_count 过高，retrieval_budget 不足 → 大部分 bridge 永远无法激活
- **Observable Signal**: starvation_events > 0, bridge_lifetime 分布极端
- **Bounded/Unbounded**: Bounded（bridge_budget 限制总数，dormant 状态保护）
- **Mitigation**: bridge_budget + active/dormant分层
- **Allowed in Mainline**: YES
- **Last Observed**: v0.19d
- **Evidence**: drift/overwrite pathology

---

## [P009] Active=Bug (Misinterpretation)

- **Category**: diagnostic
- **Trigger**: active_count=0 被误认为 bug，实际是 retrieval_threshold 过滤正常行为
- **Observable Signal**: active_count=0 in snapshot but runtime works
- **Bounded/Unbounded**: N/A（这是 config sensitivity，不是 pathology）
- **Mitigation**: 正确理解 retrieval physics
- **Allowed in Mainline**: N/A（不是 pathology）
- **Last Observed**: v0.19f
- **Evidence**: docs/BOUNDED_PROPERTY.md

---

## [P010] Context Window Pollution

- **Category**: memory
- **Trigger**: episodic accumulation → context 被无关记忆填满
- **Observable Signal**: context_utilization 下降，有效 retrieval ratio 下降
- **Bounded/Unbounded**: Bounded（lifecycle 清理 + archive）
- **Mitigation**: lifecycle + decay + archive
- **Allowed in Mainline**: YES
- **Last Observed**: Unknown
- **Evidence**: Hypothesis

---

## [P011] Semantic Override

- **Category**: semantic
- **Trigger**: 新 semantic formation 覆盖旧的，旧信息丢失
- **Observable Signal**: semantic_override_count 上升
- **Bounded/Unbounded**: Bounded（需要 validation_pass）
- **Mitigation**: validation_pass + negative_evidence
- **Allowed in Mainline**: YES
- **Last Observed**: Unknown
- **Evidence**: Hypothesis

---

## [P012] Silent Recovery (Policy Violation)

- **Category**: governance
- **Trigger**: agent 跳过错误上报直接 patch
- **Observable Signal**: 连续 patch failure, recursive repair loop
- **Bounded/Unbounded**: Unbounded（若不控制会破坏系统）
- **Mitigation**: Policy Section 15（错误熔断）+ Section 16（禁止 silent recovery）
- **Allowed in Mainline**: NO
- **Last Observed**: N/A（已预防）
- **Evidence**: RUNTIME_POLICY.md Section 16

---

## Summary Table

| ID | Pathology | Category | Bounded | Allowed | Status |
|----|-----------|----------|---------|---------|--------|
| P001 | Bridge Collapse Loop | lifecycle | YES | YES | Observed |
| P002 | Retrieval Drift | retrieval | YES | YES | Observed |
| P003 | Semantic Suppression | semantic | YES | YES | Observed |
| P004 | Architecture Explosion | system | NO | NO | Prevented |
| P005 | Recursive Governance | governance | NO | NO | Prevented |
| P006 | Latency Spike | performance | YES | YES | Observed |
| P007 | Memory Contamination | memory | YES | YES | Observed |
| P008 | Activation Starvation | retrieval | YES | YES | Observed |
| P009 | Active=0 Misinterpret | diagnostic | N/A | N/A | Clarified |
| P010 | Context Window Pollution | memory | YES | YES | Hypothesized |
| P011 | Semantic Override | semantic | YES | YES | Hypothesized |
| P012 | Silent Recovery | governance | NO | NO | Prevented |

---

## Maintenance Notes

```
Pathology Count: 12
- Observed: 8
- Hypothesized: 2
- Prevented (Policy): 2

Category Distribution:
- lifecycle: 1
- retrieval: 2
- semantic: 3
- memory: 2
- governance: 2
- performance: 1
- system: 1

Key Insight:
大部分 pathology 是 bounded，可以通过 governance + lifecycle 机制控制。
真正的 unbounded 风险来自 policy violation（recursive governance / silent recovery）。
```

---

## Adding New Pathologies

When a new pathology is discovered:

1. 记录到本 catalog
2. 分类（lifecycle/retrieval/semantic/memory/governance/performance/system）
3. 确认 bounded/unbounded
4. 确认 allowed in mainline
5. 更新 Summary Table
6. 报告给 owner

禁止：
- 把 config sensitivity 当作 pathology
- 把 normal behavior 当作 pathology
- 未经确认就声称 "bug found"
