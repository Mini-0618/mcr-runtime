#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/minimax/mcr')
from layered_memory import LayeredMemory
import shutil, os

tmp = '/tmp/test_sem2'
if os.path.exists(tmp): shutil.rmtree(tmp)
m = LayeredMemory(tmp)

sem_knowledge = [
    {'cluster': 'debug', 'content': '空指针异常通常由未初始化的对象引用引起', 'importance': 0.8},
    {'cluster': 'debug', 'content': '内存泄漏多数由于未关闭数据库连接和文件句柄', 'importance': 0.9},
    {'cluster': 'project_a', 'content': '项目A：接口兼容性问题是不同版本协议导致的', 'importance': 0.8},
    {'cluster': 'project_a', 'content': '项目A：模块响应慢通常需要优化数据库查询和缓存策略', 'importance': 0.8},
    {'cluster': 'research', 'content': '模型训练loss不收敛可能是学习率过大或数据标注问题', 'importance': 0.9},
]
for kw in sem_knowledge:
    m.store(kw['content'], 'semantic', kw['importance'], [kw['cluster']], current_tick=0)

print('After store, before review:')
print(f'  working: {len(m.working)}')
print(f'  episodic: {len(m.episodic)}')
print(f'  semantic: {len(m.semantic)}')
print(f'  archive: {len(m.archive)}')

for item in m.working:
    print(f'  WORKING: {item["content"][:40]} state={item.get("state")}')

# Run a few ticks of incremental review
for t in range(1, 21):
    m.incremental_review(t)

print('\nAfter 20 ticks of incremental_review:')
print(f'  working: {len(m.working)}')
print(f'  episodic: {len(m.episodic)}')
print(f'  semantic: {len(m.semantic)}')
print(f'  archive: {len(m.archive)}')

for item in m.semantic:
    print(f'  SEMANTIC: {item["content"][:40]}')
