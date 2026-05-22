"""
Stability Mechanisms - Anti-Cognitive Entropy System
不是加模块，而是给已有模块加稳定性逻辑
"""
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Optional

from config import COMPRESSION_TRIGGERS, MAX_ACTIVE_MEMORIES


class MemoryImmune:
    """
    机制1: Memory 免疫系统
    目标: 防止信息淹没，让真正重要的信息能浮出水面
    """

    def __init__(self, memory_store, config: dict = None):
        self.memory = memory_store
        self.config = config or {
            "noise_threshold": 0.3,        # 低于此重要性的标记为噪声
            "signal_importance": 0.5,       # 高于此才算是信号
            "decay_rate": 0.05,            # 每次 tick 衰减率
            "access_boost": 0.1,           # 每次访问提升重要性
            "prune_threshold": 0.2,        # 低于此直接删除
            "max_noise_ratio": 0.3,        # 噪声比例上限
        }

    def immune_check(self) -> dict:
        """
        检查并清理 memory 污染.
        返回清理报告.
        """
        memories = self.memory.memories
        if not memories:
            return {"action": "none", "cleaned": 0, "reason": "empty"}

        # 分离信号和噪声
        signals = [m for m in memories if m.get("importance", 0) >= self.config["signal_importance"]]
        noise = [m for m in memories if m.get("importance", 0) < self.config["signal_importance"]]

        noise_ratio = len(noise) / len(memories)

        actions = []

        # 噪声比例超限，强制清理
        if noise_ratio > self.config["max_noise_ratio"]:
            to_remove = [m for m in noise if m.get("importance", 0) < self.config["prune_threshold"]]
            for m in to_remove:
                self.memory.memories.remove(m)
            actions.append(f"pruned {len(to_remove)} low-value noise memories (ratio: {noise_ratio:.1%})")

        # 应用衰减
        decayed_count = self._apply_decay()
        if decayed_count > 0:
            actions.append(f"decayed {decayed_count} memories")

        # 提升高价值 memory
        boosted = self._boost_recently_accessed()
        if boosted > 0:
            actions.append(f"boosted {boosted} recently accessed memories")

        # 保存
        self.memory.save()

        return {
            "action": "cleaned" if actions else "none",
            "cleaned": len(noise),
            "signals": len(signals),
            "noise": len(noise),
            "noise_ratio": noise_ratio,
            "actions": actions,
        }

    def _apply_decay(self) -> int:
        """对未访问的 memory 施加重要性衰减."""
        now = datetime.now()
        decayed = 0

        for memory in self.memory.memories:
            if memory.get("importance", 0) <= self.config["prune_threshold"]:
                continue  # 已经太低，跳过

            last_accessed = memory.get("last_accessed")
            if last_accessed:
                try:
                    last = datetime.fromisoformat(last_accessed)
                    hours_old = (now - last).total_seconds() / 3600
                    # 超过6小时未访问，开始衰减
                    if hours_old > 6:
                        decay = self.config["decay_rate"] * min(hours_old / 24, 1.0)
                        memory["importance"] = max(
                            self.config["prune_threshold"],
                            memory["importance"] - decay
                        )
                        decayed += 1
                except (ValueError, TypeError):
                    continue

        return decayed

    def _boost_recently_accessed(self) -> int:
        """提升最近访问的 memory 重要性."""
        now = datetime.now()
        boosted = 0

        for memory in self.memory.memories:
            last_accessed = memory.get("last_accessed")
            if last_accessed:
                try:
                    last = datetime.fromisoformat(last_accessed)
                    hours_old = (now - last).total_seconds() / 3600
                    if hours_old < 1:  # 1小时内访问过
                        memory["importance"] = min(
                            1.0,
                            memory["importance"] + self.config["access_boost"]
                        )
                        boosted += 1
                except (ValueError, TypeError):
                    continue

        return boosted

    def get_signal_memories(self, min_importance: float = None) -> list:
        """只获取信号记忆，忽略噪声."""
        threshold = min_importance or self.config["signal_importance"]
        return [
            m for m in self.memory.memories
            if m.get("importance", 0) >= threshold
        ]


