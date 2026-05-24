#!/usr/bin/env python3
"""混沌实验：对比有/无稳定机制的100tick表现"""
import random
import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from loop import CognitiveLoop
from event_system import EventType, create_event

def check_repetition(chain):
    if len(chain) < 3:
        return 0.0
    summaries = [c.get('summary', '') for c in chain[-10:]]
    unique = len(set(summaries))
    return 1.0 - (unique / len(summaries)) if summaries else 0.0

def inject_chaos(loop, tick):
    chaos_types = ['conflicting_goal', 'irrelevant_memory', 'noisy_observation', 'interrupted_plan', 'duplicated_event']
    if tick % 5 == 0 and tick > 0:
        chaos_type = random.choice(chaos_types)
        if chaos_type == 'conflicting_goal':
            goals = ['突然想研究量子计算', '改做 Python 项目', '去睡觉', '刷抖音', '研究区块链']
            loop.events.push(create_event(EventType.GOAL_UPDATED, {'goal': random.choice(goals), 'reason': 'chaos'}, 'chaos'))
        elif chaos_type == 'irrelevant_memory':
            mems = ['记得小时候养过一只猫叫阿花', '想起高中数学老师说过的一句话', '突然想到三年前去过的一个城市']
            loop.memory.store(random.choice(mems), 'noise', 0.3, ['chaos', 'irrelevant'])
        elif chaos_type == 'noisy_observation':
            obs = ['好像听到窗外有鸟叫', '感觉有点困', '手机屏幕有点脏']
            loop.events.push(create_event(EventType.OBSERVATION_ADDED, {'content': random.choice(obs), 'source': 'chaos'}, 'chaos'))
        elif chaos_type == 'interrupted_plan':
            if loop.state.get('active_plan'):
                loop.state['active_plan'] = None
        elif chaos_type == 'duplicated_event':
            if loop.events.size() > 0:
                loop.events.push(loop.events.peek(1)[0])
        return chaos_type
    return None

print('MCR Stability Mechanisms Test - 100 ticks with anti-entropy')
print('=' * 80)

loop = CognitiveLoop()
loop.state['current_goal'] = '稳定性机制验证 - 100 tick 对比实验'
loop.state['active_plan'] = {'goal': '稳定性机制验证', 'steps': ['观察', '思考'], 'created_at': datetime.now().isoformat()}
loop.state['metadata']['goal_stability_score'] = 1.0

results = []
for i in range(100):
    chaos_type = inject_chaos(loop, i + 1)
    result = loop.run_cycle()
    
    chain = loop.state.get('reasoning_chain', [])
    mems = loop.memory.memories
    noise = [m for m in mems if m.get('type') == 'noise']
    
    metrics = {
        'tick': result['cycle'],
        'drift_score': result['drift_score'],
        'goal_stability': loop.state.get('metadata', {}).get('goal_stability_score', 1.0),
        'reasoning_rep': check_repetition(chain),
        'memory_count': len(mems),
        'noise_count': len(noise),
        'noise_ratio': len(noise) / max(1, len(mems)),
        'survival_triggered': result.get('stability', {}).get('survival_triggered', False),
        'memory_immune_action': result.get('stability', {}).get('memory_immune', {}).get('action', 'none'),
        'vaccine_triggered': result.get('stability', {}).get('reasoning_vaccine', {}).get('vaccine_triggered', False),
        'anchor_triggered': result.get('stability', {}).get('attention_anchor', {}).get('needs_anchor', False),
        'chaos': chaos_type,
    }
    results.append(metrics)
    
    if (i + 1) % 20 == 0:
        print(f"tick {result['cycle']:3d} | drift: {metrics['drift_score']:.3f} | goal_stab: {metrics['goal_stability']:.3f} | reason_rep: {metrics['reasoning_rep']:.2f} | noise_ratio: {metrics['noise_ratio']:.1%} | survival: {metrics['survival_triggered']} | anchor: {metrics['anchor_triggered']}")

final = results[-1]
initial = results[0]
print('=' * 80)
print('最终对比结果:')
print(f"Goal 漂移: {initial['goal_stability']:.3f} -> {final['goal_stability']:.3f} (Δ={initial['goal_stability'] - final['goal_stability']:.3f})")
print(f"Noise Ratio: {initial['noise_ratio']:.1%} -> {final['noise_ratio']:.1%}")
print(f"Reasoning 重复: {initial['reasoning_rep']:.2f} -> {final['reasoning_rep']:.2f}")
print(f"Survival 触发次数: {sum(1 for r in results if r['survival_triggered'])}")
print(f"Anchor 重聚焦次数: {sum(1 for r in results if r['anchor_triggered'])}")
print(f"MemoryImmune actions: {dict((a, sum(1 for r in results if r['memory_immune_action'] == a)) for a in set(r['memory_immune_action'] for r in results))}")
print(f"Vaccine 触发次数: {sum(1 for r in results if r['vaccine_triggered'])}")

# 保存详细结果
with open('./stability_test_results.json', 'w') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print('\n详细结果已保存到 stability_test_results.json')