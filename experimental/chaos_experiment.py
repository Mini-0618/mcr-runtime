"""
MCR 100 Tick Chaos Experiment
测试认知熵增 - 持续注入扰动观察系统是否会漂/崩/乱
"""
import json
import random
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loop import CognitiveLoop
from event_system import EventQueue, EventType, create_event
from config import EVENT_FILE


def check_repetition(chain):
    """检查 reasoning chain 是否有重复/模板化趋势."""
    if len(chain) < 3:
        return 0.0
    summaries = [c.get("summary", "") for c in chain[-10:]]
    unique = len(set(summaries))
    return 1.0 - (unique / len(summaries)) if summaries else 0.0


def inject_chaos(loop, tick):
    """
    每5 tick 注入一次混沌事件.
    模拟真实环境中的干扰.
    """
    chaos_types = [
        "conflicting_goal",
        "irrelevant_memory",
        "noisy_observation",
        "interrupted_plan",
        "duplicated_event",
    ]

    # 每5 tick 随机选一个混沌类型注入
    if tick % 5 == 0 and tick > 0:
        chaos_type = random.choice(chaos_types)

        if chaos_type == "conflicting_goal":
            # 注入冲突目标
            conflicting_goals = [
                "突然想研究量子计算",
                "改做 Python 项目",
                "去睡觉",
                "刷抖音",
                "研究区块链",
            ]
            loop.events.push(create_event(
                EventType.GOAL_UPDATED,
                {"goal": random.choice(conflicting_goals), "reason": "chaos_injection"},
                "chaos"
            ))

        elif chaos_type == "irrelevant_memory":
            # 注入无关记忆
            irrelevant_memories = [
                "记得小时候养过一只猫叫阿花",
                "想起高中数学老师说过的一句话",
                "突然想到三年前去过的一个城市",
                "记得小时候奶奶做的红烧肉",
                "想到上周看到的一部电视剧",
            ]
            mem_id = loop.memory.store(
                random.choice(irrelevant_memories),
                memory_type="noise",
                importance=0.3,
                tags=["chaos", "irrelevant"]
            )
            loop.events.push(create_event(
                EventType.MEMORY_STORED,
                {"memory_id": mem_id, "type": "chaos"},
                "chaos"
            ))

        elif chaos_type == "noisy_observation":
            # 注入噪声观察
            noisy_obs = [
                "好像听到窗外有鸟叫",
                "感觉有点困",
                "手机屏幕有点脏",
                "键盘有几个键有点松",
                "空调好像有点吵",
            ]
            loop.events.push(create_event(
                EventType.OBSERVATION_ADDED,
                {"content": random.choice(noisy_obs), "source": "chaos"},
                "chaos"
            ))

        elif chaos_type == "interrupted_plan":
            # 中断当前计划
            if loop.state.get("active_plan"):
                loop.state["active_plan"] = None
                loop.events.push(create_event(
                    EventType.INTERNAL_REASONING,
                    {"content": "计划被中断，重新思考", "source": "chaos"},
                    "chaos"
                ))

        elif chaos_type == "duplicated_event":
            # 重复发送同一事件
            if loop.events.size() > 0:
                last_event = loop.events.peek(1)[0]
                loop.events.push(last_event)  # 重复插入

        return chaos_type
    return None