class ReasoningVaccine:
    """
    机制2: Reasoning 疫苗
    目标: 防止 reasoning 模板化/退化
    """

    def __init__(self, state: dict, config: dict = None):
        self.state = state
        self.config = config or {
            "max_template_ratio": 0.6,     # 超过此比例认为模板化
            "diversity_threshold": 0.4,     # 多样性低于此值触发疫苗
            "penalty_per_repeat": 0.05,    # 每次重复惩罚
            "min_novelty": 0.2,            # 新颖性低于此值触发警告
        }
        self.reasoning_history = state.get("reasoning_chain", [])

    def vaccine_check(self) -> dict:
        """
        检查 reasoning 是否开始模板化.
        如果是，触发疫苗反应.
        """
        chain = self.state.get("reasoning_chain", [])

        if len(chain) < 5:
            return {"status": "healthy", "reason": "too_short", "vaccine_triggered": False}

        # 计算模板化程度
        template_ratio = self._calc_template_ratio(chain)
        diversity_score = self._calc_diversity(chain)

        # 检查是否需要疫苗
        needs_vaccine = template_ratio > self.config["max_template_ratio"]

        report = {
            "status": "degraded" if needs_vaccine else "healthy",
            "template_ratio": template_ratio,
            "diversity_score": diversity_score,
            "vaccine_triggered": needs_vaccine,
            "chain_length": len(chain),
        }

        if needs_vaccine:
            # 注入疫苗: 标记需要多样性问题
            report["vaccine_effect"] = self._inject_vaccine(chain)

        return report

    def _calc_template_ratio(self, chain: list) -> float:
        """计算 reasoning 模板化比例."""
        if len(chain) < 3:
            return 0.0

        recent = [c.get("summary", "") for c in chain[-10:]]
        unique = len(set(recent))
        total = len(recent)

        repetition = 1.0 - (unique / total)
        return repetition

    def _calc_diversity(self, chain: list) -> float:
        """计算 reasoning 多样性分数."""
        if len(chain) < 3:
            return 1.0

        # 检查 reasoning 长度变化
        lengths = [len(c.get("summary", "")) for c in chain[-5:]]
        length_variance = max(0, 1.0 - (max(lengths) - min(lengths)) / 100)

        # 检查内容重叠
        contents = [c.get("summary", "") for c in chain[-5:]]
        word_sets = [set(c.lower().split()) for c in contents if c]
        if len(word_sets) < 2:
            return 1.0

        # 计算平均词集合重叠度
        overlaps = []
        for i, ws1 in enumerate(word_sets):
            for ws2 in word_sets[i + 1:]:
                if ws1 and ws2:
                    overlap = len(ws1 & ws2) / max(len(ws1 | ws2), 1)
                    overlaps.append(overlap)

        avg_overlap = sum(overlaps) / len(overlaps) if overlaps else 0

        # 综合多样性和低重叠 = 高分
        diversity = (1.0 - avg_overlap) * 0.7 + length_variance * 0.3
        return max(0.0, min(1.0, diversity))

    def _inject_vaccine(self, chain: list) -> dict:
        """注入疫苗: 记录需要多样性的提示."""
        last_summary = chain[-1].get("summary", "") if chain else ""

        vaccine_note = {
            "type": "vaccine_injected",
            "timestamp": datetime.now().isoformat(),
            "reason": "reasoning_template_detected",
            "recommendation": "diversify_reasoning",
            "last_summary": last_summary,
        }

        # 添加到 state 的注释中（不污染主 chain）
        self.state.setdefault("_vaccine_log", [])
        self.state["_vaccine_log"].append(vaccine_note)
        self.state["_vaccine_log"] = self.state["_vaccine_log"][-10:]  # 保留最近10条

        return {
            "injected": True,
            "reason": "reasoning_template_ratio_exceeded",
            "recommendation": "next_cycle_should_diversify",
        }


