#!/usr/bin/env python3
import json

with open('/home/minimak/mcr/stability_test_results.json') as f:
    results = json.load(f)

noises = [r['noise_ratio'] for r in results]
reps = [r['reasoning_rep'] for r in results]
goals = [r['goal_stability'] for r in results]
survival_count = sum(1 for r in results if r['survival_triggered'])
anchor_count = sum(1 for r in results if r['anchor_triggered'])
vaccine_count = sum(1 for r in results if r['vaccine_triggered'])
immune_actions = [r['memory_immune_action'] for r in results]

print('=== 机制触发统计 ===')
print(f'MemoryImmune: cleaned={immune_actions.count("cleaned")}, boosted={immune_actions.count("boosted")}, none={immune_actions.count("none")}')
print(f'ReasoningVaccine: 触发={vaccine_count}/100')
print(f'AttentionAnchor: 触发={anchor_count}/100')
print(f'SurvivalTriggers: 触发={survival_count}/100')

print('\n=== 指标趋势（每20tick） ===')
for i in range(0, 100, 20):
    r = results[i]
    print(f'tick {r["tick"]:3d}: noise={r["noise_ratio"]:6.1%} rep={r["reasoning_rep"]:5.2f} goal={r["goal_stability"]:5.3f} drift={r["drift_score"]:5.3f}')

print('\n=== 混沌事件 ===')
chaos_events = [(r['tick'], r['chaos']) for r in results if r['chaos']]
print(f'混沌事件数: {len(chaos_events)}')
for t, c in chaos_events[:10]:
    print(f'  tick {t}: {c}')
print('  ...')