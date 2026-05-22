#!/usr/bin/env python3
"""
Profiling run for LayeredMemory benchmark.
Focus: _calc_goal_relevance, access_history traversal, semantic scoring, retrieval hot path.
Output: top cumulative time functions + per-function breakdown.
"""
import sys
import os
import cProfile
import pstats
import io
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from layered_memory import LayeredMemory

# ---- Same setup as benchmark_memory.py ----

CLUSTERS = {
    "project_a": {
        "keywords": ["项目", "设计", "模块", "接口", "架构", "开发", "测试", "部署", "需求"],
        "templates": [
            "项目A：完成{module}模块的设计文档",
            "项目A：{module}接口遇到兼容性问题",
            "项目A：用户反馈{module}功能响应慢",
            "项目A：团队讨论{module}技术选型方案",
            "项目A：{module}模块测试覆盖率提升到80%",
        ],
    },
    "project_b": {
        "keywords": ["产品", "迭代", "用户", "反馈", "体验", "上线", "策略", "增长"],
        "templates": [
            "产品B：完成新一轮用户调研分析",
            "产品B：迭代计划优先级调整公告",
            "产品B：用户反馈{module}操作复杂",
            "产品B：上线后转化率数据汇报",
            "产品B：下个季度增长策略制定",
        ],
    },
    "research": {
        "keywords": ["论文", "实验", "算法", "模型", "训练", "数据", "基准", "结果"],
        "templates": [
            "研究：阅读{module}相关论文笔记",
            "研究：复现{module}实验遇到困难",
            "研究：{module}模型训练 loss 不收敛",
            "研究：{module}基准测试结果分析",
            "研究：和导师讨论{module}创新方向",
        ],
    },
    "debug": {
        "keywords": ["bug", "错误", "崩溃", "修复", "日志", "调试", "排查", "问题"],
        "templates": [
            "调试：{module}出现空指针异常",
            "调试：{module}内存泄漏问题定位",
            "调试：{module}在高并发下崩溃",
            "调试：{module}日志显示超时错误",
            "调试：{module}排查了3小时终于解决",
        ],
    },
    "personal": {
        "keywords": ["生活", "休息", "运动", "读书", "计划", "目标", "时间", "效率"],
        "templates": [
            "个人：今日工作复盘与明日计划",
            "个人：保持运动提升精力",
            "个人：时间管理方法实践",
            "个人：读完《深度工作》读书笔记",
            "个人：专注力训练心得",
        ],
    },
}

CLUSTER_NAMES = list(CLUSTERS.keys())
MODULES = ["认证", "支付", "搜索", "推荐", "消息", "缓存", "队列", "网关", "权限", "统计"]

SEMANTIC_KNOWLEDGE = [
    {"cluster": "debug", "content": "空指针异常通常由未初始化的对象引用引起", "importance": 0.8},
    {"cluster": "debug", "content": "内存泄漏多数由于未关闭数据库连接和文件句柄", "importance": 0.9},
    {"cluster": "debug", "content": "高并发崩溃常见原因是竞态条件和锁粒度设计", "importance": 0.8},
    {"cluster": "debug", "content": "超时错误往往是网络不稳定或服务端负载过高", "importance": 0.7},
    {"cluster": "project_a", "content": "接口兼容性问题是不同版本协议导致的", "importance": 0.8},
    {"cluster": "project_a", "content": "模块响应慢通常需要优化数据库查询和缓存策略", "importance": 0.8},
    {"cluster": "research", "content": "模型训练 loss 不收敛可能是学习率过大或数据标注问题", "importance": 0.9},
    {"cluster": "research", "content": "基准测试需要控制随机种子保证可复现性", "importance": 0.7},
    {"cluster": "project_b", "content": "用户转化率低通常与产品路径设计和用户教育有关", "importance": 0.8},
    {"cluster": "personal", "content": "深度工作需要屏蔽干扰并保持专注时段", "importance": 0.7},
]