class AttentionAnchor:
    """
    机制3: Attention 锚定系统
    目标: 防止 attention 碎片化，保持目标聚焦
    """

    def __init__(self, state: dict, config: dict = None):
        self.state = state
        self.config = config or {
            "refocus_threshold": 0.2,      # goal_stability 低于此值触发锚定
            "fragmentation_threshold": 5,   # plan_history 超过此数认为碎片化
            "anchor_strength": 0.1,         # 锚定恢复强度
        }

    def anchor_check(self) -> dict:
        """
        检查 attention 是否失焦.
        如果是，执行锚定恢复.
        """
        goal_stability = self.state.get("metadata", {}).get("goal_stability_score", 1.0)
        current_goal = self.state.get("current_goal")
        plan_history_len = len(self.state.get("plan_history", []))
        observations = self.state.get("observations", [])

        # 计算碎片化指标
        fragmentation_score = self._calc_fragmentation(observations, plan_history_len)

        issues = []

        # 检查是否需要锚定
        if goal_stability < self.config["refocus_threshold"]:
            issues.append("low_goal_stability")

        if plan_history_len > self.config["fragmentation_threshold"]:
            issues.append("plan_churn")

        if fragmentation_score > 0.7:
            issues.append("observation_fragmentation")

        needs_anchor = len(issues) > 0

        report = {
            "needs_anchor": needs_anchor,
            "goal_stability": goal_stability,
            "fragmentation_score": fragmentation_score,
            "plan_churn": plan_history_len,
            "issues": issues,
        }

        if needs_anchor and current_goal:
            report["anchor_effect"] = self._apply_anchor(current_goal)

        return report

    def _calc_fragmentation(self, observations: list, plan_history_len: int) -> float:
        """
        计算 attention 碎片化程度.
        0 = 完全聚焦, 1 = 完全碎片化.
        """
        if not observations:
            return 0.0

        # 观察的时间跨度
        if len(observations) >= 2:
            try:
                first = datetime.fromisoformat(observations[0].get("timestamp", datetime.now().isoformat()))
                last = datetime.fromisoformat(observations[-1].get("timestamp", datetime.now().isoformat()))
                hours_span = (last - first).total_seconds() / 3600
                # 时间跨度大但观察少 = 碎片化
                obs_density = len(observations) / max(hours_span, 1)
                density_score = min(1.0, obs_density / 10)  # 归一化
            except (ValueError, TypeError):
                density_score = 0.5
        else:
            density_score = 1.0

        # Plan 切换频繁 = 碎片化
        plan_score = min(1.0, plan_history_len / 10)

        # 综合
        return density_score * 0.6 + plan_score * 0.4

    def _apply_anchor(self, goal: str) -> dict:
        """执行锚定，恢复目标焦点."""
        current_stability = self.state.get("metadata", {}).get("goal_stability_score", 0.5)

        # 恢复稳定性
        new_stability = min(
            1.0,
            current_stability + self.config["anchor_strength"]
        )

        self.state["metadata"]["goal_stability_score"] = new_stability

        # 添加锚定注释
        self.state.setdefault("_anchor_log", [])
        self.state["_anchor_log"].append({
            "timestamp": datetime.now().isoformat(),
            "action": "anchor_applied",
            "goal": goal,
            "stability_before": current_stability,
            "stability_after": new_stability,
        })
        self.state["_anchor_log"] = self.state["_anchor_log"][-10:]

        # 清理无关观察
        observations = self.state.get("observations", [])
        if len(observations) > 10:
            # 只保留最近的
            self.state["observations"] = observations[-10:]

        return {
            "anchored": True,
            "stability_restored": new_stability,
            "observations_pruned": len(observations) - 10 if len(observations) > 10 else 0,
        }