def run_chaos_experiment(ticks=100):
    """运行混沌实验."""
    print(f"开始 MCR 混沌熵增实验: {ticks} ticks")
    print("=" * 80)

    # 初始化
    loop = CognitiveLoop()

    # 设置初始目标
    loop.state["current_goal"] = "MCR 认知稳定性实验 - 100 tick 混沌演化"
    loop.state["active_plan"] = {
        "goal": "MCR 认知稳定性实验 - 100 tick 混沌演化",
        "steps": ["观察", "思考", "执行", "反思"],
        "created_at": datetime.now().isoformat(),
    }
    loop.state["metadata"]["goal_stability_score"] = 1.0

    results = []
    chaos_log = []

    for i in range(ticks):
        # 注入混沌
        chaos_type = inject_chaos(loop, i + 1)

        # 运行一个 cycle
        result = loop.run_cycle()

        # 计算关键指标
        reasoning_chain = loop.state.get("reasoning_chain", [])
        reasoning_repetition = check_repetition(reasoning_chain)

        # 计算 attention fragmentation - plan 切换频率
        plan_changes = len(loop.state.get("plan_history", []))

        # 计算 memory relevance - 激活的记忆是否相关
        active_memories = loop.memory.memories
        irrelevant_count = len([m for m in active_memories if m.get("type") == "noise"])

        metrics = {
            "tick": result["cycle"],
            "drift_score": result["drift_score"],
            "drifts_detected": result["drifts_detected"],
            "goal_stability": loop.state.get("metadata", {}).get("goal_stability_score", 1.0),
            "observation_count": len(loop.state.get("observations", [])),
            "reasoning_chain_len": len(reasoning_chain),
            "reasoning_repetition": reasoning_repetition,
            "memory_count": len(loop.memory.memories),
            "irrelevant_memory_count": irrelevant_count,
            "plan_changes": plan_changes,
            "event_queue_size": loop.events.size(),
            "compression_actions": len(result.get("compression_actions", [])),
            "chaos_injected": chaos_type,
        }

        results.append(metrics)

        # 每 10 tick 打印状态
        if (i + 1) % 10 == 0:
            print(
                f"tick {result['cycle']:3d} | "
                f"drift: {metrics['drift_score']:.3f} | "
                f"goal_stab: {metrics['goal_stability']:.3f} | "
                f"obs: {metrics['observation_count']:3d} | "
                f"reason_rep: {metrics['reasoning_repetition']:.2f} | "
                f"mem: {metrics['memory_count']:3d} (irr: {irrelevant_count}) | "
                f"plan_chg: {plan_changes} | "
                f"chaos: {chaos_type or '-':20s}"
            )

        if chaos_type:
            chaos_log.append({"tick": result["cycle"], "type": chaos_type})

    # 保存完整实验结果
    experiment_data = {
        "experiment": "MCR 100 Tick Chaos Entropy Test",
        "started_at": datetime.now().isoformat(),
        "ticks": ticks,
        "chaos_log": chaos_log,
        "metrics": results,
        "final_state_summary": {
            "goal_stability": results[-1]["goal_stability"],
            "drift_score": results[-1]["drift_score"],
            "reasoning_repetition": results[-1]["reasoning_repetition"],
            "total_memory": results[-1]["memory_count"],
            "total_irrelevant": results[-1]["irrelevant_memory_count"],
            "total_plan_changes": results[-1]["plan_changes"],
        },
    }

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chaos_experiment_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(experiment_data, f, ensure_ascii=False, indent=2)

    print("=" * 80)
    print("实验完成!")
    print(f"结果保存到: {output_path}")
    print()

    # 分析结果
    print("=== 熵增分析 ===")
    final = results[-1]
    initial = results[0]

    goal_drift = initial["goal_stability"] - final["goal_stability"]
    print(f"Goal 漂移: {goal_drift:.3f} ({'严重' if abs(goal_drift) > 0.5 else '可接受' if abs(goal_drift) > 0.2 else '轻微'})")

    reasoning_rep = final["reasoning_repetition"]
    print(f"Reasoning 重复率: {reasoning_rep:.2f} ({'危险 - 模板化' if reasoning_rep > 0.5 else '可接受' if reasoning_rep > 0.3 else '正常'})")

    mem_irr_ratio = final["irrelevant_memory_count"] / max(1, final["memory_count"])
    print(f"Memory 污染率: {mem_irr_ratio:.2%} ({'危险' if mem_irr_ratio > 0.5 else '可接受' if mem_irr_ratio > 0.3 else '正常'})")

    plan_churn = final["plan_changes"]
    print(f"Plan 切换次数: {plan_churn} ({'危险 - 注意力碎片化' if plan_churn > 20 else '可接受'})")

    avg_drift = sum(r["drift_score"] for r in results[-20:]) / 20
    print(f"后期平均 drift: {avg_drift:.3f} ({'递增趋势' if avg_drift > 0.3 else '稳定'})")

    return experiment_data


if __name__ == "__main__":
    run_chaos_experiment(100)