def get_cluster_for_tick(tick: int) -> str:
    phase = (tick // 100) % 5
    return CLUSTER_NAMES[phase]

def generate_signal_content(tick: int, cluster: str) -> str:
    tmpl = random.choice(CLUSTERS[cluster]["templates"])
    module = random.choice(MODULES)
    return tmpl.format(module=module)

def generate_noise_content() -> str:
    noise_contents = [
        "记得小时候养过一只猫叫阿花",
        "想起高中数学老师说过的一句话",
        "突然想到三年前去过的一个城市",
        "手机屏幕有点脏",
        "感觉有点困",
    ]
    return random.choice(noise_contents)

def get_goal_for_tick(tick: int) -> str:
    cluster = get_cluster_for_tick(tick)
    goal_map = {
        "project_a": "项目A的技术架构设计与实现",
        "project_b": "产品B的用户增长策略优化",
        "research": "大模型训练与算法优化研究",
        "debug": "系统稳定性问题排查与修复",
        "personal": "个人效率提升与深度工作实践",
    }
    return goal_map[cluster]

# ---- Profiling target ----

def run_profiled(ticks=1000):
    """Run LayeredMemory for `ticks` ticks with profiling enabled."""

    tmp_dir = f"/tmp/prof_lm_{random.randint(10000,99999)}"
    os.makedirs(tmp_dir, exist_ok=True)

    lm = LayeredMemory(tmp_dir)

    # Pre-populate semantic layer
    for kw in SEMANTIC_KNOWLEDGE:
        lm.store(
            kw["content"], "semantic", kw["importance"],
            [kw["cluster"]], current_tick=0
        )

    rng_signal = random.Random(42)
    rng_noise = random.Random(42)

    for tick in range(1, ticks + 1):
        # Inject chaos every 5 ticks
        if tick % 5 == 0 and tick > 0:
            lm.store(generate_noise_content(), 'noise', 0.3, ['chaos'], current_tick=tick)

        current_goal = get_goal_for_tick(tick)
        goal_history = [
            {"tick": max(0, tick - 10 * i), "goal": get_goal_for_tick(max(0, tick - 10 * i))}
            for i in range(5)
        ]
        active_cluster = get_cluster_for_tick(tick)

        # Add signal every 10 ticks
        if tick % 10 == 0:
            lm.store(
                generate_signal_content(tick, active_cluster),
                'signal', random.uniform(0.5, 0.9),
                [active_cluster], current_tick=tick
            )

        # Retrieval
        results = lm.retrieve(
            query=current_goal,
            current_goal=current_goal,
            current_tick=tick,
            max_results=5,
            goal_history=goal_history,
        )

        # Flush every 5 ticks
        if tick % 5 == 0:
            lm.try_flush(tick)

        # Lightweight review every tick
        lm.incremental_review(tick)

    # Print layer sizes at end
    print(f"  Final: working={len(lm.working)} episodic={len(lm.episodic)} semantic={len(lm.semantic)} archive={len(lm.archive)}")

    # Cleanup
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)

    return lm


def main():
    ticks = 1000
    print(f"=== LayeredMemory Profiling: {ticks} ticks ===")
    print()

    profiler = cProfile.Profile()
    profiler.enable()

    lm = run_profiled(ticks)

    profiler.disable()

    print()
    print("=" * 80)
    print(" TOP FUNCTIONS (cumulative time, sorted by cumtime)")
    print("=" * 80)

    s = io.StringIO()
    stats = pstats.Stats(profiler, stream=s)
    stats.sort_stats("cumulative")
    stats.print_stats(60)
    print(s.getvalue())

    print()
    print("=" * 80)
    print(" TOP FUNCTIONS (by internal time, excl. callees)")
    print("=" * 80)

    s2 = io.StringIO()
    stats2 = pstats.Stats(profiler, stream=s2)
    stats2.sort_stats("tottime")
    stats2.print_stats(40)
    print(s2.getvalue())

    # Special focus: filter to relevant functions
    print()
    print("=" * 80)
    print(" HOTSPOT FOCUS: _calc_goal_relevance / scoring / retrieval")
    print("=" * 80)

    s3 = io.StringIO()
    stats3 = pstats.Stats(profiler, stream=s3)
    stats3.sort_stats("cumulative")
    # Print only lines mentioning our target functions
    stats3.print_stats('_calc_goal_relevance|_calc_retrieval_score|_semantic_retrieval|retrieve|prefilter|scored|access_history', 200)
    # If filter matches nothing, fallback to full
    content = s3.getvalue()
    if not content.strip():
        # Fallback: show all stats filtered to top 80 lines
        s4 = io.StringIO()
        stats4 = pstats.Stats(profiler, stream=s4)
        stats4.sort_stats("cumulative")
        stats4.print_stats(80)
        content = s4.getvalue()

    # Print stats directly since filter may not match
    stats_all = pstats.Stats(profiler)
    stats_all.sort_stats("cumulative")
    all_lines = []
    for line in stats_all.stream.getvalue().split('\n')[:120]:
        print(line)


if __name__ == "__main__":
    main()