class SurvivalTriggers:
    """
    机制4: 生存触发器
    目标: 定义何时压缩/休眠/重置
    这不是普通的定时清理，而是真正的"生存决策"
    """

    def __init__(self, state: dict, memory_store, event_queue, config: dict = None):
        self.state = state
        self.memory = memory_store
        self.events = event_queue
        self.config = config or {
            "emergency_compression": {
                "memory_pollution_threshold": 0.7,     # 噪声比超过70%触发
                "state_inflation_threshold": 50,       # 观察数超过50触发
                "drift_critical_threshold": 0.5,       # drift score 超过0.5触发
            },
            "sleep": {
                "idle_ticks_threshold": 20,             # 20 tick 无有效活动
                "low_coherence_ticks": 10,             # 连续10 tick reasoning 模板化
            },
            "reset": {
                "goal_stability_floor": 0.2,           # stability 低于此值强制 reset
                "max_plan_churn": 30,                  # plan 切换超过此数
            },
        }

    def check_triggers(self) -> dict:
        """
        检查是否触发生存机制.
        返回应该采取的行动.
        """
        decisions = []

        # 检查紧急压缩
        compression = self._check_compression()
        if compression["triggered"]:
            decisions.append(("compress", compression))

        # 检查休眠
        sleep = self._check_sleep()
        if sleep["triggered"]:
            decisions.append(("sleep", sleep))

        # 检查重置
        reset = self._check_reset()
        if reset["triggered"]:
            decisions.append(("reset", reset))

        return {
            "decisions": decisions,
            "has_survival_action": len(decisions) > 0,
        }

    def _check_compression(self) -> dict:
        """检查是否需要紧急压缩."""
        memories = self.memory.memories
        observations = self.state.get("observations", [])
        drift_score = self.state.get("metadata", {}).get("last_drift_score", 0.0)

        # Memory 污染检查
        noise = [m for m in memories if m.get("importance", 0) < 0.3]
        noise_ratio = len(noise) / max(1, len(memories))

        triggers = []

        if noise_ratio > self.config["emergency_compression"]["memory_pollution_threshold"]:
            triggers.append(f"memory_pollution:{noise_ratio:.1%}")

        if len(observations) > self.config["emergency_compression"]["state_inflation_threshold"]:
            triggers.append(f"state_inflation:{len(observations)}")

        if drift_score > self.config["emergency_compression"]["drift_critical_threshold"]:
            triggers.append(f"critical_drift:{drift_score:.2f}")

        return {
            "triggered": len(triggers) > 0,
            "triggers": triggers,
            "action": "emergency_compression",
        }

    def _check_sleep(self) -> dict:
        """检查是否应该进入休眠."""
        metadata = self.state.get("metadata", {})

        # 无活动 tick 数
        idle_ticks = metadata.get("idle_ticks", 0)
        coherence_ticks = metadata.get("low_coherence_ticks", 0)

        triggers = []

        if idle_ticks > self.config["sleep"]["idle_ticks_threshold"]:
            triggers.append(f"idle:{idle_ticks}")

        if coherence_ticks > self.config["sleep"]["low_coherence_ticks"]:
            triggers.append(f"low_coherence:{coherence_ticks}")

        return {
            "triggered": len(triggers) > 0,
            "triggers": triggers,
            "action": "sleep",
        }

    def _check_reset(self) -> dict:
        """检查是否需要强制重置."""
        goal_stability = self.state.get("metadata", {}).get("goal_stability_score", 1.0)
        plan_churn = len(self.state.get("plan_history", []))

        triggers = []

        if goal_stability < self.config["reset"]["goal_stability_floor"]:
            triggers.append(f"critical_stability:{goal_stability:.2f}")

        if plan_churn > self.config["reset"]["max_plan_churn"]:
            triggers.append(f"plan_churn:{plan_churn}")

        return {
            "triggered": len(triggers) > 0,
            "triggers": triggers,
            "action": "reset",
        }

    def execute_survival(self, action: str, params: dict) -> dict:
        """执行生存行动."""
        if action == "compress":
            return self._execute_compression(params)
        elif action == "sleep":
            return self._execute_sleep(params)
        elif action == "reset":
            return self._execute_reset(params)
        return {"executed": False, "reason": "unknown_action"}

    def _execute_compression(self, params: dict) -> dict:
        """执行紧急压缩."""
        before_memory = len(self.memory.memories)

        # 激进清理低价值 memory
        pruned = self.memory.prune_low_value(min_importance=0.25)

        # 压缩 observations
        observations = self.state.get("observations", [])
        compressed_obs = observations[-20:] if len(observations) > 20 else observations
        self.state["observations"] = compressed_obs

        # 创建压缩摘要
        self.state["context_summary"] = f"[COMPRESSED at {datetime.now().isoformat()}] {len(observations)} -> {len(compressed_obs)} observations"

        after_memory = len(self.memory.memories)

        return {
            "executed": True,
            "action": "emergency_compression",
            "memory_pruned": pruned,
            "memory_before": before_memory,
            "memory_after": after_memory,
            "observations_compressed": len(observations) - len(compressed_obs),
        }

    def _execute_sleep(self, params: dict) -> dict:
        """进入休眠状态."""
        self.state["_sleep_mode"] = True
        self.state["_sleep_started"] = datetime.now().isoformat()

        return {
            "executed": True,
            "action": "sleep",
            "note": "System entering low-activity mode until triggered",
        }

    def _execute_reset(self, params: dict) -> dict:
        """执行选择性重置."""
        # 保存关键状态
        reset_snapshot = {
            "timestamp": datetime.now().isoformat(),
            "preserved_goal": self.state.get("current_goal"),
            "preserved_plan": self.state.get("active_plan"),
            "metadata": self.state.get("metadata", {}),
        }

        # 清理非关键状态
        self.state["observations"] = []
        self.state["reasoning_chain"] = []
        self.state["plan_history"] = []
        self.state["recent_decisions"] = []

        # 重置稳定性分数（但保留 goal）
        self.state["metadata"]["goal_stability_score"] = 0.8

        # 标记 reset
        self.state["_last_reset"] = datetime.now().isoformat()
        self.state["_reset_snapshot"] = reset_snapshot

        return {
            "executed": True,
            "action": "reset",
            "preserved": ["goal", "active_plan", "metadata"],
            "reset": ["observations", "reasoning_chain", "plan_history", "recent_decisions"],
        }
